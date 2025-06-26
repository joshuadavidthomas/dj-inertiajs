from __future__ import annotations

import logging
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping
from enum import Enum
from http import HTTPStatus
from typing import Any

from asgiref.sync import iscoroutinefunction
from asgiref.sync import markcoroutinefunction
from django.contrib.messages.storage import default_storage
from django.http import HttpRequest
from django.http import HttpResponseBase
from django.middleware.csrf import get_token
from django.utils.functional import cached_property
from django.utils.module_loading import import_string

from ._http import HTTPMethod
from .conf import app_settings
from .helpers import deep_transform_callables
from .views import location

logger = logging.getLogger(__name__)


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
        request.inertia = InertiaDetails(request)

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

        if not request.inertia:
            return response

        response.status_code = self.get_inertia_status_code(request, response)

        return response

    def get_inertia_status_code(
        self, request: HttpRequest, response: HttpResponseBase
    ) -> int:
        if response.status_code not in [HTTPStatus.MOVED_PERMANENTLY, HTTPStatus.FOUND]:
            return response.status_code

        if request.method not in [HTTPMethod.DELETE, HTTPMethod.PATCH, HTTPMethod.PUT]:
            return response.status_code

        return HTTPStatus.SEE_OTHER

    def force_refresh(self, request: HttpRequest) -> HttpResponseBase:
        message_storage = default_storage(request)
        message_storage.used = False
        return location(request.build_absolute_uri())


class InertiaDetails:
    def __init__(self, request: HttpRequest) -> None:
        self.request = request

    def __bool__(self) -> bool:
        return self.request.headers.get(InertiaHeader.INERTIA) is not None

    def is_partial_render(self, component: str) -> bool:
        return bool(self.partial_keys) and self.partial_component == component

    @cached_property
    def shared_props(self) -> dict[str, Any]:
        props = {}

        for path in app_settings.SHARED_PROPS:
            try:
                shared_prop = import_string(path)

                if callable(shared_prop):
                    result = shared_prop(self.request)
                elif isinstance(shared_prop, Mapping):
                    result = shared_prop
                else:
                    logger.error(
                        "Shared prop '%s' must be a callable or a Mapping, got %s",
                        path,
                        type(shared_prop).__name__,
                    )
                    continue

                if not isinstance(result, Mapping):
                    logger.error(
                        "Shared prop '%s' returned %s instead of a Mapping",
                        path,
                        type(result).__name__,
                    )
                    continue

                props.update(result)

            except ImportError:
                logger.error("Could not import shared prop '%s'", path, exc_info=True)
            except Exception:
                logger.error("Error in shared prop '%s'", path, exc_info=True)

        return props

    def props(self, props: dict[str, Any] | None = None) -> dict[str, Any]:
        props = props or {}
        merged_props = {**self.shared_props, **props}

        if self.partial_keys:
            filtered_props = {
                k: v for k, v in merged_props.items() if k in self.partial_keys
            }
        else:
            filtered_props = merged_props

        return deep_transform_callables(filtered_props)

    @cached_property
    def partial_component(self) -> str | None:
        return self.request.headers.get(InertiaHeader.PARTIAL_COMPONENT)

    @cached_property
    def partial_keys(self) -> list[str]:
        data = self.request.headers.get(InertiaHeader.PARTIAL_DATA)
        return data.split(",") if data else []

    @cached_property
    def reset_keys(self) -> list[str]:
        data = self.request.headers.get("X-Inertia-Reset", "")
        return data.split(",") if data else []

    @cached_property
    def version(self) -> str:
        return self.request.headers.get(InertiaHeader.VERSION, app_settings.VERSION)
