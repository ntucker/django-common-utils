from __future__ import unicode_literals
import json as jsonencode
from datetime import datetime
import pytz

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def absolute_url(context, obj):
    return obj.get_absolute_url(context.get('request', None))

@register.filter
@stringfilter
def underslug(string):
    return string.replace(" ", "_").replace("'", "").lower()

@register.filter
def json(obj):
    return mark_safe(jsonencode.dumps(obj))

@register.filter(name='timestamptodate')
def timestamptodate(value):
    return datetime.fromtimestamp(float(value)/1000, tz=pytz.UTC)

@register.filter(name='reversed')
def reversed_filter(value):
    return reversed(value)