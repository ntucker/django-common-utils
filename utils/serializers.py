from __future__ import unicode_literals

from rest_framework import serializers
from utils.fields import DateTimeRange, DateTimeRangeSerializerField, AutoUUIDField
from aloha.fields import HTMLField, HTMLSerializerField


class BaseModelSerializer(serializers.HyperlinkedModelSerializer):
    serializer_field_mapping = dict(serializers.HyperlinkedModelSerializer.serializer_field_mapping.items() + {DateTimeRange: DateTimeRangeSerializerField,
                                                                                                               AutoUUIDField: serializers.UUIDField,
                                                                                                               HTMLField: HTMLSerializerField,
                                                                                                               }.items())
    

    def get_default_field_names(self, declared_fields, model_info):
        """
        Return the default list of field names that will be used if the
        `Meta.fields` option is not specified.
        """
        return (
            [model_info.pk.name] + super(BaseModelSerializer, self).get_default_field_names(declared_fields, model_info)
        )

    def build_standard_field(self, field_name, model_field):
        """
        Create regular model fields.
        """
        field_class, field_kwargs = super(BaseModelSerializer, self).build_standard_field(field_name, model_field)
        
        if field_class == HTMLSerializerField:
            for k in field_class.KWARG:
                if hasattr(model_field, k):
                    field_kwargs[k] = getattr(model_field, k)

        return field_class, field_kwargs
