from __future__ import annotations

import json
from unittest.mock import Mock
from unittest.mock import patch

from requests.exceptions import RequestException

from dj_inertiajs.test import InertiaTestCase
from dj_inertiajs.test import inertia_div
from dj_inertiajs.test import inertia_page

from .utils import override_app_settings


@override_app_settings(SSR_ENABLED=True, SSR_URL="ssr-url", VERSION="1.0")
class SSRTestCase(InertiaTestCase):
    @patch("dj_inertiajs.http.requests")
    def test_it_returns_ssr_calls(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = {
            "body": "<div>Body Works</div>",
            "head": "<title>Head works</title>",
        }

        mock_request.post.return_value = mock_response

        response = self.client.get("/props/")

        mock_request.post.assert_called_once_with(
            "ssr-url/render",
            data=json.dumps(
                inertia_page("props", props={"name": "Brandon", "sport": "Hockey"})
            ),
            headers={"Content-Type": "application/json"},
        )
        self.assertTemplateUsed("inertia_ssr.html")
        self.assertContains(response, "<div>Body Works</div>")
        self.assertContains(response, "head--<title>Head works</title>--head")

    @patch("dj_inertiajs.http.requests")
    def test_it_returns_ssr_calls_with_template_data(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = {
            "body": "<div>Body Works</div>",
            "head": "<title>Head works</title>",
        }

        mock_request.post.return_value = mock_response

        response = self.client.get("/template_data/")

        self.assertTemplateUsed("inertia_ssr.html")
        self.assertContains(response, "<div>Body Works</div>")
        self.assertContains(response, "head--<title>Head works</title>--head")
        self.assertContains(response, "Brian, Basketball")

    @patch("dj_inertiajs.http.requests")
    def test_it_uses_inertia_if_inertia_requests_are_made(self, mock_requests):
        response = self.inertia.get("/props/")

        mock_requests.post.assert_not_called()
        self.assertJSONResponse(
            response,
            inertia_page("props", props={"name": "Brandon", "sport": "Hockey"}),
        )

    @patch("dj_inertiajs.http.requests")
    def test_it_fallsback_on_failure(self, mock_requests):
        def uh_oh(*args, **kwargs):
            raise RequestException()

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = uh_oh
        mock_requests.post.return_value = mock_response

        response = self.client.get("/props/")
        self.assertContains(
            response, inertia_div("props", props={"name": "Brandon", "sport": "Hockey"})
        )
