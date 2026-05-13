# apps/iglesias/apps.py
from django.apps import AppConfig


class IglesiasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.iglesias"  # <--- CAMBIA ESTO. Debe ser la ruta completa.
