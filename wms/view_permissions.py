from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse

from .models import AssociationRecipient
from .portal_helpers import get_association_profile


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


def association_required(view):
    def wrapped(request, *args, **kwargs):
        profile = get_association_profile(request.user)
        if not profile:
            raise PermissionDenied
        if profile.must_change_password:
            change_url = reverse("portal:portal_change_password")
            if request.path != change_url:
                return redirect(change_url)
        recipients_url = reverse("portal:portal_recipients")
        allowed_paths = {
            recipients_url,
            reverse("portal:portal_account"),
            reverse("portal:portal_logout"),
            reverse("portal:portal_change_password"),
        }
        has_delivery_contact = AssociationRecipient.objects.filter(
            association_contact=profile.contact,
            is_active=True,
            is_delivery_contact=True,
        ).exists()
        if not has_delivery_contact and request.path not in allowed_paths:
            return redirect(f"{recipients_url}?blocked=missing_delivery_contact")
        request.association_profile = profile
        return view(request, *args, **kwargs)

    return wrapped
