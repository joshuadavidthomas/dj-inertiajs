from django_inertia.tests.utils import ProtocolTestCase


class FlashMessagesTestCase(ProtocolTestCase):
    def test_messages_are_included_in_top_level_flash_data(self):
        response = self.inertia.get("/messages/")

        self.assertEqual(
            response.inertia.data["flash"],
            {
                "messages": [
                    {"level": "success", "message": "Profile saved!"},
                ],
            },
        )
        self.assertNotIn("messages", response.inertia.props)

    def test_flash_data_is_omitted_when_there_are_no_messages(self):
        response = self.inertia.get("/no-messages/")

        self.assertNotIn("flash", response.inertia.data)

    def test_messages_are_consumed_after_render(self):
        response = self.inertia.get("/messages/")
        self.assertIn("flash", response.inertia.data)

        response = self.inertia.get("/no-messages/")
        self.assertNotIn("flash", response.inertia.data)

    def test_messages_are_included_on_partial_requests(self):
        response = self.inertia.get(
            "/messages/",
            HTTP_X_INERTIA_PARTIAL_DATA="missing",
            HTTP_X_INERTIA_PARTIAL_COMPONENT="TestComponent",
        )

        self.assertEqual(
            response.inertia.data["flash"],
            {
                "messages": [
                    {"level": "success", "message": "Profile saved!"},
                ],
            },
        )
