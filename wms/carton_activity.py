from django.db.models import Model

from .models import CartonStatus, CartonVolunteerActivity


def _resolve_actor(actor):
    if actor is None:
        return None
    if not isinstance(actor, Model):
        return None
    if not getattr(actor, "pk", None):
        return None
    if hasattr(actor, "is_authenticated") and not actor.is_authenticated:
        return None
    return actor


def record_carton_volunteer_activity(*, carton, volunteer, action, actor=None):
    if carton is None or not getattr(carton, "pk", None):
        return None
    if volunteer is None or not getattr(volunteer, "pk", None):
        return None
    return CartonVolunteerActivity.objects.create(
        carton=carton,
        volunteer=volunteer,
        action=action,
        actor=_resolve_actor(actor),
    )


def find_last_carton_for_volunteer(volunteer):
    if volunteer is None or not getattr(volunteer, "pk", None):
        return None
    activity_queryset = (
        CartonVolunteerActivity.objects.filter(volunteer=volunteer)
        .select_related("carton")
        .order_by("-created_at", "-id")
    )
    preferred_activity = activity_queryset.exclude(carton__status=CartonStatus.SHIPPED).first()
    if preferred_activity is not None:
        return preferred_activity.carton
    fallback_activity = activity_queryset.first()
    return fallback_activity.carton if fallback_activity is not None else None
