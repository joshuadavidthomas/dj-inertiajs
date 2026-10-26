from typing import Any, Callable

from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import get_token
from django.utils.cache import patch_vary_headers

from .conf import settings
from .request import InertiaDetails
from .response import location


class InertiaMiddleware:
    """Central middleware for all Inertia.js protocol concerns.

    Responsibilities:
    - Ensure a CSRF cookie is always set, including for non-Inertia (useHttp)
      requests that do not go through Django's normal template rendering path.
    - Convert PUT/PATCH/DELETE redirects to 303 so the subsequent request
      is always treated as a GET by the browser.
    - Detect asset version mismatches and force a full-page refresh.

    It also attaches ``request.inertia``, an ``InertiaDetails``, before the
    view runs.

    Non-Inertia requests (e.g. those made via the useHttp hook in Inertia v3)
    pass through this middleware without modification beyond CSRF cookie
    injection.  It is the responsibility of the individual view to return an
    appropriate response (e.g. 422 JSON) for useHttp validation errors.
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response: Callable[[HttpRequest], Any]) -> None:
        self.get_response = get_response
        if iscoroutinefunction(get_response):
            markcoroutinefunction(self)

    def __call__(self, request: HttpRequest) -> Any:
        request.inertia = InertiaDetails(request)  # type: ignore[attr-defined]
        if iscoroutinefunction(self):
            return self.__acall__(request)
        return self.process_response(request, self.get_response(request))

    async def __acall__(self, request: HttpRequest) -> HttpResponse:
        return self.process_response(request, await self.get_response(request))

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        patch_vary_headers(response, ("X-Inertia",))

        # Inertia requests bypass Django's normal template rendering and
        # therefore never hit the standard CSRF middleware path that attaches
        # the cookie.  Set the token explicitly here so it is available for
        # both Inertia page visits and non-visit XHR (useHttp) requests.
        get_token(request)

        details: InertiaDetails = request.inertia  # type: ignore[attr-defined]
        if not details:
            return response

        if request.method == "GET" and details.version not in (None, settings.VERSION):
            return self.force_refresh(request)

        if self.redirect_has_fragment(response) and not details.prefetch:
            return self.inertia_redirect(response)

        if self.is_non_post_redirect(request, response):
            response.status_code = 303

        return response

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
        response = location(request.build_absolute_uri())
        patch_vary_headers(response, ("X-Inertia",))
        return response
