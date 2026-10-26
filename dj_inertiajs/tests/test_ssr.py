import json
from unittest.mock import Mock, patch

from django.test import override_settings

from dj_inertiajs.tests.utils import ProtocolTestCase, inertia_div, inertia_page


@override_settings(
    INERTIA={
        "LAYOUT": "layout.html",
        "VERSION": "1.0",
        "SSR": {"ENABLED": True, "URL": "ssr-url"},
    },
)
class SSRTestCase(ProtocolTestCase):
    @patch("dj_inertiajs.response.requests")
    def test_it_returns_ssr_calls(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = {
            "body": "<div>Body Works</div>",
            "head": "<title>Head works</title>",
        }

        mock_request.post.return_value = mock_response

        response = self.client.get("/props/", inertia=False)

        mock_request.post.assert_called_once_with(
            "ssr-url/render",
            data=json.dumps(
                inertia_page("props", props={"name": "Brandon", "sport": "Hockey"})
            ),
            headers={"Content-Type": "application/json"},
        )
        self.assertTemplateUsed(response, "layout.html")
        self.assertContains(response, "<div>Body Works</div>")
        self.assertContains(response, "head--<title>Head works</title>--head")

    @patch("dj_inertiajs.response.requests")
    def test_it_returns_ssr_calls_with_template_data(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = {
            "body": "<div>Body Works</div>",
            "head": "<title>Head works</title>",
        }

        mock_request.post.return_value = mock_response

        response = self.client.get("/template_data/", inertia=False)

        self.assertTemplateUsed(response, "layout.html")
        self.assertContains(response, "<div>Body Works</div>")
        self.assertContains(response, "head--<title>Head works</title>--head")
        self.assertContains(response, "Brian, Basketball")

    @patch("dj_inertiajs.response.requests")
    def test_it_uses_inertia_if_inertia_requests_are_made(self, mock_requests):
        response = self.client.get("/props/")

        mock_requests.post.assert_not_called()
        self.assertJSONResponse(
            response,
            inertia_page("props", props={"name": "Brandon", "sport": "Hockey"}),
        )

    @patch("dj_inertiajs.response.requests")
    def test_it_fallsback_on_failure(self, mock_requests):
        def uh_oh(*args, **kwargs):
            raise ValueError()  # SSR errors are logged and fall back to client-side rendering

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = uh_oh
        mock_requests.post.return_value = mock_response

        response = self.client.get("/props/", inertia=False)
        self.assertContains(
            response, inertia_div("props", props={"name": "Brandon", "sport": "Hockey"})
        )

    @patch("dj_inertiajs.response.logger")
    @patch("dj_inertiajs.response.requests")
    def test_it_logs_exception_on_ssr_failure(self, mock_requests, mock_logger):
        error = ValueError("SSR rendering failed")

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = error
        mock_requests.post.return_value = mock_response

        self.client.get("/props/", inertia=False)

        mock_logger.exception.assert_called_once_with("SSR render request failed")
