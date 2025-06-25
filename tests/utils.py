import contextlib

from django.conf import settings
from django.test import override_settings


@contextlib.contextmanager
def override_app_settings(**kwargs):
    with override_settings(DJ_INERTIAJS=settings.DJ_INERTIAJS | kwargs):
        yield
