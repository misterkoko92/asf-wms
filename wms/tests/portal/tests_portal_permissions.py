import importlib

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationProfile,
    PortalAccessRole,
    ShipmentShipper,
    ShipmentValidationStatus,
)
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

    def test_assign_association_portal_group_ignores_unsaved_user(self):
        unsaved_user = get_user_model()(username="unsaved-portal-user")
        before_count = Group.objects.filter(name=ASSOCIATION_PORTAL_GROUP_NAME).count()

        assign_association_portal_group(unsaved_user, sync_permissions=True)

        self.assertEqual(
            Group.objects.filter(name=ASSOCIATION_PORTAL_GROUP_NAME).count(),
            before_count,
        )

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

    def test_association_profile_without_grant_still_resolves_legacy_shipper_scope(self):
        user = get_user_model().objects.create_user(
            username="portal-legacy-scope-user",
            email="portal-legacy-scope-user@example.com",
            password="pass1234",
        )
        contact = self._create_contact(name="Association Legacy Scope")
        referent = Contact.objects.create(
            name="Association Legacy Scope Referent",
            first_name="Legacy",
            last_name="Referent",
            contact_type=ContactType.PERSON,
            organization=contact,
            is_active=True,
        )
        profile = AssociationProfile.objects.create(user=user, contact=contact)
        shipper = ShipmentShipper.objects.create(
            organization=contact,
            default_contact=referent,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

        portal_access = importlib.import_module("wms.portal_access")
        scopes = portal_access.list_user_portal_scopes(user)

        self.assertEqual(len(scopes), 1)
        self.assertEqual(scopes[0].association_profile, profile)
        self.assertEqual(scopes[0].shipper, shipper)

    def test_association_profile_without_runtime_shipper_can_bind_legacy_portal_scope(self):
        user = get_user_model().objects.create_user(
            username="portal-legacy-noshipper-user",
            email="portal-legacy-noshipper-user@example.com",
            password="pass1234",
        )
        contact = self._create_contact(name="Association Legacy No Shipper")
        profile = AssociationProfile.objects.create(user=user, contact=contact)
        portal_access = importlib.import_module("wms.portal_access")
        view_permissions = importlib.import_module("wms.view_permissions")

        request = RequestFactory().get("/portal/recipients/")
        request.user = user
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        request.portal_scope = portal_access.list_user_portal_scopes(user)[0]

        response = view_permissions._bind_association_profile(request)

        self.assertIsNone(response)
        self.assertEqual(request.association_profile, profile)
        self.assertIsNone(request.portal_scope.shipper)

    def test_bind_association_profile_rejects_explicit_shipper_scope_without_shipper(self):
        user = get_user_model().objects.create_user(
            username="portal-invalid-explicit-scope-user",
            email="portal-invalid-explicit-scope-user@example.com",
            password="pass1234",
        )
        contact = self._create_contact(name="Association Invalid Explicit Scope")
        AssociationProfile.objects.create(user=user, contact=contact)
        portal_access = importlib.import_module("wms.portal_access")
        view_permissions = importlib.import_module("wms.view_permissions")

        request = RequestFactory().get("/portal/recipients/")
        request.user = user
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        request.portal_scope = portal_access.PortalScope(
            source=portal_access.PORTAL_SCOPE_SOURCE_GRANT,
            role=PortalAccessRole.SHIPPER_ADMIN,
            shipper=None,
            association_profile=None,
        )

        with self.assertRaises(PermissionDenied):
            view_permissions._bind_association_profile(request)
