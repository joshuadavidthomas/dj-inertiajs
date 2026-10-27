import re
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.checks import run_checks
from django.test import SimpleTestCase, override_settings

from dj_inertiajs import checks


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
        with patch("dj_inertiajs.checks.find_spec", return_value=None):
            self.assertEqual(inertia_check_ids(), ["inertia.E003"])

    @override_settings(
        INERTIA={"LAYOUT": "layout.html", "SHARED_PROPS": ["nowhere.shared"]}
    )
    def test_unimportable_shared_props(self):
        self.assertEqual(inertia_check_ids(), ["inertia.E006"])

    @override_settings(
        INERTIA={"LAYOUT": "layout.html", "FORM_ERRORS": "nowhere.errors"}
    )
    def test_unimportable_dotted_path(self):
        self.assertEqual(inertia_check_ids(), ["inertia.E011"])

    @override_settings(INERTIA={"LAYOUT": "layout.html", "VERSION": 2})
    def test_version_of_the_wrong_type(self):
        self.assertEqual(inertia_check_ids(), ["inertia.E012"])

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
                "dj_inertiajs.middleware.InertiaMiddleware",
                "tests.testapp.middleware.CustomInertiaMiddleware",
            )
            for m in settings.MIDDLEWARE
        ]
        with override_settings(MIDDLEWARE=middleware):
            self.assertEqual(inertia_check_ids(), [])


class UpgradeChecksTestCase(SimpleTestCase):
    @override_settings(INERTIA_LAYOUT="base.html", INERTIA_SSR_URL="http://ssr")
    def test_old_settings(self):
        messages = [m for m in run_checks() if m.id == "inertia.E007"]

        self.assertEqual(
            [m.msg for m in messages],
            [
                "INERTIA_LAYOUT is an inertia-django setting and is ignored.",
                "INERTIA_SSR_URL is an inertia-django setting and is ignored.",
            ],
        )
        self.assertIn('Use INERTIA["SSR"]["URL"].', messages[1].hint)

    def test_old_middleware(self):
        middleware = [*settings.MIDDLEWARE, "inertia.middleware.InertiaMiddleware"]
        with override_settings(MIDDLEWARE=middleware):
            self.assertEqual(inertia_check_ids(), ["inertia.E008"])

    def test_old_app(self):
        with patch(
            "dj_inertiajs.checks.apps.is_installed",
            side_effect=lambda n: n == "inertia",
        ):
            self.assertEqual(inertia_check_ids(), ["inertia.E009"])

    @override_settings(INERTIA={"LAYOUT": "old_layout.html"})
    def test_layout_with_old_blocks(self):
        self.assertEqual(inertia_check_ids(), ["inertia.E010"])

    @override_settings(INERTIA={"LAYOUT": "missing.html"})
    def test_missing_layout_template_is_left_to_rendering(self):
        self.assertEqual(inertia_check_ids(), [])

    def test_every_guide_section_the_hints_name_exists(self):
        root = Path(__file__).parents[1]
        guide = root / "docs/guide/upgrading-from-inertia-django.md"
        headings = set(re.findall(r"^#+ (.+)$", guide.read_text(), re.MULTILINE))
        source = Path(checks.__file__).read_text()
        named = set(re.findall(r"""guide\(["']([^"']+)["']\)""", source))

        self.assertTrue(named)
        self.assertEqual(named - headings, set())
