import importlib

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationProfile,
    AssociationRecipient,
    Destination,
    PortalAccessGrant,
    PortalAccessRole,
    ShipmentRecipientOrganization,
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

    def test_association_required_redirects_to_scope_select_when_multiple_scopes_exist(self):
        user = get_user_model().objects.create_user(
            username="portal-multi-scope-user",
            email="portal-multi-scope-user@example.com",
            password="pass1234",
        )
        shipper_contact = self._create_contact(name="Association Multi Scope")
        referent = Contact.objects.create(
            name="Association Multi Scope Referent",
            first_name="Multi",
            last_name="Referent",
            contact_type=ContactType.PERSON,
            organization=shipper_contact,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=shipper_contact,
            default_contact=referent,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=Contact.objects.create(
                name="Association Multi Scope Correspondent",
                contact_type=ContactType.PERSON,
                is_active=True,
            ),
            is_active=True,
        )
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=self._create_contact(name="Association Multi Scope Recipient"),
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        PortalAccessGrant.objects.create(
            user=user,
            role=PortalAccessRole.SHIPPER_ADMIN,
            shipper=shipper,
        )
        PortalAccessGrant.objects.create(
            user=user,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=recipient_org,
        )
        view_permissions = importlib.import_module("wms.view_permissions")

        @view_permissions.association_required
        def sample_view(request):
            return HttpResponse("ok")

        request = RequestFactory().get("/portal/orders/")
        request.user = user
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()

        response = sample_view(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/scope-select/", response.url)

    def test_bind_association_profile_creates_bridge_profile_for_shipper_grant_without_legacy_profile(
        self,
    ):
        user = get_user_model().objects.create_user(
            username="portal-grant-no-profile-user",
            email="portal-grant-no-profile-user@example.com",
            password="pass1234",
        )
        contact = self._create_contact(name="Association Grant No Profile")
        referent = Contact.objects.create(
            name="Association Grant No Profile Referent",
            first_name="Grant",
            last_name="Referent",
            contact_type=ContactType.PERSON,
            organization=contact,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=contact,
            default_contact=referent,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Dakar",
            iata_code="DKR",
            country="Senegal",
            correspondent_contact=Contact.objects.create(
                name="Association Grant No Profile Correspondent",
                contact_type=ContactType.PERSON,
                is_active=True,
            ),
            is_active=True,
        )
        AssociationRecipient.objects.create(
            association_contact=contact,
            destination=destination,
            name="Association Grant No Profile Delivery",
            structure_name="Association Grant No Profile Delivery",
            is_delivery_contact=True,
            is_active=True,
        )
        PortalAccessGrant.objects.create(
            user=user,
            role=PortalAccessRole.SHIPPER_ADMIN,
            shipper=shipper,
        )
        view_permissions = importlib.import_module("wms.view_permissions")

        request = RequestFactory().get("/portal/orders/")
        request.user = user
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        portal_access = importlib.import_module("wms.portal_access")
        request.portal_scope = portal_access.PortalScope(
            source=portal_access.PORTAL_SCOPE_SOURCE_GRANT,
            role=PortalAccessRole.SHIPPER_ADMIN,
            grant=PortalAccessGrant.objects.get(user=user, shipper=shipper),
            shipper=shipper,
        )

        response = view_permissions._bind_association_profile(request)

        self.assertIsNone(response)
        self.assertEqual(request.association_profile.contact, contact)
        self.assertEqual(request.association_profile.user, user)
        self.assertTrue(AssociationProfile.objects.filter(user=user, contact=contact).exists())

    def test_bind_association_profile_returns_scope_select_redirect_when_scope_is_ambiguous(self):
        user = get_user_model().objects.create_user(
            username="portal-bind-ambiguous-user",
            email="portal-bind-ambiguous-user@example.com",
            password="pass1234",
        )
        shipper_contact = self._create_contact(name="Association Bind Ambiguous")
        referent = Contact.objects.create(
            name="Association Bind Ambiguous Referent",
            first_name="Bind",
            last_name="Referent",
            contact_type=ContactType.PERSON,
            organization=shipper_contact,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=shipper_contact,
            default_contact=referent,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Kayes",
            iata_code="KYS",
            country="Mali",
            correspondent_contact=Contact.objects.create(
                name="Association Bind Ambiguous Correspondent",
                contact_type=ContactType.PERSON,
                is_active=True,
            ),
            is_active=True,
        )
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=self._create_contact(name="Association Bind Ambiguous Recipient"),
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        PortalAccessGrant.objects.create(
            user=user,
            role=PortalAccessRole.SHIPPER_ADMIN,
            shipper=shipper,
        )
        PortalAccessGrant.objects.create(
            user=user,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=recipient_org,
        )
        view_permissions = importlib.import_module("wms.view_permissions")

        request = RequestFactory().get("/portal/orders/")
        request.user = user
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()

        response = view_permissions._bind_association_profile(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/scope-select/", response.url)
