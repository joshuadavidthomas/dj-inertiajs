from django.apps import AppConfig
from django.core import checks


class InertiaConfig(AppConfig):
    name = "django_inertia"
    verbose_name = "Inertia"

    def ready(self) -> None:
        from .checks import check_middleware, check_settings, check_upgrade

        checks.register(check_settings)
        checks.register(check_middleware)
        checks.register(check_upgrade)
