from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.core import urlresolvers
from django.db import models
from django.db.models import signals
from django.db import transaction

from .fields import AutoUUIDField

class AdminUrlModel(object):
    """Mixin that provides get_admin_url method"""
    def get_admin_url(self):
        content_type = ContentType.objects.get_for_model(self.__class__)
        return urlresolvers.reverse("admin:%s_%s_change" % (content_type.app_label, content_type.model),
                                    args=(self.id,))


class UUIDModel(models.Model):
    """Provides UIID primary key
    Make sure to execute db.execute("ALTER TABLE appname_modelname ALTER COLUMN id SET DEFAULT uuid_generate_v4();")
    """
    id = AutoUUIDField("id")

    class Meta:
        abstract = True

