from django.apps import apps
from django.db.models.signals import post_delete, post_save

from .models import WmsChange


def _bump_change(**kwargs) -> None:
    WmsChange.bump()


def register_change_signals() -> None:
    for app_label in ("wms", "contacts"):
        app_config = apps.get_app_config(app_label)
        for model in app_config.get_models():
            if model is WmsChange:
                continue
            post_save.connect(
                _bump_change,
                sender=model,
                dispatch_uid=f"wms_change_save_{app_label}_{model.__name__}",
            )
            post_delete.connect(
                _bump_change,
                sender=model,
                dispatch_uid=f"wms_change_delete_{app_label}_{model.__name__}",
            )
