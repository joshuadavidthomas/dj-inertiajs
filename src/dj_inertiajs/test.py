from typing import TYPE_CHECKING, Any

from django.http import HttpResponse
from django.test import AsyncClient, Client, TestCase

from .response import InertiaPage, InertiaResponse

__all__ = [
    "AsyncInertiaClient",
    "InertiaClient",
    "InertiaTestCase",
    "InertiaTestMixin",
]

if TYPE_CHECKING:
    from django.test import SimpleTestCase as _TestCaseBase
else:
    _TestCaseBase = object


class _InertiaVisits:
    def generic(
        self,
        method: str,
        path: str,
        *args: Any,
        inertia: bool = True,
        headers: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        if inertia:
            headers = {"X-Inertia": "true", **(headers or {})}
        return super().generic(method, path, *args, headers=headers, **kwargs)  # type: ignore[misc]


class InertiaClient(_InertiaVisits, Client):  # type: ignore[misc]
    """A test client whose requests are Inertia visits.

    Pass ``inertia=False`` to a request for a full page load, as a browser
    makes on the first visit: ``client.get("/events/", inertia=False)``.
    """


class AsyncInertiaClient(_InertiaVisits, AsyncClient):  # type: ignore[misc]
    """The async counterpart of ``InertiaClient``."""


class InertiaTestMixin(_TestCaseBase):
    """Inertia assertions for ``SimpleTestCase`` and its subclasses.

    Each assertion takes the response under test, like ``assertTemplateUsed``.
    ``self.client`` is an ``InertiaClient`` and ``self.async_client`` an
    ``AsyncInertiaClient``. Outside unittest, read ``response.inertia``
    directly.
    """

    client_class = InertiaClient
    async_client_class = AsyncInertiaClient

    def _inertia_response(
        self, response: HttpResponse, msg_prefix: str
    ) -> InertiaResponse:
        if not isinstance(response, InertiaResponse):
            self.fail(
                f"{msg_prefix}Expected an InertiaResponse, got {type(response).__name__}."
            )
        return response

    def _page(self, response: HttpResponse, msg_prefix: str) -> InertiaPage:
        return self._inertia_response(response, msg_prefix).inertia

    def assertComponentUsed(
        self, response: HttpResponse, component: str, msg_prefix: str = ""
    ) -> None:
        used = self._page(response, msg_prefix).component
        self.assertEqual(
            used,
            component,
            f"{msg_prefix}Component {used!r} was used, not {component!r}.",
        )

    def assertPropsEqual(
        self, response: HttpResponse, props: dict[str, Any], msg_prefix: str = ""
    ) -> None:
        self.assertDictEqual(
            self._page(response, msg_prefix).props, props, msg_prefix or None
        )

    def assertPropsContain(
        self, response: HttpResponse, props: dict[str, Any], msg_prefix: str = ""
    ) -> None:
        actual = self._page(response, msg_prefix).props
        self.assertDictEqual(actual, {**actual, **props}, msg_prefix or None)

    def assertTemplateDataEqual(
        self,
        response: HttpResponse,
        template_data: dict[str, Any],
        msg_prefix: str = "",
    ) -> None:
        actual = self._inertia_response(response, msg_prefix).template_data
        self.assertDictEqual(actual, template_data, msg_prefix or None)

    def assertTemplateDataContain(
        self,
        response: HttpResponse,
        template_data: dict[str, Any],
        msg_prefix: str = "",
    ) -> None:
        actual = self._inertia_response(response, msg_prefix).template_data
        self.assertDictEqual(actual, {**actual, **template_data}, msg_prefix or None)


class InertiaTestCase(InertiaTestMixin, TestCase):
    pass
