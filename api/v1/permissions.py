import hmac

from django.conf import settings
from rest_framework.permissions import IsAuthenticated

from wms.portal_access import resolve_active_portal_scope
from wms.portal_helpers import get_association_profile


def has_integration_key(request) -> bool:
    api_key = getattr(settings, "INTEGRATION_API_KEY", "").strip()
    request_key = request.headers.get("X-ASF-Integration-Key", "").strip()
    return bool(api_key and request_key and hmac.compare_digest(request_key, api_key))


class IntegrationKeyOrAuth(IsAuthenticated):
    require_staff = False

    def has_permission(self, request, view):
        if has_integration_key(request):
            return True
        if not super().has_permission(request, view):
            return False
        if self.require_staff:
            return bool(request.user and request.user.is_staff)
        return True


class IntegrationKeyOrStaff(IntegrationKeyOrAuth):
    require_staff = True


class IsStaffUser(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return bool(request.user and request.user.is_staff)


class IsAssociationProfileUser(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return get_association_profile(request.user) is not None


class IsPortalScopeUser(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        scope = resolve_active_portal_scope(request)
        if scope is None:
            return False
        request.portal_scope = scope
        return True
