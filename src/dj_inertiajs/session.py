"""What this package carries to the next Inertia page, the way
``django.contrib.messages`` carries messages.

Everything is kept under one session key and read once, as a whole, by the
next ``InertiaResponse`` that renders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.forms import BaseForm, BaseFormSet
from django.http import HttpRequest

from .conf import settings

__all__ = ["clear_history", "set_errors"]

SESSION_KEY = "_inertia"


@dataclass(frozen=True)
class NextPage:
    """The state stored for the next page."""

    errors: dict[str, Any] | None = None
    clear_history: bool = False
    preserve_fragment: bool = False


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
    _update(request, errors=settings.FORM_ERRORS(errors))


def clear_history(request: HttpRequest) -> None:
    """Clear the client's encrypted history on the next page, for example on
    logout."""
    _update(request, clear_history=True)


def preserve_fragment(request: HttpRequest) -> None:
    """Keep the URL fragment on the next page. ``InertiaMiddleware`` calls it
    for a ``redirect(..., preserve_fragment=True)``."""
    _update(request, preserve_fragment=True)


def pop_next_page(request: HttpRequest) -> NextPage:
    """Remove and return the state stored for the next page."""
    return NextPage(**request.session.pop(SESSION_KEY, {}))


def _update(request: HttpRequest, **changes: Any) -> None:
    # Assign a new dict: changing the stored one in place would not mark the
    # session as modified, and the change would not be saved.
    request.session[SESSION_KEY] = {
        **request.session.get(SESSION_KEY, {}),
        **changes,
    }
