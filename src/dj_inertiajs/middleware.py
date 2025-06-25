from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from enum import Enum
from http import HTTPMethod
from http import HTTPStatus

from asgiref.sync import iscoroutinefunction
from asgiref.sync import markcoroutinefunction
from django.contrib import messages
from django.http import HttpRequest
from django.http import HttpResponseBase
from django.middleware.csrf import get_token
from django.utils.functional import cached_property

from .conf import app_settings
from .helpers import deep_transform_callables
from .http import location


class InertiaHeader(str, Enum):
    INERTIA = "X-Inertia"
    LOCATION = "X-Inertia-Location"
    PARTIAL_COMPONENT = "X-Inertia-Partial-Component"
    PARTIAL_DATA = "X-Inertia-Partial-Data"
    VERSION = "X-Inertia-Version"


class InertiaMiddleware:
    sync_capable = True
    async_capable = True

    def __init__(
        self,
        get_response: (
            Callable[[HttpRequest], HttpResponseBase]
            | Callable[[HttpRequest], Awaitable[HttpResponseBase]]
        ),
    ) -> None:
        self.get_response = get_response
        self.async_mode = iscoroutinefunction(self.get_response)

        if self.async_mode:
            # Mark the class as async-capable, but do the actual switch
            # inside __call__ to avoid swapping out dunder methods
            markcoroutinefunction(self)

    def __call__(
        self, request: HttpRequest
    ) -> HttpResponseBase | Awaitable[HttpResponseBase]:
        # Add InertiaDetails to all requests
        request.inertia = InertiaDetails(request)

        # Early version check for GET requests
        if (
            request.inertia
            and request.method == HTTPMethod.GET
            and request.inertia.version != app_settings.VERSION
        ):
            return self.force_refresh(request)

        if self.async_mode:
            return self.__acall__(request)

        response = self.get_response(request)
        return self.process_inertia_response(request, response)

    async def __acall__(self, request: HttpRequest) -> HttpResponseBase:
        response = await self.get_response(request)
        return self.process_inertia_response(request, response)

    def process_inertia_response(
        self, request: HttpRequest, response: HttpResponseBase
    ) -> HttpResponseBase:
        # Inertia requests don't ever render templates, so they skip the typical Django
        # CSRF path. We'll manually add a CSRF token for every request here.
        get_token(request)

        # Only process further for Inertia requests
        if not request.inertia:
            return response

        # Handle redirect status codes for PUT/PATCH/DELETE
        if response.status_code in [
            HTTPStatus.MOVED_PERMANENTLY,
            HTTPStatus.FOUND,
        ] and request.method in [HTTPMethod.PUT, HTTPMethod.PATCH, HTTPMethod.DELETE]:
            response.status_code = HTTPStatus.SEE_OTHER

        return response

    def force_refresh(self, request: HttpRequest) -> HttpResponseBase:
        # Preserve messages across the redirect
        messages.get_messages(request).used = False
        return location(request.build_absolute_uri())


class InertiaDetails:
    """
    Encapsulates Inertia-specific request details and provides
    a clean API for accessing Inertia functionality.
    """

    def __init__(self, request: HttpRequest) -> None:
        self.request = request
        self._shared_props = {}

    def __bool__(self) -> bool:
        """Check if this is an Inertia request."""
        return InertiaHeader.INERTIA in self.request.headers

    def is_partial_render(self, component: str) -> bool:
        """Check if this is a partial render for the given component."""
        return bool(self.partial_keys) and self.partial_component == component

    def share(self, **props) -> None:
        """Share props across all components."""
        self._shared_props.update(props)

    def all(self) -> dict:
        """Get all shared props (for compatibility with current share system)."""
        return self._shared_props

    def props(self, props: dict | None = None) -> dict:
        """
        Get the final props, handling shared props and partial reloads.
        This is called by response classes to build the final prop set.
        """
        props = props or {}
        merged_props = {**self._shared_props, **props}

        # Handle partial reloads - only include requested props
        if self.partial_keys:
            filtered_props = {
                k: v for k, v in merged_props.items() if k in self.partial_keys
            }
        else:
            filtered_props = merged_props

        # Resolve any callables
        return deep_transform_callables(filtered_props)

    @cached_property
    def version(self) -> str:
        """Get the Inertia version from the request."""
        return self.request.headers.get(InertiaHeader.VERSION, app_settings.VERSION)

    @cached_property
    def partial_component(self) -> str | None:
        """Get the component being partially rendered."""
        return self.request.headers.get(InertiaHeader.PARTIAL_COMPONENT)

    @cached_property
    def partial_keys(self) -> list[str]:
        """Get the list of props requested for partial reload."""
        data = self.request.headers.get(InertiaHeader.PARTIAL_DATA)
        return data.split(",") if data else []

    @cached_property
    def reset_keys(self) -> list[str]:
        """Get the list of props to reset during partial reload."""
        data = self.request.headers.get("X-Inertia-Reset", "")
        return data.split(",") if data else []
