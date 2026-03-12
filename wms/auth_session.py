from django.conf import settings

REMEMBER_ME_SUPPORT_FIELD = "remember_me_supported"
REMEMBER_ME_FIELD = "remember_me"


def _is_truthy(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def remember_me_requested(data) -> bool:
    return _is_truthy(data.get(REMEMBER_ME_FIELD))


def remember_me_supported(data) -> bool:
    return REMEMBER_ME_SUPPORT_FIELD in data


def apply_remember_me_session_policy(request) -> None:
    if request is None:
        return
    if not remember_me_supported(request.POST):
        return
    expiry = settings.SESSION_COOKIE_AGE if remember_me_requested(request.POST) else 0
    request.session.set_expiry(expiry)
