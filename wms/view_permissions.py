from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse

from .portal_helpers import get_association_profile


def require_superuser(request):
    if not request.user.is_superuser:
        raise PermissionDenied


def association_required(view):
    def wrapped(request, *args, **kwargs):
        profile = get_association_profile(request.user)
        if not profile:
            raise PermissionDenied
        if profile.must_change_password:
            change_url = reverse("portal:portal_change_password")
            if request.path != change_url:
                return redirect(change_url)
        request.association_profile = profile
        return view(request, *args, **kwargs)

    return wrapped
