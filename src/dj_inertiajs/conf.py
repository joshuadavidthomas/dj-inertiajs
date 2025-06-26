from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from json import JSONEncoder
from typing import override

from django.conf import settings

from .utils import InertiaJsonEncoder

DJ_INERTIAJS_SETTINGS_NAME = "DJ_INERTIAJS"


@dataclass(frozen=True)
class AppSettings:
    ENCRYPT_HISTORY: bool = False
    JSON_ENCODER: type[JSONEncoder] = InertiaJsonEncoder
    LAYOUT: str = ""
    SHARED_PROPS: list[str] = field(default_factory=list)
    SSR_ENABLED: bool = False
    SSR_URL: str = "http://127.0.0.1:13714"
    VERSION: str = "1.0"

    @override
    def __getattribute__(self, __name: str) -> object:
        user_settings = getattr(settings, DJ_INERTIAJS_SETTINGS_NAME, {})
        return user_settings.get(__name, super().__getattribute__(__name))


app_settings = AppSettings()
