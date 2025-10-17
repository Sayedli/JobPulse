from django.apps import AppConfig


class ApplicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'applications'

    def ready(self) -> None:  # pragma: no cover - avoids import cycles in tests
        from . import signals  # noqa: F401
