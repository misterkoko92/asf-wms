from django.db.models.functions import Lower

from .models import VolunteerProfile

ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY = "scan_active_preparateur_volunteer_id"


def _active_volunteer_queryset():
    return (
        VolunteerProfile.objects.filter(
            is_active=True,
            user__is_active=True,
        )
        .select_related("user")
        .order_by(
            Lower("user__last_name"),
            Lower("user__first_name"),
            "id",
        )
    )


def list_active_preparateur_volunteers():
    return list(_active_volunteer_queryset())


def get_active_preparateur_volunteer(request):
    volunteer_id = request.session.get(ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY)
    if not volunteer_id:
        return None
    volunteer = _active_volunteer_queryset().filter(id=volunteer_id).first()
    if volunteer is None:
        request.session.pop(ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY, None)
        request.session.modified = True
    return volunteer


def set_active_preparateur_volunteer(request, *, volunteer):
    request.session[ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY] = volunteer.id
    request.session.modified = True


def clear_active_preparateur_volunteer(request):
    request.session.pop(ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY, None)
    request.session.modified = True


def build_preparateur_volunteer_label(volunteer):
    first_name = (getattr(volunteer.user, "first_name", "") or "").strip()
    last_name = (getattr(volunteer.user, "last_name", "") or "").strip().upper()
    full_name = " ".join(part for part in [first_name, last_name] if part).strip()
    if full_name:
        return full_name
    fallback = (volunteer.user.get_full_name() or "").strip()
    return fallback or volunteer.user.username


def get_preparateur_greeting_name(volunteer):
    first_name = (getattr(volunteer.user, "first_name", "") or "").strip()
    if first_name:
        return first_name
    short_name = (getattr(volunteer, "short_name", "") or "").strip()
    if short_name:
        return short_name
    last_name = (getattr(volunteer.user, "last_name", "") or "").strip()
    return last_name or volunteer.user.username
