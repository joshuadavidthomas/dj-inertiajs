from django.test import override_settings

from dj_inertiajs.tests.utils import ProtocolTestCase


class SettingsTestCase(ProtocolTestCase):
    @override_settings(INERTIA={"LAYOUT": "layout.html", "VERSION": "2.0"})
    def test_version_works(self):
        response = self.client.get("/empty/", headers={"x-inertia-version": "2.0"})

        self.assertEqual(response.status_code, 200)

    def test_version_fallsback(self):
        response = self.client.get("/empty/", headers={"x-inertia-version": "1.0"})

        self.assertEqual(response.status_code, 200)

    @override_settings(INERTIA={"LAYOUT": "layout.html", "VERSION": lambda: "abc123"})
    def test_version_can_be_a_callable(self):
        response = self.client.get("/empty/", headers={"x-inertia-version": "abc123"})
        self.assertEqual(response.inertia.version, "abc123")

        response = self.client.get("/empty/", headers={"x-inertia-version": "1.0"})
        self.assertEqual(response.status_code, 409)

    def test_layout(self):
        response = self.client.get("/empty/", inertia=False)
        self.assertTemplateUsed(response, "layout.html")
