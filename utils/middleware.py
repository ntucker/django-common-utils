from __future__ import unicode_literals, print_function

import re
import logging
from pprint import pprint

from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.contrib.redirects.models import Redirect
from django import http
from django.core.cache import cache
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.utils.cache import cc_delim_re, patch_vary_headers
from django.db import connection

logger = logging.getLogger(__name__)


class QueryDebuggerMiddleware(object):
    def process_response(self, request, response):
        print("[")
        for query in connection.queries:
            line = " ".join((query['sql'] or "", 'in', query['time'])).encode("ascii", errors="replace")
            print("  ", line)
        print("]")
        return response


def remove_vary_headers(response, deleteheaders):
    """
    Removes the "Vary" header in the given HttpResponse object.
    newheaders is a list of header names that should be in "Vary".
    """
    # Note that we need to keep the original order intact, because cache
    # implementations may rely on the order of the Vary contents in, say,
    # computing an MD5 hash.
    if response.has_header('Vary'):
        vary_headers = cc_delim_re.split(response['Vary'])
        # Use .lower() here so we treat headers as case-insensitive.
        deleteheaders = set(deleteheaders)
        headers = [header for header in vary_headers if header.lower() not in deleteheaders]
        if headers:
            response['Vary'] = ', '.join(headers)
        else:
            del response['Vary']


class VaryOnBots(object):
    def process_response(self, request, response):
        if hasattr(request, 'user_agent') and request.user_agent.is_bot:
            patch_vary_headers(response, ("User-Agent",))
        return response

class VaryOnAjax(object):
    def process_response(self, request, response):
        if request.is_ajax():
            patch_vary_headers(response, ("X-Requested-With",))
        return response


class RemoveCookieVaryHeader(object):
    def process_response(self, request, response):
        # remove_vary_headers(response, ("cookie",))
        patch_vary_headers(response, ("Set-Cookie",))
        return response


class StripCookieMiddleware(object):
    strip_re = re.compile(r'\b(__[^=]+=.+?(?:; |$))')

    def process_request(self, request):
        try:
            cookie = self.strip_re.sub('', request.META['HTTP_COOKIE'])
            request.META['HTTP_COOKIE'] = cookie
        except:
            pass


class DeleteSessionOnLogoutMiddleware(object):
    """Delete sessionid and csrftoken cookies on logout, for better compatibility with upstream caches."""
    def process_response(self, request, response):
        if getattr(request, '_delete_session', False):
            response.delete_cookie(settings.CSRF_COOKIE_NAME, domain=settings.CSRF_COOKIE_DOMAIN)
            response.delete_cookie(settings.SESSION_COOKIE_NAME, settings.SESSION_COOKIE_PATH, settings.SESSION_COOKIE_DOMAIN)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        try:
            view_name = '.'.join((view_func.__module__, view_func.__name__))
            # flag for deletion if this is a logout view
            request._delete_session = view_name in ('django.contrib.admin.sites.logout', 'django.contrib.auth.views.logout', 'account.views.LogoutView') and request.method == 'POST'
        except AttributeError:
            pass  # if view_func doesn't have __module__ or __name__ attrs


class PrivateBetaMiddleware(object):
    """
    Stolen from https://github.com/pragmaticbadger/django-privatebeta

    Add this to your ``MIDDLEWARE_CLASSES`` make all views except for
    those in the account application require that a user be logged in.
    This can be a quick and easy way to restrict views on your site,
    particularly if you remove the ability to create accounts.
    **Settings:**
    ``PRIVATEBETA_ENABLE_BETA``
    Whether or not the beta middleware should be used. If set to `False`
    the PrivateBetaMiddleware middleware will be ignored and the request
    will be returned. This is useful if you want to disable privatebeta
    on a development machine. Default is `True`.
    ``PRIVATEBETA_NEVER_ALLOW_VIEWS``
    A list of full view names that should *never* be displayed. This
    list is checked before the others so that this middleware exhibits
    deny then allow behavior.
    ``PRIVATEBETA_ALWAYS_ALLOW_VIEWS``
    A list of full view names that should always pass through.

    ``PRIVATEBETA_ALWAYS_ALLOW_MODULES``
    A list of modules that should always pass through. All
    views in ``django.contrib.auth.views``, ``django.views.static``
    and ``privatebeta.views`` will pass through unless they are
    explicitly prohibited in ``PRIVATEBETA_NEVER_ALLOW_VIEWS``
    ``PRIVATEBETA_REDIRECT_URL``
    The URL to redirect to. Can be relative or absolute.
    """

    def __init__(self):
        self.enable_beta = getattr(settings, 'PRIVATEBETA_ENABLE_BETA', True)
        self.beta_end_time = getattr(settings, 'PRIVATEBETA_END_TIME', None)
        self.always_allow_modules = getattr(settings, 'PRIVATEBETA_ALWAYS_ALLOW_MODULES', [])
        self.redirect_url = getattr(settings, 'PRIVATEBETA_REDIRECT_URL', '/')

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.path == self.redirect_url or request.user.is_authenticated() or not self.enable_beta or (self.beta_end_time and timezone.now() >= self.beta_end_time):
            # User is logged in, no need to check anything else.
            return
        whitelisted_modules = ['django.contrib.auth.views', 'django.views.static', ]
        if self.always_allow_modules:
            whitelisted_modules += self.always_allow_modules

        if '%s' % view_func.__module__ in whitelisted_modules:
            return
        else:
            return HttpResponseRedirect(self.redirect_url)


DNE = "!!!404!!!"
REDIRECT_KEY_PREFIX = getattr(settings, 'CACHE_REDIRECT_KEY_PREFIX', 'redirect')
CACHE_REDIRECT_TIMEOUT = getattr(settings, 'CACHE_REDIRECT_SECONDS', 1000000000)

def redirect_cache_key(path):
    return u":".join((REDIRECT_KEY_PREFIX, path))


class RedirectFallbackMiddleware(object):
    def process_response(self, request, response):
        if response.status_code != 404:
            return response  # No need to check for a redirect for non-404 responses.
        path = request.get_full_path()
        cache_key = redirect_cache_key(path)
        new_path = cache.get(cache_key, None)
        if new_path is None:
            try:
                r = Redirect.objects.get(site__id__exact=settings.SITE_ID, old_path=path)
            except Redirect.DoesNotExist:
                r = None
            if r is None and settings.APPEND_SLASH:
                # Try removing the trailing slash.
                try:
                    r = Redirect.objects.get(site__id__exact=settings.SITE_ID,
                                             old_path=path[:path.rfind('/')] + path[path.rfind('/') + 1:])
                except Redirect.DoesNotExist:
                    pass
            if r is not None:
                new_path = r.new_path
                cache.set(cache_key, new_path, CACHE_REDIRECT_TIMEOUT)
            else:
                cache.set(cache_key, DNE, CACHE_REDIRECT_TIMEOUT)
        if new_path is not None:
            if new_path == '':
                return http.HttpResponseGone()
            if new_path != DNE:
                return http.HttpResponsePermanentRedirect(new_path)

        # No redirect was found. Return the response.
        return response


@receiver(pre_save, sender=Redirect, dispatch_uid="invalidate_redirect_cache")
def invalidate_redirect_cache(instance, **kwargs):
    if instance.pk:
        old_instance = Redirect.objects.get(pk=instance.pk)
        if old_instance.old_path != instance.old_path:
            cache_key = redirect_cache_key(old_instance.old_path)
            cache.set(cache_key, DNE, CACHE_REDIRECT_TIMEOUT)

@receiver(post_save, sender=Redirect, dispatch_uid="update_redirect_cache")
def update_redirect_cache(instance, **kwargs):
    cache_key = redirect_cache_key(instance.old_path)
    cache.set(cache_key, instance.new_path, CACHE_REDIRECT_TIMEOUT)

@receiver(post_delete, sender=Redirect, dispatch_uid="delete_redirect_cache")
def delete_redirect_cache(instance, **kwargs):
    cache_key = redirect_cache_key(instance.old_path)
    cache.set(cache_key, DNE, CACHE_REDIRECT_TIMEOUT)
