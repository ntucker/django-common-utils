from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.core import urlresolvers


class AdminUrlModel(object):
    """Mixin that provides get_admin_url method"""
    def get_admin_url(self):
        content_type = ContentType.objects.get_for_model(self.__class__)
        return urlresolvers.reverse("admin:%s_%s_change" % (content_type.app_label, content_type.model),
                                    args=(self.id,))
