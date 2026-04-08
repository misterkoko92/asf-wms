import importlib

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from contacts.models import Contact, ContactType
from wms import models as wms_models
from wms.models import (
    Destination,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentValidationStatus,
)


class PortalAccessGrantTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="portal-access-user",
            email="portal-access-user@example.org",
            password="pass1234",  # pragma: allowlist secret
        )
        self.other_user = user_model.objects.create_user(
            username="portal-access-other",
            email="portal-access-other@example.org",
            password="pass1234",  # pragma: allowlist secret
        )
        self.shipper_contact = Contact.objects.create(
            name="Portal Shipper",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.shipper_referent = Contact.objects.create(
            name="Portal Shipper Referent",
            first_name="Portal",
            last_name="Referent",
            contact_type=ContactType.PERSON,
            organization=self.shipper_contact,
            is_active=True,
        )
        self.shipper = ShipmentShipper.objects.create(
            organization=self.shipper_contact,
            default_contact=self.shipper_referent,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        correspondent = Contact.objects.create(
            name="Portal Correspondent",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=correspondent,
            is_active=True,
        )
        self.recipient_contact = Contact.objects.create(
            name="Portal Recipient",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=self.recipient_contact,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

    def _build_request(self, user):
        request = RequestFactory().get("/")
        request.user = user
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        return request

    def _load_portal_access_module(self):
        try:
            return importlib.import_module("wms.portal_access")
        except ModuleNotFoundError as exc:
            self.fail(f"wms.portal_access module missing: {exc}")

    def test_wms_model_facade_exports_portal_access_grant(self):
        self.assertTrue(hasattr(wms_models, "PortalAccessGrant"))
        self.assertTrue(hasattr(wms_models, "PortalAccessRole"))

    def test_portal_access_grant_requires_exactly_one_scope(self):
        grant_model = getattr(wms_models, "PortalAccessGrant", None)
        role_enum = getattr(wms_models, "PortalAccessRole", None)

        self.assertIsNotNone(grant_model)
        self.assertIsNotNone(role_enum)

        with self.assertRaises(ValidationError):
            grant_model(
                user=self.user,
                role=role_enum.SHIPPER_ADMIN,
            ).full_clean()

        with self.assertRaises(ValidationError):
            grant_model(
                user=self.user,
                role=role_enum.SHIPPER_ADMIN,
                shipper=self.shipper,
                recipient_organization=self.recipient_organization,
            ).full_clean()

        grant = grant_model(
            user=self.user,
            role=role_enum.RECIPIENT_ADMIN,
            recipient_organization=self.recipient_organization,
        )
        grant.full_clean()

    def test_list_user_portal_scopes_returns_multiple_explicit_active_grants(self):
        grant_model = getattr(wms_models, "PortalAccessGrant", None)
        role_enum = getattr(wms_models, "PortalAccessRole", None)
        self.assertIsNotNone(grant_model)
        self.assertIsNotNone(role_enum)

        shipper_grant = grant_model.objects.create(
            user=self.user,
            role=role_enum.SHIPPER_ADMIN,
            shipper=self.shipper,
        )
        recipient_grant = grant_model.objects.create(
            user=self.user,
            role=role_enum.RECIPIENT_ADMIN,
            recipient_organization=self.recipient_organization,
        )

        portal_access = self._load_portal_access_module()
        scopes = portal_access.list_user_portal_scopes(self.user)

        self.assertEqual(len(scopes), 2)
        self.assertEqual(
            {scope.grant.id for scope in scopes}, {shipper_grant.id, recipient_grant.id}
        )
        self.assertEqual(
            {scope.role for scope in scopes},
            {role_enum.SHIPPER_ADMIN, role_enum.RECIPIENT_ADMIN},
        )

    def test_list_user_portal_scopes_falls_back_to_legacy_association_profile(self):
        profile = wms_models.AssociationProfile.objects.create(
            user=self.user,
            contact=self.shipper_contact,
        )

        portal_access = self._load_portal_access_module()
        scopes = portal_access.list_user_portal_scopes(self.user)

        self.assertEqual(len(scopes), 1)
        self.assertEqual(scopes[0].source, portal_access.PORTAL_SCOPE_SOURCE_LEGACY_ASSOCIATION)
        self.assertEqual(scopes[0].association_profile, profile)
        self.assertEqual(scopes[0].shipper, self.shipper)

    def test_resolve_active_portal_scope_ignores_inactive_grant_in_session(self):
        grant_model = getattr(wms_models, "PortalAccessGrant", None)
        role_enum = getattr(wms_models, "PortalAccessRole", None)
        self.assertIsNotNone(grant_model)
        self.assertIsNotNone(role_enum)

        inactive_grant = grant_model.objects.create(
            user=self.user,
            role=role_enum.RECIPIENT_ADMIN,
            recipient_organization=self.recipient_organization,
            is_active=False,
        )
        request = self._build_request(self.user)

        portal_access = self._load_portal_access_module()
        request.session[portal_access.ACTIVE_PORTAL_SCOPE_SESSION_KEY] = {
            "source": portal_access.PORTAL_SCOPE_SOURCE_GRANT,
            "grant_id": inactive_grant.id,
        }

        self.assertIsNone(portal_access.resolve_active_portal_scope(request))

    def test_activate_portal_scope_persists_explicit_grant_for_request_user(self):
        grant_model = getattr(wms_models, "PortalAccessGrant", None)
        role_enum = getattr(wms_models, "PortalAccessRole", None)
        self.assertIsNotNone(grant_model)
        self.assertIsNotNone(role_enum)

        grant = grant_model.objects.create(
            user=self.user,
            role=role_enum.RECIPIENT_ADMIN,
            recipient_organization=self.recipient_organization,
        )
        request = self._build_request(self.user)
        portal_access = self._load_portal_access_module()

        scope = portal_access.list_user_portal_scopes(self.user)[0]
        portal_access.activate_portal_scope(request, scope=scope)
        resolved_scope = portal_access.resolve_active_portal_scope(request)

        self.assertIsNotNone(resolved_scope)
        self.assertEqual(resolved_scope.grant, grant)
        self.assertEqual(resolved_scope.recipient_organization, self.recipient_organization)
