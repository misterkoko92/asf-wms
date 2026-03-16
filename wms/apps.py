from django.apps import AppConfig


class WmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "wms"

    def ready(self) -> None:
        from . import signals
        from .admin_permissions import install_preparateur_admin_guard

        install_preparateur_admin_guard()
        signals.register_change_signals()
