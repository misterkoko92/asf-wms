from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
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
from .forms import ShipmentTrackingAccessRecoveryForm
from .models import (
    Shipment,
    ShipmentTrackingAccessGrant,
    ShipmentTrackingAccessRole,
    ShipmentTrackingIdentityStatus,
    VolunteerProfile,
)
from .shipment_tracking_access import (
    activate_tracking_access_grant,
    find_active_tracking_access_grant,
    resolve_active_tracking_access_grant_by_id,
    resolve_shipment_contact_for_role,
    resolve_tracking_access_grant_by_email,
    resolve_tracking_access_grant_by_identifier,
    resolve_tracking_identifier_from_grant,
)

TEMPLATE_LOGIN = "scan/shipment_tracking_login.html"
TEMPLATE_SET_PASSWORD = "scan/shipment_tracking_set_password.html"  # nosec B105  # pragma: allowlist secret
TEMPLATE_ACCESS_RECOVERY = "scan/shipment_tracking_access_recovery.html"

MESSAGE_RECOVERY_SUBMITTED = _(
    "Si votre email est reconnu, vous recevrez les informations pour poursuivre votre scan."
)
ERROR_LOGIN_REQUIRED = _("Identifiant et mot de passe requis.")
ERROR_LOGIN_INVALID = _("Identifiants invalides.")
ERROR_ACCOUNT_INACTIVE = _("Compte inactif.")
ERROR_RECOVERY_EMAIL_REQUIRED = _("Email requis.")
ERROR_THROTTLE_LIMIT = _("Trop de tentatives. Merci de patienter quelques minutes.")
RECOVERY_EMAIL_TEMPLATE = "emails/shipment_tracking_access_recovery.txt"
RECOVERY_EMAIL_SUBJECT = _("ASF WMS - Accès suivi expédition")
LOGIN_THROTTLE_SECONDS_DEFAULT = 60
RECOVERY_THROTTLE_SECONDS_DEFAULT = 300


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


def _get_user_from_uidb64(uidb64):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
        return None
    return get_user_model().objects.filter(pk=uid).first()


def _normalize_email(raw_value):
    return (raw_value or "").strip().lower()


def _get_tracking_access_throttle_seconds(setting_name: str, default: int) -> int:
    raw_value = getattr(settings, setting_name, default)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return max(0, value)


def _tracking_access_throttle_keys(
    *,
    scope: str,
    role: str,
    identifier: str,
    client_ip: str,
    tracking_token: str = "",
):
    normalized_role = (role or "").strip() or "unknown"
    normalized_identifier = (identifier or "").strip().lower() or "unknown"
    normalized_ip = (client_ip or "").strip() or "unknown"
    normalized_token = (tracking_token or "").strip() or "none"
    base = f"shipment-tracking-access:{scope}:role:{normalized_role}:token:{normalized_token}"
    return (
        f"{base}:identifier:{normalized_identifier}",
        f"{base}:ip:{normalized_ip}",
    )


def _reserve_tracking_access_throttle_slot(
    *,
    scope: str,
    role: str,
    identifier: str,
    client_ip: str,
    tracking_token: str = "",
    timeout: int,
) -> bool:
    if timeout <= 0:
        return True
    identifier_key, ip_key = _tracking_access_throttle_keys(
        scope=scope,
        role=role,
        identifier=identifier,
        client_ip=client_ip,
        tracking_token=tracking_token,
    )
    identifier_reserved = cache.add(identifier_key, "1", timeout=timeout)
    ip_reserved = cache.add(ip_key, "1", timeout=timeout)
    if identifier_reserved and ip_reserved:
        return True
    if identifier_reserved:
        cache.delete(identifier_key)
    if ip_reserved:
        cache.delete(ip_key)
    return False


def _release_tracking_access_throttle_slot(
    *,
    scope: str,
    role: str,
    identifier: str,
    client_ip: str,
    tracking_token: str = "",
    timeout: int,
) -> None:
    if timeout <= 0:
        return
    for key in _tracking_access_throttle_keys(
        scope=scope,
        role=role,
        identifier=identifier,
        client_ip=client_ip,
        tracking_token=tracking_token,
    ):
        cache.delete(key)


def _build_tracking_next_url(*, shipment, role, identifier):
    params = {"role": role, "identifier": identifier}
    return (
        f"{reverse('scan:scan_shipment_track', args=[shipment.tracking_token])}?{urlencode(params)}"
    )


def _build_login_context(*, errors, identifier, role, next_url):
    return {
        "errors": errors,
        "identifier": identifier,
        "role": role,
        "next": next_url,
    }


def _merge_next_url_query(next_url, request) -> str:
    if not next_url:
        return ""
    split_result = urlsplit(next_url)
    query_pairs = dict(parse_qsl(split_result.query, keep_blank_values=True))
    for key in ("identifier", "role"):
        if key not in query_pairs:
            value = (request.GET.get(key) or request.POST.get(key) or "").strip()
            if value:
                query_pairs[key] = value
    return urlunsplit(
        (
            split_result.scheme,
            split_result.netloc,
            split_result.path,
            urlencode(query_pairs),
            split_result.fragment,
        )
    )


def _build_recovery_context(*, form, success_message):
    return {
        "form": form,
        "success_message": success_message,
    }


def _tracking_access_grant_from_request(request, *, user):
    role = (request.POST.get("role") or request.GET.get("role") or "").strip()
    identifier = (request.POST.get("identifier") or request.GET.get("identifier") or "").strip()
    grant = None
    if role and identifier:
        grant = resolve_tracking_access_grant_by_identifier(role=role, identifier=identifier)
    if grant is None and role:
        grant = resolve_tracking_access_grant_by_email(role=role, email=identifier)
    if grant is None or grant.user_id != user.id:
        return None
    return grant


def _authenticate_tracking_user(request, *, identifier, password, role):
    grant = resolve_tracking_access_grant_by_identifier(role=role, identifier=identifier)
    if grant is None:
        grant = resolve_tracking_access_grant_by_email(role=role, email=identifier)
    if grant is None:
        return None, None
    username = grant.user.username
    user = authenticate(request, username=username, password=password)
    if user is None or user.pk != grant.user_id:
        return None, None
    return user, grant


def _get_or_create_tracking_user(*, email, role, identifier):
    user_model = get_user_model()
    user = user_model.objects.filter(email__iexact=email).first()
    if user is not None:
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
        return user
    username = f"qr-{role}-{identifier or email}".lower()
    user = user_model.objects.create_user(
        username=username[:150],
        email=email,
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user


def _resolve_recovery_grant(*, shipment, email, role):
    normalized_email = _normalize_email(email)
    if role == ShipmentTrackingAccessRole.VOLUNTEER:
        user = get_user_model().objects.filter(email__iexact=normalized_email).first()
        if user is None:
            return None
        profile = getattr(user, "volunteer_profile", None)
        if profile is None:
            profile = VolunteerProfile.objects.filter(user=user).first()
        if profile is None:
            return None
        grant = find_active_tracking_access_grant(
            user=user,
            role=role,
            volunteer_profile=profile,
        )
        if grant is not None:
            return grant
        return ShipmentTrackingAccessGrant.objects.create(
            user=user,
            role=role,
            volunteer_profile=profile,
            identity_status=(
                ShipmentTrackingIdentityStatus.VERIFIED
                if getattr(profile, "is_active", False)
                else ShipmentTrackingIdentityStatus.PENDING
            ),
        )

    contact = resolve_shipment_contact_for_role(shipment=shipment, role=role)
    if contact is None:
        return None
    contact_emails = {
        _normalize_email(getattr(contact, "email", "")),
        _normalize_email(getattr(contact, "email2", "")),
    }
    contact_emails.discard("")
    if normalized_email not in contact_emails:
        return None
    grant = resolve_tracking_access_grant_by_email(role=role, email=normalized_email)
    if grant is not None and grant.contact_id == contact.id:
        return grant
    user = _get_or_create_tracking_user(
        email=normalized_email,
        role=role,
        identifier=getattr(contact, "asf_id", ""),
    )
    grant = find_active_tracking_access_grant(user=user, role=role, contact=contact)
    if grant is not None:
        return grant
    return ShipmentTrackingAccessGrant.objects.create(
        user=user,
        role=role,
        contact=contact,
        identity_status=ShipmentTrackingIdentityStatus.VERIFIED,
    )


def _build_tracking_set_password_url(request, *, user, grant, next_url):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    path = reverse("scan:scan_shipment_tracking_access_set_password", args=[uid, token])
    query = urlencode({"next": next_url, "grant": grant.id})
    return request.build_absolute_uri(f"{path}?{query}")


def _send_tracking_access_recovery_email(*, request, shipment, grant, escale_code):
    identifier = resolve_tracking_identifier_from_grant(grant)
    next_url = _build_tracking_next_url(
        shipment=shipment,
        role=grant.role,
        identifier=identifier,
    )
    set_password_url = _build_tracking_set_password_url(
        request,
        user=grant.user,
        grant=grant,
        next_url=next_url,
    )
    login_url = request.build_absolute_uri(
        f"{reverse('scan:scan_shipment_tracking_access_login')}?{urlencode({'next': next_url, 'role': grant.role})}"
    )
    tracking_url = request.build_absolute_uri(
        reverse("scan:scan_shipment_track", args=[shipment.tracking_token])
    )
    message = render_to_string(
        RECOVERY_EMAIL_TEMPLATE,
        {
            "shipment": shipment,
            "grant": grant,
            "identifier": identifier,
            "role_label": grant.get_role_display(),
            "escale_code": (escale_code or "").strip().upper(),
            "login_url": login_url,
            "set_password_url": set_password_url,
            "tracking_url": tracking_url,
        },
    )
    send_or_enqueue_email_safe(
        subject=RECOVERY_EMAIL_SUBJECT,
        message=message,
        recipient=[grant.user.email],
    )


@require_http_methods(["GET", "POST"])
def scan_shipment_tracking_access_login(request):
    if request.user.is_authenticated:
        next_url = _safe_next_url(request, request.GET.get("next"))
        grant = _tracking_access_grant_from_request(request, user=request.user)
        if next_url and grant is not None:
            activate_tracking_access_grant(request, grant=grant)
            return redirect(next_url)

    errors = []
    identifier = (request.GET.get("identifier") or "").strip()
    role = (request.GET.get("role") or "").strip()
    next_url = _safe_next_url(request, request.GET.get("next"))
    if request.method == "POST":
        identifier = (request.POST.get("identifier") or "").strip()
        password = request.POST.get("password") or ""
        role = (request.POST.get("role") or "").strip()
        next_url = _safe_next_url(request, request.POST.get("next"))
        client_ip = get_client_ip(request)
        throttle_timeout = _get_tracking_access_throttle_seconds(
            "SHIPMENT_TRACKING_ACCESS_LOGIN_THROTTLE_SECONDS",
            LOGIN_THROTTLE_SECONDS_DEFAULT,
        )
        if not identifier or not password:
            errors.append(ERROR_LOGIN_REQUIRED)
        elif not _reserve_tracking_access_throttle_slot(
            scope="login",
            role=role,
            identifier=identifier,
            client_ip=client_ip,
            timeout=throttle_timeout,
        ):
            errors.append(ERROR_THROTTLE_LIMIT)
        else:
            user, grant = _authenticate_tracking_user(
                request,
                identifier=identifier,
                password=password,
                role=role,
            )
            if user is None or grant is None:
                errors.append(ERROR_LOGIN_INVALID)
            elif not user.is_active:
                errors.append(ERROR_ACCOUNT_INACTIVE)
            else:
                _release_tracking_access_throttle_slot(
                    scope="login",
                    role=role,
                    identifier=identifier,
                    client_ip=client_ip,
                    timeout=throttle_timeout,
                )
                login(request, user)
                activate_tracking_access_grant(request, grant=grant)
                return redirect(next_url or reverse("scan:scan_root"))

    return render(
        request,
        TEMPLATE_LOGIN,
        _build_login_context(
            errors=errors,
            identifier=identifier,
            role=role,
            next_url=next_url,
        ),
    )


@require_http_methods(["GET", "POST"])
def scan_shipment_tracking_access_recovery(request):
    form = ShipmentTrackingAccessRecoveryForm(request.POST or None)
    success_message = ""
    if request.method == "POST":
        tracking_token = request.POST.get("tracking_token")
        email = _normalize_email(request.POST.get("email"))
        role = (request.POST.get("role") or "").strip()
        escale_code = (request.POST.get("escale_code") or "").strip()
        if not email:
            form.add_error("email", ERROR_RECOVERY_EMAIL_REQUIRED)
        else:
            client_ip = get_client_ip(request)
            throttle_timeout = _get_tracking_access_throttle_seconds(
                "SHIPMENT_TRACKING_ACCESS_RECOVERY_THROTTLE_SECONDS",
                RECOVERY_THROTTLE_SECONDS_DEFAULT,
            )
            if _reserve_tracking_access_throttle_slot(
                scope="recovery",
                role=role,
                identifier=email,
                client_ip=client_ip,
                tracking_token=tracking_token,
                timeout=throttle_timeout,
            ):
                shipment = None
                if tracking_token:
                    shipment = Shipment.objects.filter(tracking_token=tracking_token).first()
                if shipment is not None:
                    grant = _resolve_recovery_grant(
                        shipment=shipment,
                        email=email,
                        role=role,
                    )
                    if grant is not None:
                        _send_tracking_access_recovery_email(
                            request=request,
                            shipment=shipment,
                            grant=grant,
                            escale_code=escale_code,
                        )
            success_message = MESSAGE_RECOVERY_SUBMITTED
            form = ShipmentTrackingAccessRecoveryForm()

    return render(
        request,
        TEMPLATE_ACCESS_RECOVERY,
        _build_recovery_context(form=form, success_message=success_message),
    )


@require_http_methods(["GET", "POST"])
def scan_shipment_tracking_access_set_password(request, uidb64, token):
    user = _get_user_from_uidb64(uidb64)
    valid_link = user is not None and default_token_generator.check_token(user, token)
    form = SetPasswordForm(user) if valid_link else None
    invalid = not valid_link
    next_url = _safe_next_url(request, request.GET.get("next"))
    grant_id = request.GET.get("grant") or ""

    if valid_link and request.method == "POST":
        next_url = _safe_next_url(request, request.POST.get("next") or request.GET.get("next"))
        next_url = _merge_next_url_query(next_url, request)
        grant_id = request.POST.get("grant") or request.GET.get("grant") or grant_id
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            login(request, user)
            grant = resolve_active_tracking_access_grant_by_id(grant_id=grant_id, user=user)
            activate_tracking_access_grant(request, grant=grant)
            return redirect(next_url or reverse("scan:scan_root"))

    return render(
        request,
        TEMPLATE_SET_PASSWORD,
        {
            "form": form,
            "invalid": invalid,
            "next": next_url,
            "grant": grant_id,
        },
    )


@require_http_methods(["POST"])
def scan_shipment_tracking_access_logout(request):
    activate_tracking_access_grant(request, grant=None)
    logout(request)
    return redirect("scan:scan_shipment_tracking_access_login")
