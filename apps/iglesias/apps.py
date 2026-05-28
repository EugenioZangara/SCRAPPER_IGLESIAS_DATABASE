from django.apps import AppConfig


class IglesiasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.iglesias"

    def ready(self):
        import apps.iglesias.signals  # noqa: F401
