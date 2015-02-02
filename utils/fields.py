import uuid
import six

import psycopg2.extras, psycopg2.extensions

from django import forms
from django.db import models
from django.db.models import Lookup, Transform
from django.db.models.fields import AutoField
from django.core.exceptions import ValidationError
from django.forms.util import from_current_timezone

from djorm_pgarray.fields import ContainedByLookup, ContainsLookup, OverlapLookup, ArrayField

from .widgets import DateTimeRangeWidget

psycopg2.extras.register_uuid()


class UUIDField(six.with_metaclass(models.SubfieldBase, models.Field)):
    def __init__(self, *args, **kwargs):
        self.auto = kwargs.get('auto', False)
        if self.auto or kwargs.get('primary_key', False):
            kwargs['editable'] = False
            kwargs['unique'] = True
        if self.auto:
            kwargs['default'] = uuid.uuid4
        super(UUIDField, self).__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(UUIDField, self).deconstruct()
        if self.auto != False:
            kwargs['auto'] = self.auto
        if self.auto or kwargs.get('primary_key', False):
            del kwargs['editable']
            del kwargs['unique']
        if self.auto:
            del kwargs['default']
        return name, path, args, kwargs

    def db_type(self, connection=None):
        return 'uuid'

    def get_db_prep_value(self, value, connection, prepared=False):
        if isinstance(value, uuid.UUID):
            return str(value)
        return value
    
    def get_prep_value(self, value):
        return value

    def to_python(self, value):
        if not value:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return value


class AutoUUIDField(UUIDField, AutoField):
    """Make sure to execute db.execute("ALTER TABLE appname_modelname ALTER COLUMN id SET DEFAULT uuid_generate_v4();")"""
    def __init__(self, *args, **kwargs):
        kwargs['primary_key'] = True
        kwargs['default'] = None
        super(AutoUUIDField, self).__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(AutoUUIDField, self).deconstruct()
        del kwargs['primary_key']
        del kwargs['default']
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name):
        AutoField.contribute_to_class(self, cls, name)


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

    def deconstruct(self):
        name, path, args, kwargs = super(DateTimeRange, self).deconstruct()
        if self.require_lower != False:
            kwargs['require_lower'] = self.require_lower
        if self.require_lower != False:
            kwargs['require_upper'] = self.require_upper
        return name, path, args, kwargs

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


class LowercaseTransform(Transform):
    lookup_name = 'array_lowercase'
    def as_sql(self, qn, connection):
        lhs, params = qn.compile(self.lhs)
        return "array_lowercase(%s)" % (lhs,), params


class SingleContainedByLookup(ContainedByLookup):
    def as_sql(self, qn, connection):
        lhs, lhs_params = self.process_lhs(qn, connection)
        rhs, rhs_params = self.process_rhs(qn, connection)
        params = lhs_params + rhs_params
        return "ARRAY[%s] <@ %s::%s[]" % (lhs, rhs, self.lhs.output_field.db_type(connection)), params


UUIDField.register_lookup(SingleContainedByLookup)
DateTimeRange.register_lookup(ContainedByLookup)
DateTimeRange.register_lookup(ContainsLookup)
DateTimeRange.register_lookup(OverlapLookup)
ArrayField.register_lookup(LowercaseTransform)
