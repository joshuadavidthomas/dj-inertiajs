import copy
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.views.generic import View

from .http import InertiaResponse
from .props import Prop

__all__ = ["InertiaResponseMixin", "InertiaView"]


class InertiaResponseMixin:
    """Render an Inertia component from a class-based view.

    The Inertia counterpart of ``TemplateResponseMixin``. Put it before a
    generic view, as in ``class EventList(InertiaResponseMixin, ListView)``,
    and the generic view's ``render_to_response()`` calls render the
    component instead of a template.

    Props come from ``get_props()``. By default that collects the ``Prop``
    attributes declared on the class. A declared ``Prop`` whose value is a
    string names a method on the view, which is called only when the prop is
    sent::

        class Dashboard(InertiaView):
            component = "Dashboard"
            stats = Prop("get_stats", defer=True)

            def get_stats(self):
                return Stats.objects.summary()
    """

    request: HttpRequest
    component: str | None = None
    response_class: type[InertiaResponse] = InertiaResponse

    def get_component(self) -> str:
        if self.component is None:
            raise ImproperlyConfigured(
                f"{type(self).__name__} requires either a definition of "
                "'component' or an implementation of 'get_component()'."
            )
        return self.component

    def get_props(self, **kwargs: Any) -> dict[str, Any]:
        """Return the page's props.

        ``kwargs`` is the context a generic view built, such as
        ``object_list`` or ``form``. It is not sent; override this method,
        call ``super()``, and add the values the page needs.
        """
        props: dict[str, Any] = {}
        for klass in reversed(type(self).__mro__):
            for name, value in vars(klass).items():
                if isinstance(value, Prop):
                    props[name] = self._bind(name, value)
        return props

    def render_to_response(
        self, context: dict[str, Any], **response_kwargs: Any
    ) -> InertiaResponse:
        return self.response_class(
            self.request,
            self.get_component(),
            self.get_props(**context),
            **response_kwargs,
        )

    def _bind(self, name: str, prop: Prop) -> Prop:
        if not isinstance(prop.value, str):
            return prop
        method = getattr(self, prop.value, None)
        if not callable(method):
            raise ImproperlyConfigured(
                f"{type(self).__name__}.{name} names {prop.value!r}, "
                "which is not a method on the view."
            )
        bound = copy.copy(prop)
        bound.value = method
        return bound


class InertiaView(InertiaResponseMixin, View):
    """Render ``component`` on GET, passing URL keyword arguments to ``get_props()``."""

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> InertiaResponse:
        return self.render_to_response(kwargs)
