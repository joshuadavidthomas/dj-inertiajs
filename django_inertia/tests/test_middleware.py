from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.test import AsyncClient, RequestFactory, TestCase

from django_inertia import InertiaResponse
from django_inertia.tests.utils import ProtocolTestCase


class AsyncMiddlewareTestCase(TestCase):
    async def test_protocol_handling_under_asgi(self):
        client = AsyncClient()

        response = await client.put("/redirect/", headers={"X-Inertia": "true"})
        self.assertEqual(response.status_code, 303)

        response = await client.get(
            "/test/", headers={"X-Inertia": "true", "X-Inertia-Version": "stale"}
        )
        self.assertEqual(response.status_code, 409)


class MiddlewareTestCase(ProtocolTestCase):
    def test_anything(self):
        response = self.client.get("/test/")

        self.assertEqual(response.status_code, 200)

    def test_stale_versions_are_refreshed(self):
        response = self.inertia.get(
            "/empty/",
            HTTP_X_INERTIA_VERSION="some-nonsense",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.headers["X-Inertia-Location"], "http://testserver/empty/"
        )

    def test_redirect_status(self):
        response = self.inertia.post("/redirect/")
        self.assertEqual(response.status_code, 302)

        for http_method in ["put", "patch", "delete"]:
            response = getattr(self.inertia, http_method)("/redirect/")

            self.assertEqual(response.status_code, 303)

    def test_a_request_not_from_inertia_is_ignored(self):
        response = self.client.get(
            "/empty/",
            HTTP_X_INERTIA_VERSION="some-nonsense",
        )

        self.assertEqual(response.status_code, 200)

    def test_external_redirect_status(self):
        response = self.inertia.post("/external-redirect/")
        self.assertEqual(response.status_code, 409)
        self.assertIn("X-Inertia-Location", response.headers)
        self.assertEqual("http://foobar.com/", response.headers["X-Inertia-Location"])


class RequestDetailsTestCase(ProtocolTestCase):
    def test_request_inertia_describes_the_request(self):
        response = self.client.get("/request-details/")
        self.assertEqual(
            response.inertia.props,
            {"inertia": False, "partial_data": None, "is_partial": False},
        )

        response = self.inertia.get(
            "/request-details/",
            HTTP_X_INERTIA_PARTIAL_COMPONENT="OtherComponent",
            HTTP_X_INERTIA_PARTIAL_DATA="stats, plans",
        )
        self.assertEqual(
            response.inertia.props,
            {"inertia": True, "partial_data": ["stats", "plans"], "is_partial": False},
        )

    def test_responses_work_without_the_middleware(self):
        request = RequestFactory().get("/", HTTP_X_INERTIA="true")
        request.session = SessionStore()

        response = InertiaResponse(request, "TestComponent", {"name": "Brandon"})
        response.render()

        self.assertEqual(response.inertia.props, {"name": "Brandon"})
        self.assertFalse(request.inertia.partial_except)
