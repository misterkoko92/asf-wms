from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse

from .compliance import is_role_operation_allowed
from .helper_install import resolve_helper_installer_access
from .models import AssociationRecipient, OrganizationRole, OrganizationRoleAssignment
from .portal_helpers import get_association_profile

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


def require_superuser(request):
    if not request.user.is_superuser:
        raise PermissionDenied


def scan_staff_required(view):
    @login_required(login_url="admin:login")
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
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
    def _resolve_shipper_access_block_reason(profile):
        role_assignment = (
            OrganizationRoleAssignment.objects.filter(
                organization=profile.contact,
                role=OrganizationRole.SHIPPER,
            )
            .order_by("id")
            .first()
        )
        if role_assignment is None:
            return None
        if not role_assignment.is_active:
            return BLOCKED_REASON_REVIEW_PENDING
        if not is_role_operation_allowed(role_assignment):
            return BLOCKED_REASON_COMPLIANCE_REQUIRED
        return None

    def wrapped(request, *args, **kwargs):
        profile = get_association_profile(request.user)
        if not profile:
            raise PermissionDenied
        if profile.must_change_password:
            change_url = reverse("portal:portal_change_password")
            if request.path != change_url:
                return redirect(change_url)
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
        return view(request, *args, **kwargs)

    return wrapped
