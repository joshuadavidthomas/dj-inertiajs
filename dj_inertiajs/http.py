import logging
from dataclasses import dataclass
from functools import cached_property, wraps
from http import HTTPStatus
from json import JSONEncoder
from json import dumps as json_encode
from json import loads as json_decode
from typing import Any, Callable

from asgiref.sync import iscoroutinefunction
from django.contrib.messages import get_messages
from django.core.exceptions import ImproperlyConfigured
from django.forms import BaseForm
from django.http import HttpRequest, HttpResponse
from django.template.response import ContentNotRenderedError, SimpleTemplateResponse
from django.utils.cache import patch_vary_headers

from .props import Prop
from .settings import settings

try:
    # Must be early-imported so tests can patch it with
    # a mock module
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

INERTIA_SESSION_CLEAR_HISTORY = "_inertia_clear_history"
INERTIA_SESSION_PRESERVE_FRAGMENT = "_inertia_preserve_fragment"
INERTIA_SESSION_ERRORS = "_inertia_errors"

SKIP_PROP = object()


class InertiaDetails:
    """Inertia's view of one request, available as ``request.inertia``.

    ``InertiaMiddleware`` attaches it, the way ``SessionMiddleware`` attaches
    ``request.session``. It is truthy when the Inertia client made the
    request. Its methods change the page this request renders, or with a
    redirect, the next page.
    """

    def __init__(self, request: HttpRequest) -> None:
        self._request = request
        self.shared: dict[str, Any] = {}

    def __bool__(self) -> bool:
        return "X-Inertia" in self._request.headers

    @property
    def version(self) -> str | None:
        """The asset version the client has, from ``X-Inertia-Version``."""
        return self._request.headers.get("X-Inertia-Version")

    @property
    def partial_component(self) -> str | None:
        """The component a partial reload is for."""
        return self._request.headers.get("X-Inertia-Partial-Component")

    @property
    def partial_data(self) -> list[str] | None:
        """The only props a partial reload asks for, or ``None`` for all."""
        return self._header_list("X-Inertia-Partial-Data")

    @property
    def partial_except(self) -> list[str] | None:
        """The props a partial reload asks to leave out."""
        return self._header_list("X-Inertia-Partial-Except")

    @property
    def reset(self) -> list[str]:
        """Merge props the client asks to replace instead of merge."""
        return self._header_list("X-Inertia-Reset") or []

    @property
    def except_once_props(self) -> list[str]:
        """Once props the client already holds."""
        return self._header_list("X-Inertia-Except-Once-Props") or []

    @property
    def merge_intent(self) -> str:
        """``"append"`` or ``"prepend"``: where infinite scroll adds merged items."""
        return self._request.headers.get(
            "X-Inertia-Infinite-Scroll-Merge-Intent", "append"
        )

    @property
    def prefetch(self) -> bool:
        return self._request.headers.get("Purpose") == "prefetch"

    def is_partial(self, component: str) -> bool:
        """Whether this request is a partial reload of ``component``."""
        return self.partial_component == component

    def share(self, **props: Any) -> None:
        """Add props to the page this request renders, as shared props."""
        self.shared.update(props)

    def clear_history(self) -> None:
        """Clear the client's encrypted history on the next page."""
        self._request.session[INERTIA_SESSION_CLEAR_HISTORY] = True

    def preserve_fragment(self) -> None:
        """Keep the URL fragment across the redirect this view returns."""
        self._request.session[INERTIA_SESSION_PRESERVE_FRAGMENT] = True

    def set_errors(self, errors: BaseForm | dict[str, Any]) -> None:
        """Send validation errors as the ``errors`` prop on the next page.

        Call this before redirecting back to the form, the way
        ``messages.error()`` is used. ``errors`` is a form or a mapping of
        field names to messages; each field keeps its first message. The
        errors are sent once, and included in partial reloads too.
        """
        self._request.session[INERTIA_SESSION_ERRORS] = error_messages(errors)

    def _header_list(self, name: str) -> list[str] | None:
        if name not in self._request.headers:
            return None
        return [
            value.strip()
            for value in self._request.headers[name].split(",")
            if value.strip()
        ]


class InertiaHttpRequest(HttpRequest):
    """An ``HttpRequest`` that has passed through ``InertiaMiddleware``.

    Use it to annotate views that call ``request.inertia``."""

    inertia: InertiaDetails


def get_details(request: HttpRequest) -> InertiaDetails:
    """Return ``request.inertia``, attaching it if no middleware did, such as
    for a request built with ``RequestFactory``."""
    details = getattr(request, "inertia", None)
    if not isinstance(details, InertiaDetails):
        details = InertiaDetails(request)
        request.inertia = details  # type: ignore[attr-defined]
    return details


def resolve_value(value: Any) -> Any:
    return value() if callable(value) else value


class PropsResolver:
    """Resolve props once and collect Inertia v3 metadata by dotted path."""

    def __init__(self, request: InertiaDetails, component: str, props: dict[str, Any]):
        self.request = request
        self.component = component
        self.props = props
        self.metadata: dict[str, Any] = {
            "deferredProps": {},
            "mergeProps": [],
            "prependProps": [],
            "deepMergeProps": [],
            "matchPropsOn": [],
            "scrollProps": {},
            "onceProps": {},
            "rescuedProps": [],
        }

    def resolve(self) -> tuple[dict[str, Any], dict[str, Any]]:
        resolved = self._resolve_mapping(self.props)
        return resolved, {key: value for key, value in self.metadata.items() if value}

    def _resolve_mapping(
        self, props: dict[str, Any], prefix: str = "", parent_resolved: bool = False
    ) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for key, prop in props.items():
            path = f"{prefix}.{key}" if prefix else key
            value = self._resolve_prop(prop, path, parent_resolved)
            if value is not SKIP_PROP:
                resolved[key] = value
        return resolved

    def _resolve_prop(self, prop: Any, path: str, parent_resolved: bool = False) -> Any:
        if (
            not parent_resolved
            and not (isinstance(prop, Prop) and prop.always)
            and self._excluded_by_partial_request(path)
        ):
            return SKIP_PROP

        if isinstance(prop, dict):
            if not prop:
                return {}
            resolved = self._resolve_mapping(prop, path, parent_resolved)
            return resolved if resolved else SKIP_PROP
        if isinstance(prop, list):
            return self._resolve_list(prop, path, parent_resolved)

        is_cached_once_prop = self._should_skip_loaded_once_prop(prop, path)
        self._collect_metadata(
            prop,
            path,
            include_deferred=not is_cached_once_prop,
        )
        if is_cached_once_prop:
            return SKIP_PROP
        if (
            not self._is_partial()
            and isinstance(prop, Prop)
            and prop.skipped_on_first_load
        ):
            return SKIP_PROP

        try:
            value = prop.resolve() if isinstance(prop, Prop) else resolve_value(prop)
        except Exception:
            if isinstance(prop, Prop) and prop.rescue:
                self.metadata["rescuedProps"].append(path)
                return SKIP_PROP
            raise

        if isinstance(value, Prop):
            return self._resolve_prop(value, path, parent_resolved=True)
        if isinstance(value, dict):
            if not value:
                return {}
            resolved = self._resolve_mapping(value, path, parent_resolved=True)
            return resolved if resolved else SKIP_PROP
        if isinstance(value, list):
            return self._resolve_list(value, path, parent_resolved=True)
        return value

    def _resolve_list(
        self, values: list[Any], path: str, parent_resolved: bool
    ) -> list[Any]:
        resolved: list[Any] = []
        for index, value in enumerate(values):
            item = self._resolve_list_item(value, path, index, parent_resolved)
            if item is not SKIP_PROP:
                resolved.append(item)
        return resolved

    def _resolve_list_item(
        self, value: Any, path: str, index: int, parent_resolved: bool
    ) -> Any:
        item_path = f"{path}.{index}"
        if isinstance(value, dict):
            return self._resolve_mapping(value, item_path, parent_resolved)
        if isinstance(value, Prop):
            return self._resolve_prop(value, item_path, parent_resolved)
        return resolve_value(value)

    def _is_partial(self) -> bool:
        return self.request.is_partial(self.component)

    def _excluded_by_partial_request(self, path: str) -> bool:
        if not self._is_partial():
            return False
        only = self.request.partial_data
        if only is not None and not any(self._paths_overlap(path, key) for key in only):
            return True
        except_keys = self.request.partial_except or []
        return any(path == key or path.startswith(f"{key}.") for key in except_keys)

    @staticmethod
    def _paths_overlap(left: str, right: str) -> bool:
        return (
            left == right
            or left.startswith(f"{right}.")
            or right.startswith(f"{left}.")
        )

    def _should_skip_loaded_once_prop(self, prop: Any, path: str) -> bool:
        return (
            bool(self.request)
            and not self._is_partial()
            and isinstance(prop, Prop)
            and prop.once
            and not prop.fresh
            and prop.once_key(path) in self.request.except_once_props
        )

    def _collect_metadata(
        self, prop: Any, path: str, *, include_deferred: bool = True
    ) -> None:
        if not isinstance(prop, Prop):
            return
        if include_deferred and prop.defer and not self._is_partial():
            self.metadata["deferredProps"].setdefault(prop.group, []).append(path)
        if prop.merges:
            self._collect_merge_metadata(prop, path)
        if prop.once:
            self.metadata["onceProps"][prop.once_key(path)] = {
                "prop": path,
                "expiresAt": prop.once_expires_at(),
            }

    def _collect_merge_metadata(self, prop: Prop, path: str) -> None:
        reset = path in self.request.reset
        if prop.scroll is not None:
            self.metadata["scrollProps"][path] = {**prop.scroll, "reset": reset}
        if reset:
            return
        if prop.deep_merge:
            self.metadata["deepMergeProps"].append(path)
        else:
            prepend_paths = prop.merge_paths(path, prepend=True)
            append_paths = prop.merge_paths(path)
            if prepend_paths:
                self.metadata["prependProps"].extend(prepend_paths)
            elif self._is_partial() and self.request.merge_intent == "prepend":
                self.metadata["prependProps"].extend(append_paths)
            else:
                self.metadata["mergeProps"].extend(append_paths)
        self.metadata["matchPropsOn"].extend(
            f"{path}.{match}" for match in prop.match_on
        )


@dataclass(frozen=True)
class InertiaPage:
    """The page object an Inertia response sent, as the client decodes it.

    ``data`` holds the whole object, including protocol metadata such as
    ``deferredProps`` and ``flash``.
    """

    component: str
    props: dict[str, Any]
    url: str
    version: str
    data: dict[str, Any]


class InertiaResponse(SimpleTemplateResponse):
    """An Inertia page that is resolved and encoded when ``render()`` is called.

    Like ``TemplateResponse``, the component, props and template data stay
    editable until Django's handler renders the response, so decorators and
    ``process_template_response`` middleware can change them.
    """

    json_encoder: type[JSONEncoder] | None = None
    rendering_attrs = [
        *SimpleTemplateResponse.rendering_attrs,
        "_inertia",
        "component",
        "props",
        "template_data",
        "encrypt_history",
    ]

    def __init__(
        self,
        request: HttpRequest,
        component: str,
        props: dict[str, Any] | None = None,
        template_data: dict[str, Any] | None = None,
        *,
        template_name: str | None = None,
        status: int | None = None,
        headers: dict[str, Any] | None = None,
        encrypt_history: bool | None = None,
    ) -> None:
        """``template_name`` is the layout for full page loads, by default
        ``INERTIA["LAYOUT"]``. It renders the page with the ``inertia_head``
        and ``inertia_body`` tags from ``{% load inertia %}``.

        ``encrypt_history`` encrypts the page in the browser's history;
        ``None`` uses ``INERTIA["ENCRYPT_HISTORY"]``.
        """
        if encrypt_history is not None and not isinstance(encrypt_history, bool):
            raise TypeError(
                f"Expected bool for encrypt_history, got {type(encrypt_history).__name__}"
            )
        self._inertia = get_details(request)
        content_type = None
        if self._inertia:
            headers = {**(headers or {}), "X-Inertia": "true"}
            content_type = "application/json"
        super().__init__(
            template_name or settings.LAYOUT or "",
            content_type=content_type,
            status=status,
            headers=headers,
        )
        self._request = request
        self.component = component
        self.props = props or {}
        self.template_data = template_data or {}
        self.encrypt_history = encrypt_history
        patch_vary_headers(self, ("X-Inertia",))

    @property
    def rendered_content(self) -> str:
        data = json_encode(
            self.page_data(),
            cls=self.json_encoder or settings.JSON_ENCODER,
        )
        # Page data is embedded in a JSON script tag for Inertia v3 clients.
        # Escape the few characters that could terminate or alter that script.
        data = (
            data.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
        )
        self._page_json = data
        if self._inertia:
            return data
        return self.build_first_load(data)

    @cached_property
    def inertia(self) -> InertiaPage:
        """The page this response sent. Available once the response is rendered."""
        if not self.is_rendered:
            raise ContentNotRenderedError(
                "The response must be rendered before its Inertia page is available."
            )
        data = json_decode(self._page_json)
        return InertiaPage(
            component=data["component"],
            props=data["props"],
            url=data["url"],
            version=data["version"],
            data=data,
        )

    def page_data(self) -> dict[str, Any]:
        request = self._request
        details = self._inertia
        clear_history = request.session.pop(INERTIA_SESSION_CLEAR_HISTORY, False)
        if not isinstance(clear_history, bool):
            raise TypeError(
                f"Expected bool for clear_history, got {type(clear_history).__name__}"
            )

        should_preserve_fragment = request.session.pop(
            INERTIA_SESSION_PRESERVE_FRAGMENT, False
        )
        if not isinstance(should_preserve_fragment, bool):
            raise TypeError(
                f"Expected bool for preserve_fragment, got {type(should_preserve_fragment).__name__}"
            )

        shared: dict[str, Any] = {}
        for provider in settings.SHARED_PROPS:
            shared.update(provider(request))
        shared.update(details.shared)
        errors = request.session.pop(INERTIA_SESSION_ERRORS, None)
        if errors:
            shared["errors"] = Prop(errors, always=True)

        resolved_props, metadata = PropsResolver(
            details, self.component, {**shared, **self.props}
        ).resolve()
        _page: dict[str, Any] = {
            "component": self.component,
            "props": resolved_props,
            "url": request.get_full_path(),
            "version": settings.VERSION,
            "encryptHistory": (
                settings.ENCRYPT_HISTORY
                if self.encrypt_history is None
                else self.encrypt_history
            ),
            "clearHistory": clear_history,
        }

        if should_preserve_fragment:
            _page["preserveFragment"] = True

        if shared:
            _page["sharedProps"] = list(shared)
        messages = [
            {"level": message.level_tag, "message": str(message)}
            for message in get_messages(request)
        ]
        if messages:
            _page["flash"] = {"messages": messages}
        _page.update(metadata)

        return _page

    def build_first_load(self, data: str) -> str:
        if not self.template_name:
            raise ImproperlyConfigured(
                'Set INERTIA["LAYOUT"] in your Django settings, '
                "or pass template_name to the response."
            )

        page = {"json": data, "head": "", "body": None}
        if settings.SSR_ENABLED:
            try:
                ssr_response = requests.post(
                    f"{settings.SSR_URL}/render",
                    data=data,
                    headers={"Content-Type": "application/json"},
                )
                ssr_response.raise_for_status()
                rendered = ssr_response.json()
                page["head"] = "".join(rendered["head"])
                page["body"] = rendered["body"]
            except Exception:
                logger.exception("SSR render request failed")

        template = self.resolve_template(self.template_name)
        return template.render({**self.template_data, "_inertia": page}, self._request)


def render(
    request: HttpRequest,
    component: str,
    props: dict[str, Any] | None = None,
    template_data: dict[str, Any] | None = None,
    *,
    template_name: str | None = None,
    status: int | None = None,
    headers: dict[str, Any] | None = None,
    encrypt_history: bool | None = None,
) -> InertiaResponse:
    return InertiaResponse(
        request,
        component,
        props,
        template_data,
        template_name=template_name,
        status=status,
        headers=headers,
        encrypt_history=encrypt_history,
    )


def location(location: str) -> HttpResponse:
    return HttpResponse(
        "",
        status=HTTPStatus.CONFLICT,
        headers={
            "X-Inertia-Location": location,
        },
    )


def error_messages(errors: BaseForm | dict[str, Any]) -> dict[str, str]:
    """Map each field to its first error message, the shape Inertia forms expect."""
    if isinstance(errors, BaseForm):
        errors = errors.errors
    return {
        field: str(messages[0]) if isinstance(messages, list) else str(messages)
        for field, messages in errors.items()
    }


def inertia(
    component: str, *, encrypt_history: bool | None = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Render the props dict a view returns as ``component``.

    ``encrypt_history=True`` encrypts the page in the browser's history, and
    ``False`` opts out of ``INERTIA["ENCRYPT_HISTORY"]``.

    Works with sync and async views. A view that returns an ``HttpResponse``,
    such as a redirect, passes it through unchanged.
    """

    def to_response(request: HttpRequest, props: Any) -> HttpResponse:
        if isinstance(props, HttpResponse):
            return props
        return InertiaResponse(
            request, component, props, encrypt_history=encrypt_history
        )

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if iscoroutinefunction(func):

            @wraps(func)
            async def async_view(
                request: HttpRequest, *args: Any, **kwargs: Any
            ) -> HttpResponse:
                return to_response(request, await func(request, *args, **kwargs))

            return async_view

        @wraps(func)
        def view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            return to_response(request, func(request, *args, **kwargs))

        return view

    return decorator
