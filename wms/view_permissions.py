from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse

from .helper_install import resolve_helper_installer_access
from .models import (
    AssociationProfile,
    AssociationRecipient,
    PortalAccessRole,
    ShipmentShipper,
    ShipmentValidationStatus,
)
from .portal_access import list_user_portal_scopes, resolve_active_portal_scope
from .portal_helpers import get_association_profile
from .preparateur_session import (
    build_preparateur_volunteer_label,
    get_active_preparateur_volunteer,
    get_preparateur_greeting_name,
)
from .scan_permissions import is_scan_view_allowed_for_user, user_is_preparateur

BLOCKED_REASON_QUERY_PARAM = "blocked"
BLOCKED_REASON_MISSING_DELIVERY_CONTACT = "missing_delivery_contact"
BLOCKED_REASON_REVIEW_PENDING = "review_pending"
BLOCKED_REASON_COMPLIANCE_REQUIRED = "compliance_required"
BLOCKED_MESSAGE_MISSING_DELIVERY_CONTACT = (
    "Compte bloqué: ajoutez au moins un destinataire avec la case "
    '"Contact utilisé pour la réception dans l\'escale de livraison" cochée.'
)
BLOCKED_MESSAGE_REVIEW_PENDING = (
    "Compte expéditeur en cours de revue ASF. Accès commandes bloqué temporairement."
)
BLOCKED_MESSAGE_COMPLIANCE_REQUIRED = (
    "Compte bloqué: documents expéditeur non conformes ou non validés par ASF."
)
BLOCKED_MESSAGES = {
    BLOCKED_REASON_MISSING_DELIVERY_CONTACT: BLOCKED_MESSAGE_MISSING_DELIVERY_CONTACT,
    BLOCKED_REASON_REVIEW_PENDING: BLOCKED_MESSAGE_REVIEW_PENDING,
    BLOCKED_REASON_COMPLIANCE_REQUIRED: BLOCKED_MESSAGE_COMPLIANCE_REQUIRED,
}
ACCOUNT_REQUEST_VALIDATION_GROUP_DEFAULT = "Account_User_Validation"


def require_superuser(request):
    if not request.user.is_superuser:
        raise PermissionDenied


def user_can_review_account_requests(user):
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_staff", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    group_name = getattr(
        settings,
        "ACCOUNT_REQUEST_VALIDATION_GROUP_NAME",
        ACCOUNT_REQUEST_VALIDATION_GROUP_DEFAULT,
    )
    return user.groups.filter(name=group_name).exists()


def scan_staff_required(view):
    @login_required(login_url="admin:login")
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        request.scan_is_preparateur = user_is_preparateur(request.user)
        request.scan_active_volunteer = None
        request.scan_active_volunteer_label = ""
        request.scan_active_volunteer_greeting_name = ""
        if request.scan_is_preparateur:
            active_volunteer = get_active_preparateur_volunteer(request)
            request.scan_active_volunteer = active_volunteer
            if active_volunteer is not None:
                request.scan_active_volunteer_label = build_preparateur_volunteer_label(
                    active_volunteer
                )
                request.scan_active_volunteer_greeting_name = get_preparateur_greeting_name(
                    active_volunteer
                )
        if not is_scan_view_allowed_for_user(request):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


def scan_account_validator_required(view):
    @scan_staff_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not user_can_review_account_requests(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


def scan_staff_or_helper_installer_token_required(*, app_label):
    def decorator(view):
        staff_view = scan_staff_required(view)

        @wraps(view)
        def wrapped(request, *args, **kwargs):
            helper_access = resolve_helper_installer_access(request, app_label=app_label)
            if helper_access is not None:
                request.helper_installer_access = helper_access
                return view(request, *args, **kwargs)
            return staff_view(request, *args, **kwargs)

        return wrapped

    return decorator


def volunteer_required(view):
    @login_required(login_url="volunteer:login")
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        profile = getattr(request.user, "volunteer_profile", None)
        if not profile or not profile.is_active:
            raise PermissionDenied
        if profile.must_change_password:
            try:
                change_url = reverse("volunteer:change_password")
            except NoReverseMatch:
                change_url = ""
            if change_url and request.path != change_url:
                return redirect(change_url)
        request.volunteer_profile = profile
        return view(request, *args, **kwargs)

    return wrapped


def association_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        response = _bind_portal_scope(request)
        if response is not None:
            return response
        response = _bind_association_profile(request)
        if response is not None:
            return response
        return view(request, *args, **kwargs)

    return wrapped


def portal_scope_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        response = _bind_portal_scope(request)
        if response is not None:
            return response
        return view(request, *args, **kwargs)

    return wrapped


def _resolve_shipper_access_block_reason(profile):
    shipper = (
        ShipmentShipper.objects.filter(
            organization=profile.contact,
        )
        .order_by("id")
        .first()
    )
    if shipper is None:
        return None
    if not shipper.is_active or shipper.validation_status == ShipmentValidationStatus.PENDING:
        return BLOCKED_REASON_REVIEW_PENDING
    if shipper.validation_status == ShipmentValidationStatus.REJECTED:
        return BLOCKED_REASON_COMPLIANCE_REQUIRED
    return None


def _bind_portal_scope(request):
    scope = resolve_active_portal_scope(request)
    scopes = list_user_portal_scopes(request.user)
    request.portal_scope_count = len(scopes)
    if scope is None:
        if len(scopes) > 1:
            return redirect("portal:portal_scope_select")
        raise PermissionDenied
    request.portal_scope = scope
    if scope.association_profile is not None and scope.association_profile.must_change_password:
        change_url = reverse("portal:portal_change_password")
        if request.path != change_url:
            return redirect(change_url)
    if request.method == "GET":
        from .application.portal.onboarding import build_portal_onboarding_context

        request.portal_onboarding = build_portal_onboarding_context(request)
    return None


def _bind_association_profile(request):
    scope = getattr(request, "portal_scope", None)
    if scope is None:
        response = _bind_portal_scope(request)
        if response is not None:
            return response
        scope = getattr(request, "portal_scope", None)
    if scope is None or scope.role != PortalAccessRole.SHIPPER_ADMIN:
        raise PermissionDenied
    if scope.shipper is None and scope.association_profile is None:
        raise PermissionDenied

    profile = _resolve_scope_association_profile(request, scope=scope)
    if profile is None:
        raise PermissionDenied

    recipients_url = reverse("portal:portal_recipients")
    account_url = reverse("portal:portal_account")
    billing_url = reverse("portal:portal_billing")
    allowed_paths = {
        recipients_url,
        account_url,
        reverse("portal:portal_logout"),
        reverse("portal:portal_change_password"),
    }

    def _is_allowed_portal_path(path):
        if path in allowed_paths:
            return True
        if path.startswith(recipients_url):
            return True
        return path.startswith(billing_url)

    shipper_block_reason = _resolve_shipper_access_block_reason(profile)
    if shipper_block_reason and not _is_allowed_portal_path(request.path):
        blocked_message = BLOCKED_MESSAGES.get(shipper_block_reason)
        if blocked_message:
            messages.error(request, blocked_message)
        return redirect(f"{account_url}?{BLOCKED_REASON_QUERY_PARAM}={shipper_block_reason}")

    has_delivery_contact = AssociationRecipient.objects.filter(
        association_contact=profile.contact,
        is_active=True,
        is_delivery_contact=True,
    ).exists()
    if not has_delivery_contact and not _is_allowed_portal_path(request.path):
        return redirect(
            f"{recipients_url}?{BLOCKED_REASON_QUERY_PARAM}={BLOCKED_REASON_MISSING_DELIVERY_CONTACT}"
        )

    request.association_profile = profile
    return None


def _resolve_scope_association_profile(request, *, scope):
    if scope.association_profile is not None:
        return scope.association_profile

    profile = get_association_profile(request.user)
    if scope.shipper is None:
        return profile

    scope_contact_id = scope.shipper.organization_id
    if profile is not None:
        if profile.contact_id != scope_contact_id:
            raise PermissionDenied
        return profile

    return AssociationProfile.objects.create(
        user=request.user,
        contact=scope.shipper.organization,
    )


def require_association_profile(request):
    response = _bind_association_profile(request)
    if response is not None:
        return response
    return request.association_profile
