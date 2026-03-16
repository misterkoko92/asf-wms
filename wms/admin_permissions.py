from django.contrib import admin

from .scan_permissions import user_is_preparateur


def install_preparateur_admin_guard():
    if getattr(admin.site, "_wms_preparateur_guard_installed", False):
        return

    original_has_permission = admin.site.has_permission

    def guarded_has_permission(request):
        if user_is_preparateur(getattr(request, "user", None)):
            return False
        return original_has_permission(request)

    admin.site.has_permission = guarded_has_permission
    admin.site._wms_preparateur_guard_installed = True
