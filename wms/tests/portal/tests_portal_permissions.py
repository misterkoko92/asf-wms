from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import AssociationProfile
from wms.portal_permissions import (
    ASSOCIATION_PORTAL_GROUP_NAME,
    ASSOCIATION_PORTAL_PERMISSION_CODENAMES,
    assign_association_portal_group,
    ensure_association_portal_group,
)


class PortalPermissionsTests(TestCase):
    def _create_contact(self, name="Association Test"):
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def test_ensure_association_portal_group_sets_expected_permissions(self):
        group = ensure_association_portal_group(sync_permissions=True)

        self.assertEqual(group.name, ASSOCIATION_PORTAL_GROUP_NAME)
        self.assertSetEqual(
            set(group.permissions.values_list("codename", flat=True)),
            set(ASSOCIATION_PORTAL_PERMISSION_CODENAMES),
        )

    def test_assign_association_portal_group_adds_user_to_group(self):
        user = get_user_model().objects.create_user(
            username="portal-group-user",
            email="portal-group-user@example.com",
            password="pass1234",
        )
        assign_association_portal_group(user, sync_permissions=True)

        group = Group.objects.get(name=ASSOCIATION_PORTAL_GROUP_NAME)
        self.assertTrue(user.groups.filter(id=group.id).exists())

    def test_association_profile_creation_auto_assigns_group(self):
        user = get_user_model().objects.create_user(
            username="portal-profile-user",
            email="portal-profile-user@example.com",
            password="pass1234",
        )
        contact = self._create_contact(name="Association Grouped")

        AssociationProfile.objects.create(user=user, contact=contact)

        group = Group.objects.get(name=ASSOCIATION_PORTAL_GROUP_NAME)
        self.assertTrue(user.groups.filter(id=group.id).exists())
