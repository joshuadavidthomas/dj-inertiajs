from functools import wraps
from typing import Any, Callable

from asgiref.sync import iscoroutinefunction
from django.http import HttpRequest, HttpResponse

from .response import InertiaResponse

__all__ = ["inertia"]


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
