from __future__ import unicode_literals

import json

from simplejson.encoder import JSONEncoderForHTML

from rest_framework.utils.encoders import JSONEncoder


JSONRestEncoderForHTML = type(b'JSONRestEncoderForHTML', (JSONEncoderForHTML,), dict(JSONEncoder.__dict__))