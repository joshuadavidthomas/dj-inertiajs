from typing import TYPE_CHECKING, Any

from django.http import HttpResponse
from django.test import Client, TestCase

from .http import InertiaPage, InertiaResponse

__all__ = ["InertiaClient", "InertiaTestCase", "InertiaTestMixin"]

if TYPE_CHECKING:
    from django.test import SimpleTestCase as _TestCaseBase
else:
    _TestCaseBase = object


class InertiaClient(Client):
    """A test client whose requests are Inertia visits."""

    def __init__(
        self, *args: Any, headers: dict[str, str] | None = None, **kwargs: Any
    ):
        super().__init__(
            *args, headers={"X-Inertia": "true", **(headers or {})}, **kwargs
        )


class InertiaTestMixin(_TestCaseBase):
    """Inertia assertions for ``SimpleTestCase`` and its subclasses.

    Each assertion takes the response under test, like ``assertTemplateUsed``.
    ``self.inertia`` is an ``InertiaClient``. Outside unittest, read
    ``response.inertia`` directly.
    """

    def setUp(self) -> None:
        super().setUp()
        self.inertia = InertiaClient()

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

    def assertHasExactProps(
        self, response: HttpResponse, props: dict[str, Any], msg_prefix: str = ""
    ) -> None:
        self.assertDictEqual(
            self._page(response, msg_prefix).props, props, msg_prefix or None
        )

    def assertIncludesProps(
        self, response: HttpResponse, props: dict[str, Any], msg_prefix: str = ""
    ) -> None:
        actual = self._page(response, msg_prefix).props
        self.assertDictEqual(actual, {**actual, **props}, msg_prefix or None)

    def assertHasExactTemplateData(
        self,
        response: HttpResponse,
        template_data: dict[str, Any],
        msg_prefix: str = "",
    ) -> None:
        actual = self._inertia_response(response, msg_prefix).template_data
        self.assertDictEqual(actual, template_data, msg_prefix or None)

    def assertIncludesTemplateData(
        self,
        response: HttpResponse,
        template_data: dict[str, Any],
        msg_prefix: str = "",
    ) -> None:
        actual = self._inertia_response(response, msg_prefix).template_data
        self.assertDictEqual(actual, {**actual, **template_data}, msg_prefix or None)


class InertiaTestCase(InertiaTestMixin, TestCase):
    pass
