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
