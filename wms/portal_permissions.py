from django.contrib.auth.models import Group, Permission

ASSOCIATION_PORTAL_GROUP_NAME = "Association_Portail"

# Minimal permission set for association users in portal flows.
# Access control is primarily enforced by association profile scoping.
ASSOCIATION_PORTAL_PERMISSION_CODENAMES = (
    "view_product",
    "view_order",
    "add_order",
    "view_associationrecipient",
    "add_associationrecipient",
    "change_associationrecipient",
    "view_accountdocument",
    "add_accountdocument",
    "view_orderdocument",
    "add_orderdocument",
    "view_associationportalcontact",
    "add_associationportalcontact",
    "change_associationportalcontact",
)


def get_association_portal_permissions():
    return Permission.objects.filter(
        content_type__app_label="wms",
        codename__in=ASSOCIATION_PORTAL_PERMISSION_CODENAMES,
    )


def ensure_association_portal_group(*, sync_permissions=True):
    group, _ = Group.objects.get_or_create(name=ASSOCIATION_PORTAL_GROUP_NAME)
    if sync_permissions:
        group.permissions.set(get_association_portal_permissions())
    return group


def assign_association_portal_group(user, *, sync_permissions=True):
    if not user or not getattr(user, "pk", None):
        return
    group = ensure_association_portal_group(sync_permissions=sync_permissions)
    user.groups.add(group)
