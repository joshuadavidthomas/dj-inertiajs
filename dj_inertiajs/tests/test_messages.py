from dj_inertiajs.tests.utils import ProtocolTestCase


class FlashMessagesTestCase(ProtocolTestCase):
    def test_messages_are_included_in_top_level_flash_data(self):
        response = self.client.get("/messages/")

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
        response = self.client.get("/no-messages/")

        self.assertNotIn("flash", response.inertia.data)

    def test_messages_are_consumed_after_render(self):
        response = self.client.get("/messages/")
        self.assertIn("flash", response.inertia.data)

        response = self.client.get("/no-messages/")
        self.assertNotIn("flash", response.inertia.data)

    def test_messages_are_included_on_partial_requests(self):
        response = self.client.get(
            "/messages/",
            headers={
                "x-inertia-partial-data": "missing",
                "x-inertia-partial-component": "TestComponent",
            },
        )

        self.assertEqual(
            response.inertia.data["flash"],
            {
                "messages": [
                    {"level": "success", "message": "Profile saved!"},
                ],
            },
        )
