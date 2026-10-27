from typing import Any

from django.http import HttpRequest
from django.http.response import HttpResponseRedirectBase
from django.shortcuts import redirect as django_redirect

from .response import InertiaResponse

__all__ = ["redirect", "render"]


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


def redirect(
    to: Any,
    *args: Any,
    permanent: bool = False,
    preserve_fragment: bool = False,
    **kwargs: Any,
) -> HttpResponseRedirectBase:
    """``django.shortcuts.redirect``, plus Inertia's redirect options.

    ``preserve_fragment=True`` keeps the URL fragment of the request, such as
    ``#section``, on the page the client is redirected to.
    """
    response = django_redirect(to, *args, permanent=permanent, **kwargs)
    response.preserve_fragment = preserve_fragment  # type: ignore[union-attr]
    return response
