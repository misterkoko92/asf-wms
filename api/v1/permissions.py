from django.conf import settings
from rest_framework.permissions import IsAuthenticated


def has_integration_key(request) -> bool:
    api_key = getattr(settings, "INTEGRATION_API_KEY", "").strip()
    request_key = request.headers.get("X-ASF-Integration-Key", "").strip()
    return bool(api_key and request_key == api_key)


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
