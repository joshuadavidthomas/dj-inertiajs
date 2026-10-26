from unittest.mock import patch

from django.conf import settings
from django.core.checks import run_checks
from django.test import SimpleTestCase, override_settings


def inertia_check_ids():
    return sorted(m.id for m in run_checks() if m.id.startswith("inertia."))


class ChecksTestCase(SimpleTestCase):
    def test_valid_configuration_passes(self):
        self.assertEqual(inertia_check_ids(), [])

    @override_settings(INERTIA={"LAYOUT": "layout.html", "VERISON": "2"})
    def test_unknown_key(self):
        self.assertEqual(inertia_check_ids(), ["inertia.E001"])

    @override_settings(INERTIA={})
    def test_missing_layout(self):
        self.assertEqual(inertia_check_ids(), ["inertia.E002"])

    @override_settings(INERTIA={"LAYOUT": "layout.html", "SSR": {"ENABLED": True}})
    def test_ssr_without_requests(self):
        with patch("django_inertia.checks.find_spec", return_value=None):
            self.assertEqual(inertia_check_ids(), ["inertia.E003"])

    @override_settings(
        INERTIA={"LAYOUT": "layout.html", "SHARED_PROPS": ["nowhere.shared"]}
    )
    def test_unimportable_shared_props(self):
        self.assertEqual(inertia_check_ids(), ["inertia.E006"])

    def test_missing_middleware(self):
        middleware = [
            m
            for m in settings.MIDDLEWARE
            if not m.endswith(("InertiaMiddleware", "SessionMiddleware"))
        ]
        with override_settings(MIDDLEWARE=middleware):
            self.assertEqual(inertia_check_ids(), ["inertia.E004", "inertia.E005"])

    def test_middleware_subclasses_count(self):
        middleware = [
            m.replace(
                "django_inertia.middleware.InertiaMiddleware",
                "django_inertia.tests.testapp.middleware.CustomInertiaMiddleware",
            )
            for m in settings.MIDDLEWARE
        ]
        with override_settings(MIDDLEWARE=middleware):
            self.assertEqual(inertia_check_ids(), [])
