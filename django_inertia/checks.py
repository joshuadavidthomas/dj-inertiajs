from importlib.util import find_spec
from typing import Any

from django.conf import settings as django_settings
from django.core.checks import CheckMessage, Error
from django.utils.module_loading import import_string

from .settings import DEFAULTS, settings

SESSION_MIDDLEWARE = "django.contrib.sessions.middleware.SessionMiddleware"
INERTIA_MIDDLEWARE = "django_inertia.middleware.InertiaMiddleware"


def check_settings(**kwargs: Any) -> list[CheckMessage]:
    errors: list[CheckMessage] = []
    unknown = sorted(set(getattr(django_settings, "INERTIA", {})) - set(DEFAULTS))
    if unknown:
        errors.append(
            Error(
                f"Unknown INERTIA keys: {', '.join(unknown)}.",
                hint=f"Valid keys are {', '.join(DEFAULTS)}.",
                id="inertia.E001",
            )
        )
    if not settings.LAYOUT:
        errors.append(
            Error(
                'INERTIA["LAYOUT"] is not set.',
                hint="Set it to the template that wraps every Inertia page.",
                id="inertia.E002",
            )
        )
    for path in settings._get("SHARED_PROPS"):
        try:
            import_string(path)
        except ImportError as e:
            errors.append(
                Error(
                    f'INERTIA["SHARED_PROPS"] entry {path!r} cannot be imported: {e}',
                    id="inertia.E006",
                )
            )
    if settings.SSR_ENABLED and find_spec("requests") is None:
        errors.append(
            Error(
                "Server-side rendering is enabled but requests is not installed.",
                hint="Install the package's ssr extra.",
                id="inertia.E003",
            )
        )
    return errors


def check_middleware(**kwargs: Any) -> list[CheckMessage]:
    errors: list[CheckMessage] = []
    if not _contains_subclass(INERTIA_MIDDLEWARE, django_settings.MIDDLEWARE):
        errors.append(
            Error(
                f"'{INERTIA_MIDDLEWARE}' must be in MIDDLEWARE.",
                id="inertia.E004",
            )
        )
    if not _contains_subclass(SESSION_MIDDLEWARE, django_settings.MIDDLEWARE):
        errors.append(
            Error(
                f"'{SESSION_MIDDLEWARE}' must be in MIDDLEWARE.",
                hint="Inertia stores history and fragment flags in the session.",
                id="inertia.E005",
            )
        )
    return errors


def _contains_subclass(class_path: str, candidate_paths: list[str]) -> bool:
    cls = import_string(class_path)
    for path in candidate_paths:
        try:
            candidate = import_string(path)
        except ImportError:
            continue
        if isinstance(candidate, type) and issubclass(candidate, cls):
            return True
    return False
