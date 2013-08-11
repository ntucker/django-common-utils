import uuid
import six

import psycopg2.extras, psycopg2.extensions

from django import forms
from django.db import models
from django.core.exceptions import ValidationError
from django.forms.util import from_current_timezone

from .widgets import DateTimeRangeWidget

psycopg2.extras.register_uuid()


class UUIDField(six.with_metaclass(models.SubfieldBase, models.Field)):
    def __init__(self, *args, **kwargs):
        self.auto = kwargs.get('auto', False)
        if self.auto or kwargs.get('primary_key', False):
            kwargs['editable'] = False
            kwargs['blank'] = True
            kwargs['unique'] = True
        if self.auto:
            print("WARNING")
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
    from rest_framework import serializers
    class DateTimeRangeSerializerField(serializers.DateTimeField):
        def to_native(self, value):
            return list(map(super(DateTimeRangeSerializerField, self).to_native, [value.lower, value.upper]))

        def from_native(self, data):
            data = [from_current_timezone(super(DateTimeRangeSerializerField, self).from_native(value)) for value in data]
            if data[1] is not None and data[0] > data[1]:
                raise ValidationError('Range must end after it starts')
            return psycopg2.extras.DateTimeTZRange(data[0], data[1])
except ImportError:
    pass

class DateTimeRangeFormField(forms.MultiValueField):
    widget = DateTimeRangeWidget
    def __init__(self, *args, **kwargs):
        fields = (forms.DateTimeField(), forms.DateTimeField())
        super(DateTimeRangeFormField, self).__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        if data_list[0] > data_list[1]:
            raise ValidationError('Range must end after it starts')
        return psycopg2.extras.DateTimeTZRange(data_list[0], data_list[1])

class DateTimeRange(six.with_metaclass(models.SubfieldBase, models.Field)):
    def __init__(self, *args, **kwargs):
        self.require_lower = kwargs.pop('require_lower', False)
        self.require_upper = kwargs.pop('require_upper', False)
        super(DateTimeRange, self).__init__(*args, **kwargs)
        
    def db_type(self, connection=None):
        return 'tstzrange'

    def validate(self, value, model_instance):
        super(DateTimeRange, self).validate(value, model_instance)
        if self.require_lower and value.lower is None:
            raise ValidationError("Lower datetime bound must be set")
        if self.require_upper and value.upper is None:
            raise ValidationError("Upper datetime bound must be set")
        
    def formfield(self, **kwargs):
        defaults = {'form_class': DateTimeRangeFormField}
        defaults.update(kwargs)
        return super(DateTimeRange, self).formfield(**defaults)


try:
    from south.modelsinspector import add_introspection_rules
    rules = [
             (
              (UUIDField,),
              [],
              {
               "auto": ["auto", {"default": False}],
               "default": ["default", {"ignore_if": 'auto'}],
               },
              )
             ]
    add_introspection_rules(rules, ["^utils\.fields\.UUIDField"])
    rules = [
             (
              (DateTimeRange,),
              [],
              {
               "require_lower": ["require_lower", {"default": False}],
               "require_upper": ["require_upper", {"default": False}],
               },
              )
             ]
    add_introspection_rules(rules, ["^utils\.fields\.DateTimeRange"])
except ImportError:
    pass
