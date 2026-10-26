import json
from typing import Any, Callable

from django.conf import settings as django_settings
from django.http import HttpRequest
from django.utils.module_loading import import_string

__all__ = ["DEFAULTS", "settings"]

DEFAULTS: dict[str, Any] = {
    "LAYOUT": None,
    "VERSION": "1.0",
    "JSON_ENCODER": "dj_inertiajs.encoders.InertiaJsonEncoder",
    "ENCRYPT_HISTORY": False,
    "SHARED_PROPS": [],
    "FORM_ERRORS": "dj_inertiajs.request.error_messages",
    "SSR": {
        "ENABLED": False,
        "URL": "http://localhost:13714",
    },
}


class InertiaSettings:
    """The project's ``INERTIA`` setting merged over ``DEFAULTS``.

    Read on every access so ``override_settings(INERTIA=...)`` takes effect.
    """

    def _get(self, key: str) -> Any:
        return getattr(django_settings, "INERTIA", {}).get(key, DEFAULTS[key])

    @property
    def LAYOUT(self) -> str | None:
        return self._get("LAYOUT")  # type: ignore[no-any-return]

    @property
    def VERSION(self) -> str:
        return self._get("VERSION")  # type: ignore[no-any-return]

    @property
    def JSON_ENCODER(self) -> type[json.JSONEncoder]:
        return import_string(self._get("JSON_ENCODER"))  # type: ignore[no-any-return]

    @property
    def ENCRYPT_HISTORY(self) -> bool:
        return self._get("ENCRYPT_HISTORY")  # type: ignore[no-any-return]

    @property
    def SHARED_PROPS(self) -> list[Callable[[HttpRequest], dict[str, Any]]]:
        return [import_string(path) for path in self._get("SHARED_PROPS")]

    @property
    def FORM_ERRORS(self) -> Callable[[Any], dict[str, Any]]:
        return import_string(self._get("FORM_ERRORS"))  # type: ignore[no-any-return]

    @property
    def SSR_ENABLED(self) -> bool:
        return {**DEFAULTS["SSR"], **self._get("SSR")}["ENABLED"]  # type: ignore[no-any-return]

    @property
    def SSR_URL(self) -> str:
        return {**DEFAULTS["SSR"], **self._get("SSR")}["URL"]  # type: ignore[no-any-return]


settings = InertiaSettings()
