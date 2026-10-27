from __future__ import annotations

from typing import Any

from django.forms import BaseForm, BaseFormSet
from django.http import HttpRequest

from .conf import settings

__all__ = [
    "InertiaDetails",
    "InertiaHttpRequest",
    "clear_history",
    "set_errors",
]

INERTIA_SESSION_CLEAR_HISTORY = "_inertia_clear_history"
INERTIA_SESSION_PRESERVE_FRAGMENT = "_inertia_preserve_fragment"
INERTIA_SESSION_ERRORS = "_inertia_errors"


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


def error_messages(
    errors: BaseForm | BaseFormSet[Any] | dict[str, Any],
) -> dict[str, str]:
    """Map each field to its first error message, the shape Inertia forms expect.

    The default ``INERTIA["FORM_ERRORS"]``. Errors not tied to a field stay
    under Django's ``"__all__"`` key. A formset's errors are keyed
    ``"<prefix>.<index>.<field>"``, and its own errors ``"<prefix>"``.
    """
    if isinstance(errors, BaseFormSet):
        prefix = str(errors.prefix)
        result = {}
        if errors.non_form_errors():
            result[prefix] = str(errors.non_form_errors()[0])
        for index, form in enumerate(errors.forms):
            for field, message in error_messages(form).items():
                result[f"{prefix}.{index}.{field}"] = message
        return result
    if isinstance(errors, BaseForm):
        errors = errors.errors
    return {
        field: str(messages[0]) if isinstance(messages, list) else str(messages)
        for field, messages in errors.items()
    }


def set_errors(
    request: HttpRequest, errors: BaseForm | BaseFormSet[Any] | dict[str, Any]
) -> None:
    """Send validation errors as the ``errors`` prop on the next page.

    Call this before redirecting back to the form, the way
    ``messages.error()`` is used. ``errors`` is a form, a formset or a
    mapping of field names to messages, converted by
    ``INERTIA["FORM_ERRORS"]``; by default each field keeps its first
    message. The errors are sent once, and included in partial reloads too.
    """
    request.session[INERTIA_SESSION_ERRORS] = settings.FORM_ERRORS(errors)


def clear_history(request: HttpRequest) -> None:
    """Clear the client's encrypted history on the next page, for example on
    logout."""
    request.session[INERTIA_SESSION_CLEAR_HISTORY] = True
