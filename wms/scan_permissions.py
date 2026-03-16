PREPARATEUR_GROUP_NAME = "Preparateur"
PREPARATEUR_ALLOWED_SCAN_VIEWS = frozenset(
    {
        "scan_root",
        "scan_pack",
        "scan_sync",
    }
)


def user_is_preparateur(user):
    if not getattr(user, "is_authenticated", False):
        return False
    return user.groups.filter(name=PREPARATEUR_GROUP_NAME).exists()


def is_scan_view_allowed_for_user(request):
    if not user_is_preparateur(request.user):
        return True
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match is None:
        return False
    return resolver_match.url_name in PREPARATEUR_ALLOWED_SCAN_VIEWS
