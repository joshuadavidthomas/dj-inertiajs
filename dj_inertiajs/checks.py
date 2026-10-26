import re
from importlib.util import find_spec
from typing import Any

from django.apps import apps
from django.conf import settings as django_settings
from django.core.checks import CheckMessage, Error
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.utils.module_loading import import_string

from .conf import DEFAULTS, settings

SESSION_MIDDLEWARE = "django.contrib.sessions.middleware.SessionMiddleware"
INERTIA_MIDDLEWARE = "dj_inertiajs.middleware.InertiaMiddleware"
OLD_MIDDLEWARE = "inertia.middleware.InertiaMiddleware"
OLD_SETTINGS = {
    "INERTIA_LAYOUT": 'INERTIA["LAYOUT"]',
    "INERTIA_VERSION": 'INERTIA["VERSION"]',
    "INERTIA_JSON_ENCODER": 'INERTIA["JSON_ENCODER"], as a dotted path',
    "INERTIA_ENCRYPT_HISTORY": 'INERTIA["ENCRYPT_HISTORY"]',
    "INERTIA_SSR_ENABLED": 'INERTIA["SSR"]["ENABLED"]',
    "INERTIA_SSR_URL": 'INERTIA["SSR"]["URL"]',
}
OLD_LAYOUT_BLOCK = re.compile(r"{%-?\s*block\s+inertia(_head)?\s*-?%}")


def guide(section: str) -> str:
    return f'See the section "{section}" in the guide "Upgrading from inertia-django".'


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


def check_upgrade(**kwargs: Any) -> list[CheckMessage]:
    """Report inertia-django configuration that this package no longer reads."""
    errors: list[CheckMessage] = []
    for name, replacement in OLD_SETTINGS.items():
        if hasattr(django_settings, name):
            errors.append(
                Error(
                    f"{name} is an inertia-django setting and is ignored.",
                    hint=f"Use {replacement}. {guide('Settings')}",
                    id="inertia.E007",
                )
            )
    if OLD_MIDDLEWARE in django_settings.MIDDLEWARE:
        errors.append(
            Error(
                f"'{OLD_MIDDLEWARE}' is inertia-django's middleware.",
                hint=f"Replace it with '{INERTIA_MIDDLEWARE}'. {guide('Middleware')}",
                id="inertia.E008",
            )
        )
    if apps.is_installed("inertia"):
        errors.append(
            Error(
                "inertia-django's 'inertia' app is in INSTALLED_APPS.",
                hint=f"Replace it with 'dj_inertiajs'. {guide('Install and app name')}",
                id="inertia.E009",
            )
        )
    layout = settings.LAYOUT
    source = _template_source(layout) if layout else None
    if source is not None and OLD_LAYOUT_BLOCK.search(source):
        errors.append(
            Error(
                f"The layout {layout!r} uses inertia-django's "
                "{% block inertia %} or {% block inertia_head %}, which are no "
                "longer filled, so pages render without the app.",
                hint="Load inertia and use {% inertia_head %} and {% inertia_body %}. "
                + guide("Layout templates"),
                id="inertia.E010",
            )
        )
    return errors


def _template_source(name: str) -> str | None:
    try:
        template = get_template(name)
    except TemplateDoesNotExist:
        return None
    source = getattr(getattr(template, "template", None), "source", None)
    return source if isinstance(source, str) else None
