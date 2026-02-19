from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
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

    def test_association_profile_requires_active_organization_contact(self):
        user = get_user_model().objects.create_user(
            username="portal-invalid-profile",
            email="portal-invalid-profile@example.com",
            password="pass1234",
        )
        person_contact = Contact.objects.create(
            name="Person Contact",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        with self.assertRaises(ValidationError):
            AssociationProfile.objects.create(user=user, contact=person_contact)

        inactive_org = Contact.objects.create(
            name="Inactive Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=False,
        )
        with self.assertRaises(ValidationError):
            AssociationProfile.objects.create(user=user, contact=inactive_org)

    def test_association_profile_creation_syncs_contact_email_from_user(self):
        user = get_user_model().objects.create_user(
            username="portal-email-sync-create",
            email="user@example.com",
            password="pass1234",
        )
        contact = Contact.objects.create(
            name="Association Sync Create",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            email="contact@example.com",
        )
        AssociationProfile.objects.create(user=user, contact=contact)
        contact.refresh_from_db()
        self.assertEqual(contact.email, "user@example.com")

    def test_association_profile_creation_backfills_user_email_when_empty(self):
        user = get_user_model().objects.create_user(
            username="portal-email-sync-create-empty",
            email="",
            password="pass1234",
        )
        contact = Contact.objects.create(
            name="Association Sync Empty",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            email="contact@example.com",
        )
        AssociationProfile.objects.create(user=user, contact=contact)
        user.refresh_from_db()
        self.assertEqual(user.email, "contact@example.com")

    def test_contact_email_update_syncs_profile_user_email(self):
        user = get_user_model().objects.create_user(
            username="portal-email-sync-contact",
            email="user-before@example.com",
            password="pass1234",
        )
        contact = self._create_contact(name="Association Sync Contact")
        AssociationProfile.objects.create(user=user, contact=contact)

        contact.email = "contact-after@example.com"
        contact.save(update_fields=["email"])
        user.refresh_from_db()
        self.assertEqual(user.email, "contact-after@example.com")

    def test_user_email_update_syncs_profile_contact_email(self):
        user = get_user_model().objects.create_user(
            username="portal-email-sync-user",
            email="user-before@example.com",
            password="pass1234",
        )
        contact = self._create_contact(name="Association Sync User")
        AssociationProfile.objects.create(user=user, contact=contact)

        user.email = "user-after@example.com"
        user.save(update_fields=["email"])
        contact.refresh_from_db()
        self.assertEqual(contact.email, "user-after@example.com")
