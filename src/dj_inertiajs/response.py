import logging
from dataclasses import dataclass
from functools import cached_property
from http import HTTPStatus
from json import JSONEncoder
from json import dumps as json_encode
from json import loads as json_decode
from typing import Any

from django.contrib.messages import get_messages
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import get_token
from django.template.response import ContentNotRenderedError, SimpleTemplateResponse
from django.utils.cache import patch_vary_headers
from django.utils.encoding import iri_to_uri

from .conf import settings
from .props import Prop, PropsResolver
from .request import get_details
from .session import NextPage, pop_next_page

try:
    # Must be early-imported so tests can patch it with
    # a mock module
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

__all__ = ["InertiaLocation", "InertiaPage", "InertiaResponse"]

logger = logging.getLogger(__name__)


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
    # What page_data() took from the session, for the middleware to put back
    # if it discards the rendered page.
    next_page: NextPage | None = None
    rendering_attrs = [
        *SimpleTemplateResponse.rendering_attrs,
        "_request",
        "_details",
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

        ``template_data`` is extra context for that layout. It is copied, so
        ``response.template_data`` can change before render without affecting
        another response built from the same dict.

        ``encrypt_history`` encrypts the page in the browser's history;
        ``None`` uses ``INERTIA["ENCRYPT_HISTORY"]``.
        """
        if encrypt_history is not None and not isinstance(encrypt_history, bool):
            raise TypeError(
                f"Expected bool for encrypt_history, got {type(encrypt_history).__name__}"
            )
        self._details = get_details(request)
        content_type = None
        if self._details:
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
        self.template_data = dict(template_data or {})
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
        if self._details:
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
        details = self._details
        # The client sends this cookie's token with every visit and useHttp
        # request, but an Inertia page never renders {% csrf_token %}.
        get_token(request)
        next_page = self.next_page = pop_next_page(request)

        shared: dict[str, Any] = {}
        for provider in settings.SHARED_PROPS:
            shared.update(provider(request))
        if next_page.errors:
            shared["errors"] = Prop(next_page.errors, always=True)

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
            "clearHistory": next_page.clear_history,
        }

        if next_page.preserve_fragment:
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


class InertiaLocation(HttpResponse):
    """Make the Inertia client leave the app and load ``url`` in full.

    The Inertia counterpart of ``HttpResponseRedirect``, for an external
    site or a page that is not an Inertia page.
    """

    status_code = HTTPStatus.CONFLICT

    def __init__(self, url: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self["X-Inertia-Location"] = iri_to_uri(url)

    @property
    def url(self) -> str:
        return self["X-Inertia-Location"]
