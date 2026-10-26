from django.test import override_settings

from dj_inertiajs.tests.utils import ProtocolTestCase


class HistoryTestCase(ProtocolTestCase):
    def test_encrypt_history_setting(self):
        response = self.client.get("/empty/", inertia=False)
        assert response.inertia.data["encryptHistory"] is False

        with override_settings(
            INERTIA={"LAYOUT": "layout.html", "ENCRYPT_HISTORY": True}
        ):
            response = self.client.get("/empty/", inertia=False)
            assert response.inertia.data["encryptHistory"] is True

    def test_encrypt_history(self):
        response = self.client.get("/encrypt-history/", inertia=False)
        assert response.inertia.data["encryptHistory"] is True

        with override_settings(
            INERTIA={"LAYOUT": "layout.html", "ENCRYPT_HISTORY": True}
        ):
            response = self.client.get("/no-encrypt-history/", inertia=False)
            assert response.inertia.data["encryptHistory"] is False

    def test_class_based_view_encrypts_history(self):
        response = self.client.get("/encrypted-view/", inertia=False)
        assert response.inertia.data["encryptHistory"] is True

    def test_clear_history(self):
        response = self.client.get("/clear-history/", inertia=False)
        assert response.inertia.data["clearHistory"] is True

    def test_clear_history_redirect(self):
        response = self.client.get(
            "/clear-history-redirect/", follow=True, inertia=False
        )
        self.assertRedirects(response, "/empty/")
        assert response.inertia.data["clearHistory"] is True

    def test_raises_type_error(self):
        with self.assertRaisesMessage(
            TypeError, "Expected bool for encrypt_history, got str"
        ):
            self.client.get("/encrypt-history-type-error/", inertia=False)
