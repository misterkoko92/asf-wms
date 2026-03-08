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
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from .client_ip import get_client_ip
from .emailing import send_or_enqueue_email_safe
from .view_permissions import volunteer_required

TEMPLATE_LOGIN = "benevole/login.html"
TEMPLATE_SET_PASSWORD = "benevole/set_password.html"  # nosec B105  # pragma: allowlist secret
TEMPLATE_CHANGE_PASSWORD = "benevole/change_password.html"  # nosec B105  # pragma: allowlist secret
TEMPLATE_ACCESS_RECOVERY = "benevole/access_recovery.html"

ERROR_LOGIN_REQUIRED = _("Email et mot de passe requis.")
ERROR_LOGIN_INVALID = _("Identifiants invalides.")
ERROR_ACCOUNT_INACTIVE = _("Compte inactif.")
ERROR_ACCOUNT_NOT_ACTIVE = _("Compte bénévole non activé.")
ERROR_RECOVERY_EMAIL_REQUIRED = _("Email requis.")
MESSAGE_PASSWORD_UPDATED = _("Mot de passe mis à jour.")  # nosec B105
MESSAGE_RECOVERY_SUBMITTED = _(
    "Si votre email est reconnu, vous recevrez un lien pour definir votre mot de passe."
)

RECOVERY_PAGE_TITLE = _("Mot de passe oublié / Première connexion bénévole")
RECOVERY_HEADING = _("Mot de passe oublié / Première connexion")
RECOVERY_LEAD = _(
    "Saisissez votre email pour recevoir un lien de definition ou de "
    "reinitialisation du mot de passe."
)
RECOVERY_SUBMIT_LABEL = _("Recevoir le lien")
RECOVERY_EMAIL_TEMPLATE = "emails/volunteer_forgot_password.txt"
RECOVERY_EMAIL_SUBJECT = _("ASF WMS - Mot de passe oublié / Première connexion bénévole")
RECOVERY_THROTTLE_SECONDS_DEFAULT = 300


def _get_volunteer_profile(user):
    return getattr(user, "volunteer_profile", None)


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


def _authenticate_volunteer_user(request, identifier, password):
    user = get_user_model().objects.filter(email__iexact=identifier).first()
    username = user.username if user else identifier
    return authenticate(request, username=username, password=password)


def _normalize_email(raw_value):
    return (raw_value or "").strip().lower()


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


def _build_recovery_context(*, errors, email, success_message):
    return {
        "errors": errors,
        "email": email,
        "success_message": success_message,
        "page_title": RECOVERY_PAGE_TITLE,
        "heading": RECOVERY_HEADING,
        "lead": RECOVERY_LEAD,
        "submit_label": RECOVERY_SUBMIT_LABEL,
    }


def _get_recovery_throttle_seconds():
    raw_value = getattr(
        settings,
        "VOLUNTEER_AUTH_RECOVERY_THROTTLE_SECONDS",
        RECOVERY_THROTTLE_SECONDS_DEFAULT,
    )
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return RECOVERY_THROTTLE_SECONDS_DEFAULT
    return max(0, value)


def _reserve_recovery_throttle_slot(*, email, client_ip):
    timeout = _get_recovery_throttle_seconds()
    if timeout <= 0:
        return True

    normalized_email = _normalize_email(email)
    normalized_ip = (client_ip or "").strip() or "unknown"
    cache_key = f"volunteer-access-recovery:email:{normalized_email}:ip:{normalized_ip}"
    return cache.add(cache_key, "1", timeout=timeout)


def _resolve_recovery_user(*, email):
    user = get_user_model().objects.filter(email__iexact=email).first()
    if not user or not user.is_active:
        return None

    profile = _get_volunteer_profile(user)
    if not profile or not profile.is_active:
        return None
    return user


def _build_set_password_url(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    path = reverse("volunteer:set_password", args=[uid, token])
    return request.build_absolute_uri(path)


def _send_recovery_email(*, request, user, email):
    set_password_url = _build_set_password_url(request, user)
    login_url = request.build_absolute_uri(reverse("volunteer:login"))
    message = render_to_string(
        RECOVERY_EMAIL_TEMPLATE,
        {
            "email": email,
            "set_password_url": set_password_url,
            "login_url": login_url,
        },
    )
    send_or_enqueue_email_safe(
        subject=RECOVERY_EMAIL_SUBJECT,
        message=message,
        recipient=[email],
    )


def _volunteer_access_recovery(request):
    if request.user.is_authenticated:
        profile = _get_volunteer_profile(request.user)
        if profile and profile.is_active:
            return redirect("volunteer:dashboard")

    errors = []
    email = ""
    success_message = ""

    if request.method == "POST":
        email = _normalize_email(request.POST.get("email"))
        if not email:
            errors.append(ERROR_RECOVERY_EMAIL_REQUIRED)
        else:
            client_ip = get_client_ip(request)
            if _reserve_recovery_throttle_slot(email=email, client_ip=client_ip):
                user = _resolve_recovery_user(email=email)
                if user is not None:
                    _send_recovery_email(request=request, user=user, email=email)
            success_message = MESSAGE_RECOVERY_SUBMITTED
            email = ""

    return render(
        request,
        TEMPLATE_ACCESS_RECOVERY,
        _build_recovery_context(
            errors=errors,
            email=email,
            success_message=success_message,
        ),
    )


@require_http_methods(["GET", "POST"])
def volunteer_login(request):
    if request.user.is_authenticated:
        profile = _get_volunteer_profile(request.user)
        if profile and profile.is_active:
            return redirect(
                "volunteer:change_password"
                if profile.must_change_password
                else "volunteer:dashboard"
            )

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
            user = _authenticate_volunteer_user(request, identifier, password)
            if not user:
                errors.append(ERROR_LOGIN_INVALID)
            elif not user.is_active:
                errors.append(ERROR_ACCOUNT_INACTIVE)
            else:
                profile = _get_volunteer_profile(user)
                if not profile or not profile.is_active:
                    errors.append(ERROR_ACCOUNT_NOT_ACTIVE)
                else:
                    login(request, user)
                    if profile.must_change_password:
                        return redirect("volunteer:change_password")
                    return redirect(next_url or "volunteer:dashboard")

    return render(
        request,
        TEMPLATE_LOGIN,
        {"errors": errors, "identifier": identifier, "next": next_url},
    )


@require_http_methods(["GET", "POST"])
def volunteer_forgot_password(request):
    return _volunteer_access_recovery(request)


@login_required(login_url="volunteer:login")
def volunteer_logout(request):
    logout(request)
    return redirect("volunteer:login")


@require_http_methods(["GET", "POST"])
def volunteer_set_password(request, uidb64, token):
    user = _get_user_from_uidb64(uidb64)
    profile = _get_volunteer_profile(user) if user else None
    if not user or not profile or not default_token_generator.check_token(user, token):
        return render(request, TEMPLATE_SET_PASSWORD, {"invalid": True})

    form = SetPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        _set_profile_password_changed(profile)
        login(request, user)
        return redirect("volunteer:dashboard")

    return render(request, TEMPLATE_SET_PASSWORD, {"form": form, "invalid": False})


@volunteer_required
@require_http_methods(["GET", "POST"])
def volunteer_change_password(request):
    form = SetPasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        _set_profile_password_changed(request.volunteer_profile)
        messages.success(request, MESSAGE_PASSWORD_UPDATED)
        return redirect("volunteer:dashboard")
    return render(request, TEMPLATE_CHANGE_PASSWORD, {"form": form})
