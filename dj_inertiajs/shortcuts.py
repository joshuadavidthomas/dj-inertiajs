from typing import Any

from django.http import HttpRequest

from .response import InertiaResponse

__all__ = ["render"]


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
