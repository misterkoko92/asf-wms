from django.db.models import Model

from .models import CartonStatusEvent
from .workflow_observability import log_carton_status_transition


def _resolve_actor(user):
    if user is None:
        return None
    if not hasattr(user, "_meta"):
        return None
    if not getattr(user, "pk", None):
        return None
    if hasattr(user, "is_authenticated") and not user.is_authenticated:
        return None
    return user


def _is_persisted_model_instance(instance):
    return isinstance(instance, Model) and getattr(instance, "pk", None) is not None


def record_carton_status_event(
    *,
    carton,
    previous_status,
    new_status,
    reason="",
    user=None,
):
    if previous_status == new_status:
        return False
    if not _is_persisted_model_instance(carton):
        return False
    CartonStatusEvent.objects.create(
        carton=carton,
        previous_status=previous_status,
        new_status=new_status,
        reason=reason or "",
        created_by=_resolve_actor(user),
    )
    return True


def set_carton_status(
    *,
    carton,
    new_status,
    user=None,
    reason="",
    update_fields=None,
):
    previous_status = getattr(carton, "status", None)
    if previous_status == new_status:
        return False
    carton.status = new_status
    fields = list(update_fields or [])
    if "status" not in fields:
        fields.append("status")
    carton.save(update_fields=fields)
    record_carton_status_event(
        carton=carton,
        previous_status=previous_status,
        new_status=new_status,
        reason=reason,
        user=user,
    )
    log_carton_status_transition(
        carton=carton,
        previous_status=previous_status,
        new_status=new_status,
        reason=reason,
        user=user,
        source="set_carton_status",
    )
    return True
