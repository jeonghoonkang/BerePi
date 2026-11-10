"""Authenticated feature-test fixtures. Production has no anonymous bypass.

Feature tests exercise their API as a known Basic client; auth tests import the
real app factory directly and verify anonymous requests are always denied.
"""
import os
from unittest.mock import patch

from flask.testing import FlaskClient
from werkzeug.datastructures import Headers
from app import create_app as real_create_app

TEST_PASSWORD = 'feature-test-password-only'


class FeatureClient(FlaskClient):
    def open(self, *args, **kwargs):
        if os.environ.get('PHOTO_BROWSER_PASSWORD'):
            return super().open(*args, **kwargs)
        # Only a test client supplies this credential; the application never
        # accepts anonymous requests and no testing flag weakens its guard.
        if 'auth' not in kwargs and not Headers(kwargs.get('headers')).get('Authorization'):
            kwargs['auth'] = ('feature-test', TEST_PASSWORD)
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': TEST_PASSWORD}):
            return super().open(*args, **kwargs)


def create_app(*args, **kwargs):
    if os.environ.get('PHOTO_BROWSER_PASSWORD'):
        app = real_create_app(*args, **kwargs)
    else:
        with patch.dict(os.environ, {'PHOTO_BROWSER_PASSWORD': TEST_PASSWORD}):
            app = real_create_app(*args, **kwargs)
    app.test_client_class = FeatureClient
    return app
