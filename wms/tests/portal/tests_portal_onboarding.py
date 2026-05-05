from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

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
