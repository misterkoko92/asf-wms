from django.db.models.functions import Lower

from .models import VolunteerProfile

PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY = "preparateur_active_volunteer_id"
LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY = "scan_active_preparateur_volunteer_id"


def build_preparateur_volunteer_queryset():
    return (
        VolunteerProfile.objects.filter(is_active=True, user__is_active=True)
        .select_related("user")
        .order_by(Lower("user__last_name"), Lower("user__first_name"), "id")
    )


def clear_active_preparateur_volunteer(request):
    if PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY in request.session:
        request.session.pop(PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY, None)
    if LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY in request.session:
        request.session.pop(LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY, None)


def set_active_preparateur_volunteer(request, volunteer):
    request.session[PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY] = volunteer.id
    request.session.pop(LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY, None)


def get_active_preparateur_volunteer(request):
    volunteer_id = request.session.get(PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY)
    if not volunteer_id:
        volunteer_id = request.session.get(LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY)
    if not volunteer_id:
        return None
    volunteer = build_preparateur_volunteer_queryset().filter(pk=volunteer_id).first()
    if volunteer is None:
        clear_active_preparateur_volunteer(request)
    return volunteer


def build_preparateur_volunteer_label(volunteer):
    user = getattr(volunteer, "user", None)
    if user is None:
        return ""
    first_name = (user.first_name or "").strip()
    last_name = (user.last_name or "").strip()
    if first_name and last_name:
        return f"{first_name} {last_name.upper()}"
    if first_name:
        return first_name
    if last_name:
        return last_name.upper()
    return user.username


def list_active_preparateur_volunteers():
    return list(build_preparateur_volunteer_queryset())


def get_preparateur_greeting_name(volunteer):
    user = getattr(volunteer, "user", None)
    if user is None:
        return ""
    first_name = (user.first_name or "").strip()
    if first_name:
        return first_name
    last_name = (user.last_name or "").strip()
    if last_name:
        return last_name.upper()
    return user.username
