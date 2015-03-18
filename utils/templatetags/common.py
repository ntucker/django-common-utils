from __future__ import unicode_literals

from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.simple_tag(takes_context=True)
def absolute_url(context, obj):
    return obj.get_absolute_url(context.get('request', None))

@register.filter
@stringfilter
def underslug(string):
    return string.replace(" ", "_").replace("'", "").lower()