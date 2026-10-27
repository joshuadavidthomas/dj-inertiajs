import json

from django.conf import settings
from django.test import override_settings

from dj_inertiajs.test import InertiaClient
from tests.utils import ProtocolTestCase, inertia_page

# ---------------------------------------------------------------------------
# preserveFragment
# ---------------------------------------------------------------------------


class PreserveFragmentTestCase(ProtocolTestCase):
    """Tests for server-side preserveFragment support introduced in Inertia v3.

    When a view returns redirect(..., preserve_fragment=True), the Inertia
    page that follows includes preserveFragment: true in the page object.  The client uses this to retain the original URL fragment
    across the redirect.
    """

    def test_preserve_fragment_is_included_after_the_redirect(self):
        self.assertJSONResponse(
            self.client.get("/preserve-fragment-redirect/", follow=True),
            inertia_page("empty", preserve_fragment=True),
        )

    def test_preserve_fragment_is_absent_by_default(self):
        """preserveFragment is not in the page object when not requested."""
        response = self.client.get("/empty/")
        page = response.json()

        self.assertNotIn("preserveFragment", page)

    def test_preserve_fragment_persists_across_a_redirect(self):
        """The flag survives in the session for the page that follows the
        redirect, including for a plain (non-Inertia) request."""
        response = self.client.get(
            "/preserve-fragment-redirect/", follow=True, inertia=False
        )

        self.assertTrue(response.inertia.data.get("preserveFragment"))

    def test_preserve_fragment_is_consumed_after_one_response(self):
        """The session flag is cleared after the first response that reads it,
        so a second request does not see preserveFragment: true."""
        self.client.get("/preserve-fragment-redirect/", follow=True)
        response = self.client.get("/empty/")
        page = response.json()

        self.assertNotIn("preserveFragment", page)


# ---------------------------------------------------------------------------
# preserveErrors via partial reload filtering
# ---------------------------------------------------------------------------


@override_settings(
    INERTIA={
        "LAYOUT": "layout.html",
        "SHARED_PROPS": ["tests.testapp.views.shared_errors"],
    }
)
class PreserveErrorsTestCase(ProtocolTestCase):
    """Tests that verify preserveErrors behaviour for partial reloads.

    The Django adapter already filters shared props through the partial reload
    mechanism.  When the client sends a partial reload that does not include
    the errors key, the shared errors prop is excluded from the response.
    This allows the client-side preserveErrors option to work correctly:
    the server will not overwrite the client's existing errors with an empty
    dict unless the client explicitly requests the errors key.
    """

    def test_shared_errors_are_included_on_full_render(self):
        """Shared errors are present on a full (non-partial) Inertia render."""
        response = self.client.get("/preserve-errors/")
        page = response.json()

        self.assertIn("errors", page["props"])
        self.assertEqual(page["props"]["errors"], {"email": "required"})

    def test_shared_errors_are_excluded_from_partial_reload_by_default(self):
        """When errors is not in X-Inertia-Partial-Data the shared errors
        prop is omitted from the partial reload response, ensuring the client's
        preserveErrors option can retain its existing errors."""
        response = self.client.get(
            "/preserve-errors/",
            headers={
                "x-inertia-partial-data": "name",
                "x-inertia-partial-component": "TestComponent",
            },
        )
        page = response.json()

        self.assertIn("name", page["props"])
        self.assertNotIn("errors", page["props"])

    def test_shared_errors_are_included_when_explicitly_requested(self):
        """A partial reload that includes errors in X-Inertia-Partial-Data
        does receive the errors prop."""
        response = self.client.get(
            "/preserve-errors/",
            headers={
                "x-inertia-partial-data": "errors",
                "x-inertia-partial-component": "TestComponent",
            },
        )
        page = response.json()

        self.assertIn("errors", page["props"])


# ---------------------------------------------------------------------------
# Infinite scroll merge intent
# ---------------------------------------------------------------------------


class InfiniteScrollMergeIntentTestCase(ProtocolTestCase):
    """Tests for the X-Inertia-Infinite-Scroll-Merge-Intent request header.

    When the client sends this header with the value prepend during a partial
    reload for merge-able props, the response should include a prependProps
    list so the client knows to prepend the new data rather than append it.
    """

    def test_merge_props_are_in_merge_props_without_intent_header(self):
        """Without X-Inertia-Infinite-Scroll-Merge-Intent the merge-able
        prop is listed in mergeProps as normal."""
        self.assertJSONResponse(
            self.client.get("/infinite-scroll/"),
            inertia_page(
                "infinite-scroll",
                props={"name": "Brandon", "items": ["item1", "item2"]},
                merge_props=["items"],
            ),
        )

    def test_append_intent_does_not_produce_prepend_props(self):
        """An explicit append intent header does not produce prependProps."""
        response = self.client.get(
            "/infinite-scroll/",
            headers={
                "x-inertia-partial-data": "items",
                "x-inertia-partial-component": "TestComponent",
                "x-inertia-infinite-scroll-merge-intent": "append",
            },
        )
        page = response.json()

        self.assertNotIn("prependProps", page)

    def test_prepend_intent_produces_prepend_props(self):
        """When the merge intent is prepend, prependProps is included in the
        partial reload response with the requested merge-able prop keys."""
        response = self.client.get(
            "/infinite-scroll/",
            headers={
                "x-inertia-partial-data": "items",
                "x-inertia-partial-component": "TestComponent",
                "x-inertia-infinite-scroll-merge-intent": "prepend",
            },
        )
        page = response.json()

        self.assertIn("prependProps", page)
        self.assertIn("items", page["prependProps"])

    def test_prepend_intent_on_non_partial_render_produces_no_prepend_props(self):
        """prependProps is never produced on a full (non-partial) render even
        when the intent header is present, because there is no meaningful
        merge operation on a first load."""
        response = self.client.get(
            "/infinite-scroll/",
            headers={"x-inertia-infinite-scroll-merge-intent": "prepend"},
        )
        page = response.json()

        self.assertNotIn("prependProps", page)

    def test_prepend_intent_excludes_non_merge_props_from_prepend_props(self):
        """Only merge-able props requested in the partial data are included
        in prependProps; regular props are not listed there."""
        response = self.client.get(
            "/infinite-scroll/",
            headers={
                "x-inertia-partial-data": "name,items",
                "x-inertia-partial-component": "TestComponent",
                "x-inertia-infinite-scroll-merge-intent": "prepend",
            },
        )
        page = response.json()

        self.assertIn("prependProps", page)
        self.assertIn("items", page["prependProps"])
        self.assertNotIn("name", page["prependProps"])

    def test_prepend_props_respects_reset_keys(self):
        """A key listed in X-Inertia-Reset is excluded from prependProps."""
        response = self.client.get(
            "/infinite-scroll/",
            headers={
                "x-inertia-partial-data": "items",
                "x-inertia-partial-component": "TestComponent",
                "x-inertia-infinite-scroll-merge-intent": "prepend",
                "x-inertia-reset": "items",
            },
        )
        page = response.json()

        self.assertNotIn("prependProps", page)


# ---------------------------------------------------------------------------
# useHttp CSRF
# ---------------------------------------------------------------------------


class UseHttpCsrfTestCase(ProtocolTestCase):
    """Tests that verify CSRF token availability for useHttp (non-visit XHR).

    useHttp requests do not carry the X-Inertia header, so the cookie must
    come from the Inertia page the app loaded with.
    """

    def test_csrf_token_is_set_for_non_inertia_requests(self):
        """A plain (non-Inertia) request receives a CSRF cookie, enabling
        useHttp requests to include the token."""
        response = self.client.get("/props/", inertia=False)
        self.assertIsNotNone(response.cookies.get("csrftoken"))

    def test_csrf_token_is_set_for_inertia_requests(self):
        """Inertia-flagged requests also receive the CSRF cookie."""
        response = self.client.get("/props/")
        self.assertIsNotNone(response.cookies.get("csrftoken"))

    def test_plain_django_responses_get_no_csrf_cookie(self):
        """Pages that are not Inertia pages keep Django's own CSRF behavior,
        so they stay cacheable."""
        response = self.client.get("/test/", inertia=False)
        self.assertIsNone(response.cookies.get("csrftoken"))
        self.assertIsNone(response.cookies.get("XSRF-TOKEN"))
        self.assertNotIn("Cookie", response.get("Vary", ""))

    def test_non_inertia_response_is_not_modified_by_middleware(self):
        """The middleware does not alter the status or content of a response
        to a plain HTTP request, which is the path taken by useHttp."""
        response = self.client.get("/test/", inertia=False)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("X-Inertia", response.headers)

    def test_non_inertia_4xx_responses_pass_through_unchanged(self):
        """A 422 JSON response returned by a view for a useHttp validation
        error is forwarded to the client without modification."""
        from django.http import JsonResponse

        from dj_inertiajs.middleware import InertiaMiddleware

        class FakeGet:
            def __call__(self, request):
                return JsonResponse({"errors": {"email": "required"}}, status=422)

        middleware = InertiaMiddleware(FakeGet())

        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post(
            "/api/submit/",
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        response = middleware(request)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            json.loads(response.content), {"errors": {"email": "required"}}
        )

    def test_non_inertia_redirect_passes_through_unchanged(self):
        """A redirect response from a view that handles a useHttp request is
        forwarded as-is; the middleware does not change its status code."""
        from django.http import HttpResponseRedirect

        from dj_inertiajs.middleware import InertiaMiddleware

        class FakeGet:
            def __call__(self, request):
                return HttpResponseRedirect("/login/")

        middleware = InertiaMiddleware(FakeGet())

        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post(
            "/api/submit/",
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        response = middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/login/")


class XsrfTokenTestCase(ProtocolTestCase):
    """The v3 client's default CSRF names, XSRF-TOKEN and X-XSRF-TOKEN, work
    without client configuration."""

    def setUp(self):
        self.csrf_client = InertiaClient(enforce_csrf_checks=True)

    def post(self, token):
        headers = {} if token is None else {"X-XSRF-TOKEN": token}
        return self.csrf_client.post("/v3/post/", headers=headers)

    def xsrf_token(self, response):
        return response.cookies["XSRF-TOKEN"].value

    def test_inertia_page_sets_a_cookie_javascript_can_read(self):
        cookie = self.csrf_client.get("/v3/nested/").cookies["XSRF-TOKEN"]

        self.assertEqual(cookie["httponly"], "")
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(cookie["max-age"], 31449600)

    def test_plain_django_pages_stay_free_of_the_cookie(self):
        self.csrf_client.get("/v3/nested/")
        response = self.csrf_client.get("/test/", inertia=False)

        self.assertNotIn("XSRF-TOKEN", response.cookies)
        self.assertNotIn("Cookie", response.get("Vary", ""))

    def test_post_with_the_xsrf_header_passes_the_csrf_check(self):
        token = self.xsrf_token(self.csrf_client.get("/v3/nested/"))

        self.assertEqual(self.post(token).status_code, 302)

    def test_post_without_a_valid_token_is_rejected(self):
        self.csrf_client.get("/v3/nested/")

        self.assertEqual(self.post(None).status_code, 403)
        self.assertEqual(self.post("x" * 64).status_code, 403)

    @override_settings(CSRF_USE_SESSIONS=True, CSRF_COOKIE_HTTPONLY=True)
    def test_works_when_django_keeps_its_token_out_of_cookies(self):
        response = self.csrf_client.get("/v3/nested/")

        self.assertIsNone(response.cookies.get("csrftoken"))
        self.assertEqual(self.post(self.xsrf_token(response)).status_code, 302)

    def test_rotated_token_reaches_the_cookie_in_either_middleware_order(self):
        csrf = "django.middleware.csrf.CsrfViewMiddleware"
        inertia = "dj_inertiajs.middleware.InertiaMiddleware"
        others = [m for m in settings.MIDDLEWARE if m not in (csrf, inertia)]
        for use_sessions in (False, True):
            for order in ([csrf, inertia], [inertia, csrf]):
                with (
                    self.subTest(use_sessions=use_sessions, order=order),
                    override_settings(
                        MIDDLEWARE=others + order, CSRF_USE_SESSIONS=use_sessions
                    ),
                ):
                    self.csrf_client = InertiaClient(enforce_csrf_checks=True)
                    old = self.xsrf_token(self.csrf_client.get("/v3/nested/"))
                    response = self.csrf_client.get("/csrf-rotate/", inertia=False)
                    new = self.xsrf_token(response)

                    self.assertEqual(self.post(old).status_code, 403)
                    self.assertEqual(self.post(new).status_code, 302)
