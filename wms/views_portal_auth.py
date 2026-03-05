from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import (
    url_has_allowed_host_and_scheme,
    urlsafe_base64_decode,
    urlsafe_base64_encode,
)
from django.views.decorators.http import require_http_methods

from .emailing import send_or_enqueue_email_safe
from .portal_helpers import get_association_profile
from .view_permissions import association_required

TEMPLATE_LOGIN = "portal/login.html"
TEMPLATE_SET_PASSWORD = "portal/set_password.html"  # nosec B105
TEMPLATE_CHANGE_PASSWORD = "portal/change_password.html"  # nosec B105
TEMPLATE_ACCESS_RECOVERY = "portal/access_recovery.html"

MODE_RECOVERY_FIRST = "first"
MODE_RECOVERY_FORGOT = "forgot"

ERROR_LOGIN_REQUIRED = "Email et mot de passe requis."
ERROR_LOGIN_INVALID = "Identifiants invalides."
ERROR_ACCOUNT_INACTIVE = "Compte inactif."
ERROR_ACCOUNT_NOT_ACTIVE = "Compte non activé par ASF."
ERROR_RECOVERY_EMAIL_REQUIRED = "Email requis."

MESSAGE_PASSWORD_UPDATED = "Mot de passe mis à jour."  # nosec B105
MESSAGE_RECOVERY_SUBMITTED = (
    "Si votre email est reconnu, vous recevrez un lien pour definir votre mot de passe."
)

SUBJECT_RECOVERY_FIRST = "ASF WMS - Premiere connexion portail"
SUBJECT_RECOVERY_FORGOT = "ASF WMS - Mot de passe oublie portail"

RECOVERY_THROTTLE_SECONDS_DEFAULT = 300

RECOVERY_MODE_CONFIG = {
    MODE_RECOVERY_FIRST: {
        "page_title": "Premiere connexion",
        "heading": "Premiere connexion",
        "lead": "Saisissez votre email pour recevoir un lien de definition du mot de passe.",
        "submit_label": "Recevoir le lien",
        "template": "emails/portal_first_connection.txt",
        "subject": SUBJECT_RECOVERY_FIRST,
    },
    MODE_RECOVERY_FORGOT: {
        "page_title": "Mot de passe oublie",
        "heading": "Mot de passe oublie",
        "lead": "Saisissez votre email pour recevoir un lien de reinitialisation.",
        "submit_label": "Reinitialiser le mot de passe",
        "template": "emails/portal_forgot_password.txt",
        "subject": SUBJECT_RECOVERY_FORGOT,
    },
}


def _build_login_context(*, errors, identifier, next_url):
    return {"errors": errors, "identifier": identifier, "next": next_url}


def _build_recovery_context(*, mode, errors, email, success_message):
    mode_config = RECOVERY_MODE_CONFIG[mode]
    return {
        "errors": errors,
        "email": email,
        "success_message": success_message,
        **mode_config,
    }


def _authenticate_portal_user(request, identifier, password):
    user = get_user_model().objects.filter(email__iexact=identifier).first()
    username = user.username if user else identifier
    return authenticate(request, username=username, password=password)


def _set_profile_password_changed(profile):
    if profile and profile.must_change_password:
        profile.must_change_password = False
        profile.save(update_fields=["must_change_password"])


def _get_user_from_uidb64(uidb64):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
        return None
    return get_user_model().objects.filter(pk=uid).first()


def _safe_next_url(request, next_url):
    candidate = (next_url or "").strip()
    if not candidate:
        return ""
    if not url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return ""
    return candidate


def _normalize_email(raw_value):
    return (raw_value or "").strip().lower()


def _get_client_ip(request):
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    return (request.META.get("REMOTE_ADDR") or "").strip() or "unknown"


def _get_recovery_throttle_seconds():
    raw_value = getattr(
        settings,
        "PORTAL_AUTH_RECOVERY_THROTTLE_SECONDS",
        RECOVERY_THROTTLE_SECONDS_DEFAULT,
    )
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return RECOVERY_THROTTLE_SECONDS_DEFAULT
    return max(0, value)


def _reserve_recovery_throttle_slot(*, mode, email, client_ip):
    timeout = _get_recovery_throttle_seconds()
    if timeout <= 0:
        return True

    normalized_email = _normalize_email(email)
    normalized_ip = (client_ip or "").strip() or "unknown"
    cache_key = (
        f"portal-access-recovery:{mode}:email:{normalized_email}:ip:{normalized_ip}"
    )
    return cache.add(cache_key, "1", timeout=timeout)


def _resolve_recovery_user(*, email, mode):
    user = get_user_model().objects.filter(email__iexact=email).first()
    if not user or not user.is_active:
        return None

    profile = get_association_profile(user)
    if not profile:
        return None

    if mode == MODE_RECOVERY_FIRST:
        if profile.must_change_password or not user.has_usable_password():
            return user
        return None

    if mode == MODE_RECOVERY_FORGOT:
        if user.has_usable_password():
            return user
        return None

    return None


def _build_set_password_url(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    path = reverse("portal:portal_set_password", args=[uid, token])
    return request.build_absolute_uri(path)


def _send_recovery_email(*, request, user, email, mode):
    mode_config = RECOVERY_MODE_CONFIG[mode]
    set_password_url = _build_set_password_url(request, user)
    login_url = request.build_absolute_uri(reverse("portal:portal_login"))
    message = render_to_string(
        mode_config["template"],
        {
            "email": email,
            "set_password_url": set_password_url,
            "login_url": login_url,
        },
    )
    send_or_enqueue_email_safe(
        subject=mode_config["subject"],
        message=message,
        recipient=[email],
    )


def _portal_access_recovery(request, *, mode):
    if request.user.is_authenticated:
        profile = get_association_profile(request.user)
        if profile:
            return redirect("portal:portal_dashboard")

    errors = []
    email = ""
    success_message = ""

    if request.method == "POST":
        email = _normalize_email(request.POST.get("email"))
        if not email:
            errors.append(ERROR_RECOVERY_EMAIL_REQUIRED)
        else:
            client_ip = _get_client_ip(request)
            if _reserve_recovery_throttle_slot(
                mode=mode,
                email=email,
                client_ip=client_ip,
            ):
                user = _resolve_recovery_user(email=email, mode=mode)
                if user is not None:
                    _send_recovery_email(
                        request=request,
                        user=user,
                        email=email,
                        mode=mode,
                    )
            success_message = MESSAGE_RECOVERY_SUBMITTED
            email = ""

    return render(
        request,
        TEMPLATE_ACCESS_RECOVERY,
        _build_recovery_context(
            mode=mode,
            errors=errors,
            email=email,
            success_message=success_message,
        ),
    )


@require_http_methods(["GET", "POST"])
def portal_login(request):
    if request.user.is_authenticated:
        profile = get_association_profile(request.user)
        if profile:
            return redirect("portal:portal_dashboard")

    errors = []
    identifier = ""
    next_url = _safe_next_url(request, request.GET.get("next"))
    if request.method == "POST":
        identifier = (request.POST.get("identifier") or "").strip()
        password = request.POST.get("password") or ""
        next_url = _safe_next_url(request, request.POST.get("next"))
        if not identifier or not password:
            errors.append(ERROR_LOGIN_REQUIRED)
        else:
            user = _authenticate_portal_user(request, identifier, password)
            if not user:
                errors.append(ERROR_LOGIN_INVALID)
            elif not user.is_active:
                errors.append(ERROR_ACCOUNT_INACTIVE)
            else:
                profile = get_association_profile(user)
                if not profile:
                    errors.append(ERROR_ACCOUNT_NOT_ACTIVE)
                    return render(
                        request,
                        TEMPLATE_LOGIN,
                        _build_login_context(
                            errors=errors,
                            identifier=identifier,
                            next_url=next_url,
                        ),
                    )
                login(request, user)
                if profile and profile.must_change_password:
                    return redirect("portal:portal_change_password")
                return redirect(next_url or "portal:portal_dashboard")

    return render(
        request,
        TEMPLATE_LOGIN,
        _build_login_context(errors=errors, identifier=identifier, next_url=next_url),
    )


@require_http_methods(["GET", "POST"])
def portal_first_connection(request):
    return _portal_access_recovery(request, mode=MODE_RECOVERY_FIRST)


@require_http_methods(["GET", "POST"])
def portal_forgot_password(request):
    return _portal_access_recovery(request, mode=MODE_RECOVERY_FORGOT)


@login_required(login_url="portal:portal_login")
def portal_logout(request):
    logout(request)
    return redirect("portal:portal_login")


@require_http_methods(["GET", "POST"])
def portal_set_password(request, uidb64, token):
    user = _get_user_from_uidb64(uidb64)

    if not user or not default_token_generator.check_token(user, token):
        return render(request, TEMPLATE_SET_PASSWORD, {"invalid": True})

    form = SetPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        _set_profile_password_changed(get_association_profile(user))
        login(request, user)
        return redirect("portal:portal_dashboard")

    return render(request, TEMPLATE_SET_PASSWORD, {"form": form, "invalid": False})


@login_required(login_url="portal:portal_login")
@association_required
@require_http_methods(["GET", "POST"])
def portal_change_password(request):
    form = SetPasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        _set_profile_password_changed(request.association_profile)
        messages.success(request, MESSAGE_PASSWORD_UPDATED)
        return redirect("portal:portal_dashboard")
    return render(request, TEMPLATE_CHANGE_PASSWORD, {"form": form})
