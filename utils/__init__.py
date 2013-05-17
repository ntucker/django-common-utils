from __future__ import unicode_literals

import hashlib

from django.utils.http import urlquote


def template_cache_key(fragment_name, *vary_on):
    """Stolen from django/templatetags/cache.py of Django 1.4"""
    args = hashlib.md5(u':'.join([urlquote(var) for var in vary_on]))
    return 'template.cache.%s.%s' % (fragment_name, args.hexdigest())
