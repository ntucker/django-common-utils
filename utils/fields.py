import uuid
import six

import psycopg2.extras

from django import forms
from django.db import models

psycopg2.extras.register_uuid()


class UUIDField(six.with_metaclass(models.SubfieldBase, models.Field)):
    def __init__(self, *args, **kwargs):
        auto = kwargs.get('auto', False)
        if auto or kwargs.get('primary_key', False):
            kwargs['editable'] = False
            kwargs['blank'] = True
            kwargs['unique'] = True
        if auto:
            kwargs['default'] = uuid.uuid4
        super(UUIDField, self).__init__(*args, **kwargs)

    def db_type(self, connection=None):
        return 'uuid'

    def get_db_prep_value(self, value, connection, prepared=False):
        if isinstance(value, uuid.UUID):
            return str(value)
        return value

    def to_python(self, value):
        if not value:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return value

    def contribute_to_class(self, cls, name):
        assert not cls._meta.has_auto_field, "A model can't have more than one AutoField."
        super(UUIDField, self).contribute_to_class(cls, name)
        cls._meta.has_auto_field = True
        cls._meta.auto_field = self


try:
    from south.modelsinspector import add_introspection_rules
    rules = [
             (
              (UUIDField,),
              [],
              {
               "auto": ["auto", {"default": True}],
               "default": ["default", {"ignore_if": 'auto'}],
               },
              )
             ]
    add_introspection_rules(rules, ["^utils\.fields\.UUIDField"])
except ImportError:
    pass
