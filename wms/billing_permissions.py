from django.core.exceptions import PermissionDenied

BILLING_STAFF_GROUP_NAME = "Billing_Staff"


def user_can_access_billing_scan(user) -> bool:
    if not user or not user.is_authenticated or not user.is_staff:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=BILLING_STAFF_GROUP_NAME).exists()


def user_can_manage_billing_admin(user) -> bool:
    return bool(user and user.is_authenticated and user.is_superuser)


def require_billing_staff_or_superuser(request):
    if not user_can_access_billing_scan(request.user):
        raise PermissionDenied
