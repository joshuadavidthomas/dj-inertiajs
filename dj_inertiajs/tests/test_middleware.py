from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.test import AsyncClient, RequestFactory, TestCase
from django.utils.cache import has_vary_header

from dj_inertiajs import InertiaResponse, redirect
from dj_inertiajs.middleware import InertiaMiddleware
from dj_inertiajs.tests.utils import ProtocolTestCase


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
        response = self.client.get("/test/", inertia=False)

        self.assertEqual(response.status_code, 200)

    def test_stale_versions_are_refreshed(self):
        response = self.client.get(
            "/empty/", headers={"x-inertia-version": "some-nonsense"}
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.headers["X-Inertia-Location"], "http://testserver/empty/"
        )
        self.assertEqual(response.headers["X-Inertia-Version"], "1.0")

    def test_responses_vary_on_x_inertia(self):
        plain = self.client.get("/test/", inertia=False)
        self.assertTrue(has_vary_header(plain, "X-Inertia"))

        page = self.client.get("/empty/")
        self.assertEqual(page["X-Inertia"], "true")
        self.assertTrue(has_vary_header(page, "X-Inertia"))

        stale = self.client.get("/empty/", headers={"x-inertia-version": "stale"})
        self.assertTrue(has_vary_header(stale, "X-Inertia"))

    def test_messages_survive_a_version_refresh(self):
        response = self.client.get("/messages/", headers={"x-inertia-version": "stale"})
        self.assertEqual(response.status_code, 409)

        response = self.client.get("/no-messages/")
        self.assertEqual(
            response.inertia.data["flash"],
            {"messages": [{"level": "success", "message": "Profile saved!"}]},
        )

    def test_permanent_redirects_after_put_become_303(self):
        middleware = InertiaMiddleware(
            lambda request: HttpResponsePermanentRedirect("/players")
        )
        response = middleware(RequestFactory().put("/players", HTTP_X_INERTIA="true"))
        self.assertEqual(response.status_code, 303)

    def test_prefetch_follows_a_fragment_redirect_itself(self):
        middleware = InertiaMiddleware(
            lambda request: HttpResponseRedirect("/players#goalies")
        )
        request = RequestFactory().get(
            "/players", HTTP_X_INERTIA="true", HTTP_PURPOSE="prefetch"
        )
        response = middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/players#goalies")

    def test_redirect_shortcut_defaults(self):
        response = redirect("/players")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(response.preserve_fragment)

    def test_redirect_status(self):
        response = self.client.post("/redirect/")
        self.assertEqual(response.status_code, 302)

        for http_method in ["put", "patch", "delete"]:
            response = getattr(self.client, http_method)("/redirect/")

            self.assertEqual(response.status_code, 303)

    def test_a_request_not_from_inertia_is_ignored(self):
        response = self.client.get(
            "/empty/", headers={"x-inertia-version": "some-nonsense"}, inertia=False
        )

        self.assertEqual(response.status_code, 200)

    def test_external_redirect_status(self):
        response = self.client.post("/external-redirect/")
        self.assertEqual(response.status_code, 409)
        self.assertIn("X-Inertia-Location", response.headers)
        self.assertEqual("http://foobar.com/", response.headers["X-Inertia-Location"])

    def test_external_redirect_is_a_plain_redirect_on_a_full_page_load(self):
        response = self.client.post("/external-redirect/", inertia=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "http://foobar.com/")

    def test_full_page_redirect_keeps_the_views_cookies_headers_and_scheme(self):
        response = self.client.get("/app-location/", inertia=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "myapp://open")
        self.assertEqual(response.headers["X-Custom"], "kept")
        self.assertEqual(response.cookies["viewcookie"].value, "1")
        self.assertNotIn("X-Inertia-Location", response.headers)


class RequestDetailsTestCase(ProtocolTestCase):
    def test_request_inertia_describes_the_request(self):
        response = self.client.get("/request-details/", inertia=False)
        self.assertEqual(
            response.inertia.props,
            {"inertia": False, "partial_data": None, "is_partial": False},
        )

        response = self.client.get(
            "/request-details/",
            headers={
                "x-inertia-partial-component": "OtherComponent",
                "x-inertia-partial-data": "stats, plans",
            },
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
