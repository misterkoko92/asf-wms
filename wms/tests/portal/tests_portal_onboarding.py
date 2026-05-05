import importlib

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from contacts.models import Contact, ContactType
from wms import models as wms_models
from wms.models import (
    AssociationProfile,
    Destination,
    PortalAccessRole,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentValidationStatus,
)
from wms.portal_access import (
    PORTAL_SCOPE_SOURCE_GRANT,
    PORTAL_SCOPE_SOURCE_LEGACY_ASSOCIATION,
    PortalScope,
)


class PortalOnboardingPreferenceModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="portal-onboarding-user",
            email="portal-onboarding-user@example.org",
            password="pass1234",  # pragma: allowlist secret
        )
        self.shipper_contact = Contact.objects.create(
            name="Association Onboarding",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.shipper_referent = Contact.objects.create(
            name="Referent Onboarding",
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
        self.profile = AssociationProfile.objects.create(
            user=self.user,
            contact=self.shipper_contact,
        )
        correspondent = Contact.objects.create(
            name="Correspondent Onboarding",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=correspondent,
            is_active=True,
        )
        recipient_contact = Contact.objects.create(
            name="Recipient Onboarding",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=recipient_contact,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

    def test_shipper_preference_defaults_to_show_on_next_login(self):
        preference_model = getattr(wms_models, "PortalOnboardingPreference", None)
        self.assertIsNotNone(preference_model)

        preference = preference_model.objects.create(
            user=self.user,
            role=PortalAccessRole.SHIPPER_ADMIN,
            shipper=self.shipper,
        )

        self.assertTrue(preference.show_on_next_login)

    def test_recipient_preference_accepts_recipient_scope(self):
        preference_model = getattr(wms_models, "PortalOnboardingPreference", None)
        self.assertIsNotNone(preference_model)

        preference = preference_model(
            user=self.user,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=self.recipient_organization,
        )

        preference.full_clean()

    def test_legacy_shipper_preference_accepts_association_profile_scope(self):
        preference_model = getattr(wms_models, "PortalOnboardingPreference", None)
        self.assertIsNotNone(preference_model)

        preference = preference_model(
            user=self.user,
            role=PortalAccessRole.SHIPPER_ADMIN,
            association_profile=self.profile,
        )

        preference.full_clean()

    def test_preference_requires_exactly_one_scope_target(self):
        preference_model = getattr(wms_models, "PortalOnboardingPreference", None)
        self.assertIsNotNone(preference_model)

        with self.assertRaises(ValidationError):
            preference_model(
                user=self.user,
                role=PortalAccessRole.SHIPPER_ADMIN,
            ).full_clean()

        with self.assertRaises(ValidationError):
            preference_model(
                user=self.user,
                role=PortalAccessRole.SHIPPER_ADMIN,
                shipper=self.shipper,
                recipient_organization=self.recipient_organization,
            ).full_clean()

    def test_preference_scope_target_must_match_role(self):
        preference_model = getattr(wms_models, "PortalOnboardingPreference", None)
        self.assertIsNotNone(preference_model)

        with self.assertRaises(ValidationError):
            preference_model(
                user=self.user,
                role=PortalAccessRole.RECIPIENT_ADMIN,
                shipper=self.shipper,
            ).full_clean()

        with self.assertRaises(ValidationError):
            preference_model(
                user=self.user,
                role=PortalAccessRole.SHIPPER_ADMIN,
                recipient_organization=self.recipient_organization,
            ).full_clean()

    def test_duplicate_preference_is_rejected_for_same_user_role_and_scope(self):
        preference_model = getattr(wms_models, "PortalOnboardingPreference", None)
        self.assertIsNotNone(preference_model)

        preference_model.objects.create(
            user=self.user,
            role=PortalAccessRole.SHIPPER_ADMIN,
            shipper=self.shipper,
        )

        with self.assertRaises(ValidationError):
            preference_model(
                user=self.user,
                role=PortalAccessRole.SHIPPER_ADMIN,
                shipper=self.shipper,
            ).full_clean()


class PortalOnboardingHelperTests(PortalOnboardingPreferenceModelTests):
    def _load_onboarding_module(self):
        try:
            return importlib.import_module("wms.application.portal.onboarding")
        except ModuleNotFoundError as exc:
            self.fail(f"wms.application.portal.onboarding module missing: {exc}")

    def _build_request(self, scope):
        request = RequestFactory().get("/portal/")
        request.user = self.user
        request.portal_scope = scope
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        return request

    def _shipper_scope(self):
        return PortalScope(
            source=PORTAL_SCOPE_SOURCE_GRANT,
            role=PortalAccessRole.SHIPPER_ADMIN,
            shipper=self.shipper,
        )

    def _recipient_scope(self):
        return PortalScope(
            source=PORTAL_SCOPE_SOURCE_GRANT,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=self.recipient_organization,
        )

    def _legacy_scope(self):
        return PortalScope(
            source=PORTAL_SCOPE_SOURCE_LEGACY_ASSOCIATION,
            role=PortalAccessRole.SHIPPER_ADMIN,
            shipper=self.shipper,
            association_profile=self.profile,
        )

    def test_build_shipper_context_creates_default_preference_and_auto_opens(self):
        onboarding = self._load_onboarding_module()
        request = self._build_request(self._shipper_scope())

        context = onboarding.build_portal_onboarding_context(request)

        self.assertEqual(context["role"], PortalAccessRole.SHIPPER_ADMIN)
        self.assertTrue(context["auto_open"])
        self.assertTrue(context["show_on_next_login"])
        self.assertEqual(context["title"], "Tutoriel expéditeur")
        self.assertEqual(len(context["steps"]), 6)
        self.assertIn("demande d'expédition", context["steps"][3]["body"])
        self.assertTrue(
            wms_models.PortalOnboardingPreference.objects.filter(
                user=self.user,
                role=PortalAccessRole.SHIPPER_ADMIN,
                shipper=self.shipper,
                show_on_next_login=True,
            ).exists()
        )

    def test_build_recipient_context_uses_recipient_wizard(self):
        onboarding = self._load_onboarding_module()
        request = self._build_request(self._recipient_scope())

        context = onboarding.build_portal_onboarding_context(request)

        self.assertEqual(context["role"], PortalAccessRole.RECIPIENT_ADMIN)
        self.assertEqual(context["title"], "Tutoriel destinataire")
        self.assertEqual(len(context["steps"]), 5)
        self.assertIn("fiche structure", context["steps"][1]["title"].lower())

    def test_legacy_shipper_context_is_stored_on_association_profile_scope(self):
        onboarding = self._load_onboarding_module()
        request = self._build_request(self._legacy_scope())

        context = onboarding.build_portal_onboarding_context(request)

        self.assertTrue(context["auto_open"])
        self.assertTrue(
            wms_models.PortalOnboardingPreference.objects.filter(
                user=self.user,
                role=PortalAccessRole.SHIPPER_ADMIN,
                association_profile=self.profile,
            ).exists()
        )

    def test_mark_seen_suppresses_repeated_auto_open_only_for_current_session(self):
        onboarding = self._load_onboarding_module()
        request = self._build_request(self._shipper_scope())
        self.assertTrue(onboarding.build_portal_onboarding_context(request)["auto_open"])

        onboarding.mark_portal_onboarding_seen(request, show_on_next_login=True)

        same_session_context = onboarding.build_portal_onboarding_context(request)
        self.assertFalse(same_session_context["auto_open"])
        preference = wms_models.PortalOnboardingPreference.objects.get(
            user=self.user,
            role=PortalAccessRole.SHIPPER_ADMIN,
            shipper=self.shipper,
        )
        self.assertTrue(preference.show_on_next_login)
        self.assertIsNotNone(preference.last_seen_at)

        next_session_request = self._build_request(self._shipper_scope())
        next_session_context = onboarding.build_portal_onboarding_context(next_session_request)
        self.assertTrue(next_session_context["auto_open"])

    def test_unchecked_preference_disables_future_auto_open(self):
        onboarding = self._load_onboarding_module()
        request = self._build_request(self._recipient_scope())

        onboarding.mark_portal_onboarding_seen(request, show_on_next_login=False)

        next_session_request = self._build_request(self._recipient_scope())
        context = onboarding.build_portal_onboarding_context(next_session_request)
        self.assertFalse(context["auto_open"])
        self.assertFalse(context["show_on_next_login"])
