from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.core import urlresolvers
from django.db import models
from django.db.models import signals
from django.db import transaction

from .fields import UUIDField

class AdminUrlModel(object):
    """Mixin that provides get_admin_url method"""
    def get_admin_url(self):
        content_type = ContentType.objects.get_for_model(self.__class__)
        return urlresolvers.reverse("admin:%s_%s_change" % (content_type.app_label, content_type.model),
                                    args=(self.id,))


class UUIDModel(models.Model):
    """Provides UIID primary key
    Make sure to execute db.execute("ALTER TABLE appname_modelname ALTER COLUMN id SET DEFAULT uuid_generate_v4();")
    Overrides save_base purely to check for UUIDField instead of AutoField to ignore upon creation
    """
    id = UUIDField("id", primary_key=True, default=None)

    class Meta:
        abstract = True

    def save_base(self, raw=False, cls=None, origin=None, force_insert=False,
                  force_update=False, using=None, update_fields=None):
        """
        Does the heavy-lifting involved in saving. Subclasses shouldn't need to
        override this method. It's separate from save() in order to hide the
        need for overrides of save() to pass around internal-only parameters
        ('raw', 'cls', and 'origin').
        """
        using = using or router.db_for_write(self.__class__, instance=self)
        assert not (force_insert and (force_update or update_fields))
        assert update_fields is None or len(update_fields) > 0
        if cls is None:
            cls = self.__class__
            meta = cls._meta
            if not meta.proxy:
                origin = cls
        else:
            meta = cls._meta

        if origin and not meta.auto_created:
            signals.pre_save.send(sender=origin, instance=self, raw=raw, using=using,
                                  update_fields=update_fields)

        # If we are in a raw save, save the object exactly as presented.
        # That means that we don't try to be smart about saving attributes
        # that might have come from the parent class - we just save the
        # attributes we have been given to the class we have been given.
        # We also go through this process to defer the save of proxy objects
        # to their actual underlying model.
        if not raw or meta.proxy:
            if meta.proxy:
                org = cls
            else:
                org = None
            for parent, field in meta.parents.items():
                # At this point, parent's primary key field may be unknown
                # (for example, from administration form which doesn't fill
                # this field). If so, fill it.
                if field and getattr(self, parent._meta.pk.attname) is None and getattr(self, field.attname) is not None:
                    setattr(self, parent._meta.pk.attname, getattr(self, field.attname))

                self.save_base(cls=parent, origin=org, using=using,
                               update_fields=update_fields)

                if field:
                    setattr(self, field.attname, self._get_pk_val(parent._meta))
                    # Since we didn't have an instance of the parent handy, we
                    # set attname directly, bypassing the descriptor.
                    # Invalidate the related object cache, in case it's been
                    # accidentally populated. A fresh instance will be
                    # re-built from the database if necessary.
                    cache_name = field.get_cache_name()
                    if hasattr(self, cache_name):
                        delattr(self, cache_name)

            if meta.proxy:
                return

        if not meta.proxy:
            non_pks = [f for f in meta.local_fields if not f.primary_key]

            if update_fields:
                non_pks = [f for f in non_pks if f.name in update_fields or f.attname in update_fields]

            # First, try an UPDATE. If that doesn't update anything, do an INSERT.
            pk_val = self._get_pk_val(meta)
            pk_set = pk_val is not None
            record_exists = True
            manager = cls._base_manager
            if pk_set:
                # Determine if we should do an update (pk already exists, forced update,
                # no force_insert)
                if ((force_update or update_fields) or (not force_insert and
                        manager.using(using).filter(pk=pk_val).exists())):
                    if force_update or non_pks:
                        values = [(f, None, (raw and getattr(self, f.attname) or f.pre_save(self, False))) for f in non_pks]
                        if values:
                            rows = manager.using(using).filter(pk=pk_val)._update(values)
                            if force_update and not rows:
                                raise DatabaseError("Forced update did not affect any rows.")
                            if update_fields and not rows:
                                raise DatabaseError("Save with update_fields did not affect any rows.")
                else:
                    record_exists = False
            if not pk_set or not record_exists:
                if meta.order_with_respect_to:
                    # If this is a model with an order_with_respect_to
                    # autopopulate the _order field
                    field = meta.order_with_respect_to
                    order_value = manager.using(using).filter(**{field.name: getattr(self, field.attname)}).count()
                    self._order = order_value

                fields = meta.local_fields
                if not pk_set:
                    if force_update or update_fields:
                        raise ValueError("Cannot force an update in save() with no primary key.")
                    fields = [f for f in fields if not isinstance(f, UUIDField)]

                record_exists = False

                update_pk = bool(meta.has_auto_field and not pk_set)
                result = manager._insert([self], fields=fields, return_id=update_pk, using=using, raw=raw)

                if update_pk:
                    setattr(self, meta.pk.attname, result)
            transaction.commit_unless_managed(using=using)

        # Store the database on which the object was saved
        self._state.db = using
        # Once saved, this is no longer a to-be-added instance.
        self._state.adding = False

        # Signal that the save is complete
        if origin and not meta.auto_created:
            signals.post_save.send(sender=origin, instance=self, created=(not record_exists),
                                   update_fields=update_fields, raw=raw, using=using)

    save_base.alters_data = True

