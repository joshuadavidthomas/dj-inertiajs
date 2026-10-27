from typing import Any, Callable

from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.conf import settings as django_settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils.cache import patch_vary_headers

from .conf import settings
from .request import InertiaDetails
from .response import InertiaLocation, InertiaResponse
from .session import preserve_fragment

# The Inertia v3 client reads the CSRF token from this cookie and sends it in
# an X-XSRF-TOKEN header, the names Laravel uses.
XSRF_COOKIE_NAME = "XSRF-TOKEN"
XSRF_HEADER = "HTTP_X_XSRF_TOKEN"


class InertiaMiddleware:
    """Central middleware for all Inertia.js protocol concerns.

    Responsibilities:
    - Convert PUT/PATCH/DELETE redirects to 303 so the subsequent request
      is always treated as a GET by the browser.
    - Detect asset version mismatches and force a full-page refresh.
    - Give the client the CSRF token under its default names: an
      ``XSRF-TOKEN`` cookie, read back from an ``X-XSRF-TOKEN`` header.

    It also attaches ``request.inertia``, an ``InertiaDetails``, before the
    view runs.

    Requests that are not Inertia visits, such as those from ``useHttp``,
    only get the CSRF handling and ``Vary: X-Inertia``. Their views return
    their own responses, such as 422 JSON for validation errors.
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response: Callable[[HttpRequest], Any]) -> None:
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)

    def __call__(self, request: HttpRequest) -> Any:
        request.inertia = InertiaDetails(request)  # type: ignore[attr-defined]
        if XSRF_HEADER in request.META:
            # CsrfViewMiddleware checks the token in its process_view(), which
            # runs after every middleware's request phase.
            request.META.setdefault(
                django_settings.CSRF_HEADER_NAME, request.META[XSRF_HEADER]
            )
        if iscoroutinefunction(self):
            return self.__acall__(request)
        return self.process_response(request, self.get_response(request))

    async def __acall__(self, request: HttpRequest) -> HttpResponse:
        return self.process_response(request, await self.get_response(request))

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        details: InertiaDetails = request.inertia  # type: ignore[attr-defined]
        if isinstance(response, InertiaLocation) and not details:
            # Only the Inertia client understands the 409; a browser loading
            # the URL directly gets an ordinary redirect, which keeps the
            # view's cookies and headers. Setting Location after construction
            # allows any scheme, as the 409 does, such as mailto: or an app's.
            redirect = HttpResponseRedirect("/")
            for header, value in response.items():
                if header != "X-Inertia-Location":
                    redirect[header] = value
            redirect["Location"] = response.url
            redirect.cookies = response.cookies
            response = redirect

        patch_vary_headers(response, ("X-Inertia",))
        self.set_xsrf_cookie(request, response)

        if getattr(response, "preserve_fragment", False):
            preserve_fragment(request)

        if not details:
            return response

        if request.method == "GET" and details.version not in (None, settings.VERSION):
            return self.force_refresh(request)

        if self.redirect_has_fragment(response) and not details.prefetch:
            return self.inertia_redirect(response)

        if self.is_non_post_redirect(request, response):
            response.status_code = 303

        return response

    def set_xsrf_cookie(self, request: HttpRequest, response: HttpResponse) -> None:
        # The cookie holds Django's CSRF secret, as Django's own cookie does.
        # Inertia pages always send it, to set and renew it; other responses
        # only replace a stale one, after rotate_token() at login.
        secret = request.META.get("CSRF_COOKIE")
        if secret is None:
            return
        current = request.COOKIES.get(XSRF_COOKIE_NAME)
        if not isinstance(response, InertiaResponse) and current in (None, secret):
            return
        response.set_cookie(
            XSRF_COOKIE_NAME,
            secret,
            max_age=django_settings.CSRF_COOKIE_AGE,
            domain=django_settings.CSRF_COOKIE_DOMAIN,
            path=django_settings.CSRF_COOKIE_PATH,
            secure=django_settings.CSRF_COOKIE_SECURE,
            samesite=django_settings.CSRF_COOKIE_SAMESITE,
        )
        patch_vary_headers(response, ("Cookie",))

    def is_non_post_redirect(
        self, request: HttpRequest, response: HttpResponse
    ) -> bool:
        return self.is_redirect_request(response) and request.method in [
            "PUT",
            "PATCH",
            "DELETE",
        ]

    def is_redirect_request(self, response: HttpResponse) -> bool:
        return response.status_code in [301, 302]

    def redirect_has_fragment(self, response: HttpResponse) -> bool:
        return self.is_redirect_request(response) and "#" in response.headers.get(
            "Location", ""
        )

    def inertia_redirect(self, response: HttpResponse) -> HttpResponse:
        return HttpResponse(
            "",
            status=409,
            headers={"X-Inertia-Redirect": response.headers["Location"]},
        )

    def force_refresh(self, request: HttpRequest) -> HttpResponse:
        # If the storage middleware is not defined, get_messages returns an empty list
        storage = messages.get_messages(request)
        if not isinstance(storage, list):
            storage.used = False
        response = InertiaLocation(request.build_absolute_uri())
        # The client compares it with its own to tell a version change from
        # an ordinary location visit, and skips reloading background requests.
        response["X-Inertia-Version"] = settings.VERSION
        patch_vary_headers(response, ("X-Inertia",))
        return response
