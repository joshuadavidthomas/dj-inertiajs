from django.test import override_settings

from django_inertia.tests.utils import ProtocolTestCase


class SettingsTestCase(ProtocolTestCase):
    @override_settings(INERTIA={"LAYOUT": "layout.html", "VERSION": "2.0"})
    def test_version_works(self):
        response = self.inertia.get("/empty/", HTTP_X_INERTIA_VERSION="2.0")

        self.assertEqual(response.status_code, 200)

    def test_version_fallsback(self):
        response = self.inertia.get("/empty/", HTTP_X_INERTIA_VERSION="1.0")

        self.assertEqual(response.status_code, 200)

    def test_layout(self):
        response = self.client.get("/empty/")
        self.assertTemplateUsed(response, "layout.html")
