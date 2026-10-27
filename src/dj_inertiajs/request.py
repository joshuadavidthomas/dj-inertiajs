from __future__ import annotations

from django.http import HttpRequest

__all__ = [
    "InertiaDetails",
    "InertiaHttpRequest",
]


class InertiaDetails:
    """Inertia's view of one request, available as ``request.inertia``.

    ``InertiaMiddleware`` attaches it, the way ``SessionMiddleware`` attaches
    ``request.session``, and only describes the request, like
    django-htmx's ``request.htmx``. It is truthy when the Inertia client made
    the request.
    """

    def __init__(self, request: HttpRequest) -> None:
        self._request = request

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
