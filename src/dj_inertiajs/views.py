from __future__ import annotations

from functools import wraps
from http import HTTPStatus
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.http import HttpResponse
from django.views.generic import View

from .http import InertiaResponse
from .http import clear_history as set_clear_history
from .http import encrypt_history as set_encrypt_history


class InertiaMixin:
    clear_history: bool = False
    component_name: str | None = None
    encrypt_history: bool = False
    request: HttpRequest
    serializer_class: Any = None
    template_name: str | None = None
    ssr_template_name: str | None = None

    def get_clear_history(self) -> bool:
        return self.clear_history

    def get_component_name(self) -> str:
        if self.component_name is None:
            raise ImproperlyConfigured(
                "%s must define 'component_name' or override 'get_component_name()'",
                self.__class__.__name__,
            )
        return self.component_name

    def get_context_data(self, **kwargs):
        if hasattr(super(), "get_context_data"):
            return super().get_context_data(**kwargs)
        return kwargs

    def get_encrypt_history(self) -> bool:
        return self.encrypt_history

    def get_prop_data(self, **kwargs):
        return {}

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs.setdefault("context", self.get_serializer_context())
        return serializer_class(*args, **kwargs)

    def get_serializer_context(self):
        return {
            "request": self.request,
            "view": self,
        }

    def get_serializer_class(self):
        assert (
            self.serializer_class is not None
        ), f"'{self.__class__.__name__}' should either include a `serializer_class` attribute, or override the `get_serializer_class()` method."
        return self.serializer_class

    def get_template_name(self) -> str | None:
        return self.template_name

    def get_ssr_template_name(self) -> str | None:
        return self.ssr_template_name

    def render_to_response(self, context, **response_kwargs):
        component_name = self.get_component_name()

        props = self.get_prop_data(**context)

        if hasattr(self, "serializer_class") and self.serializer_class is not None:
            props = self.serialize_props(props)

        if self.get_encrypt_history():
            set_encrypt_history(self.request, True)

        if self.get_clear_history():
            set_clear_history(self.request)

        template_name = self.get_template_name()
        ssr_template_name = self.get_ssr_template_name()

        return InertiaResponse(
            self.request,
            component_name,
            props,
            context,
            template_name=template_name,
            ssr_template_name=ssr_template_name,
            **response_kwargs,
        )

    def serialize_props(self, data: Any) -> Any:
        if hasattr(self, "serializer_class") and self.serializer_class:
            serializer = self.get_serializer(data)
            return serializer.data
        return data


class InertiaView(InertiaMixin, View):
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)


def render(
    request,
    component,
    props=None,
    template_data=None,
    template_name=None,
    ssr_template_name=None,
):
    return InertiaResponse(
        request,
        component,
        props or {},
        template_data or {},
        template_name=template_name,
        ssr_template_name=ssr_template_name,
    )


def location(location):
    from .middleware import InertiaHeader

    return HttpResponse(
        b"",
        status=HTTPStatus.CONFLICT,
        headers={
            InertiaHeader.LOCATION: location,
        },
    )


def inertia(component):
    def decorator(func):
        @wraps(func)
        def process_inertia_response(request, *args, **kwargs):
            props = func(request, *args, **kwargs)

            if isinstance(props, HttpResponse):
                return props

            return InertiaResponse(request, component, props)

        return process_inertia_response

    return decorator
