from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactAddress, ContactType
from wms.application.portal.destination_options import list_served_destination_options
from wms.application.portal.readiness import (
    MISSING_ADMIN_CONTACT,
    MISSING_PREPARATION_CONTACT,
    MISSING_VALIDATED_RECIPIENT,
    build_shipper_readiness,
)
from wms.models import (
    AssociationPortalContact,
    AssociationProfile,
    Destination,
    ShipmentRecipientOrganization,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from wms.shipment_party_setup import ensure_shipment_shipper


class ServedDestinationOptionsTests(TestCase):
    def _create_correspondent(self, name: str, *, is_active: bool = True) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=is_active,
        )

    def _create_destination(
        self,
        *,
        city: str,
        iata_code: str,
        country: str,
        correspondent_is_active: bool = True,
        is_active: bool = True,
    ) -> Destination:
        correspondent = self._create_correspondent(
            f"Correspondant {iata_code}",
            is_active=correspondent_is_active,
        )
        return Destination.objects.create(
            city=city,
            iata_code=iata_code,
            country=country,
            correspondent_contact=correspondent,
            is_active=is_active,
        )

    def test_served_destination_options_include_only_active_destinations_with_active_correspondent(
        self,
    ):
        served = self._create_destination(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
        )
        self._create_destination(
            city="Dakar",
            iata_code="DKR",
            country="Senegal",
            is_active=False,
        )
        self._create_destination(
            city="Abidjan",
            iata_code="ABJ",
            country="Cote d'Ivoire",
            correspondent_is_active=False,
        )

        options = list_served_destination_options()

        self.assertEqual(
            options,
            [
                {
                    "id": served.id,
                    "label": str(served),
                    "country": "Mali",
                    "iata_code": "BKO",
                }
            ],
        )


class PortalShipperReadinessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="readiness-shipper",
            email="readiness-shipper@example.org",
            password="pass1234",  # pragma: allowlist secret
        )
        self.organization = Contact.objects.create(
            name="Association Readiness",
            contact_type=ContactType.ORGANIZATION,
            email=self.user.email,
            is_active=True,
        )
        ContactAddress.objects.create(
            contact=self.organization,
            address_line1="1 Rue Readiness",
            city="Paris",
            country="France",
            is_default=True,
        )
        self.profile = AssociationProfile.objects.create(
            user=self.user,
            contact=self.organization,
            must_change_password=False,
        )
        self.shipper = ensure_shipment_shipper(
            self.organization,
            validation_status=ShipmentValidationStatus.VALIDATED,
        )

    def _create_portal_contact(
        self,
        *,
        is_administrative: bool = False,
        is_shipping: bool = False,
        email: str = "ops@example.org",
        phone: str = "+33123456789",
        address_line1: str = "1 Rue Contact",
        city: str = "Paris",
        country: str = "France",
    ) -> AssociationPortalContact:
        return AssociationPortalContact.objects.create(
            profile=self.profile,
            title="mrs",
            first_name="Ada",
            last_name="LOVELACE",
            email=email,
            phone=phone,
            emails=email,
            phones=phone,
            address_line1=address_line1,
            city=city,
            country=country,
            is_administrative=is_administrative,
            is_shipping=is_shipping,
            is_active=True,
        )

    def _create_validated_recipient_link(self):
        correspondent = Contact.objects.create(
            name="Correspondant BKO",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=correspondent,
            is_active=True,
        )
        recipient_contact = Contact.objects.create(
            name="Hopital Bamako",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=recipient_contact,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        return ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipper,
            recipient_organization=recipient_organization,
            is_active=True,
        )

    def test_readiness_fails_without_complete_admin_contact(self):
        self._create_portal_contact(is_shipping=True)
        self._create_validated_recipient_link()

        readiness = build_shipper_readiness(self.profile)

        self.assertFalse(readiness.is_ready)
        self.assertIn(MISSING_ADMIN_CONTACT, readiness.missing_codes)

    def test_readiness_fails_without_complete_preparation_contact(self):
        self._create_portal_contact(is_administrative=True)
        self._create_validated_recipient_link()

        readiness = build_shipper_readiness(self.profile)

        self.assertFalse(readiness.is_ready)
        self.assertIn(MISSING_PREPARATION_CONTACT, readiness.missing_codes)

    def test_readiness_fails_without_validated_linked_recipient(self):
        self._create_portal_contact(is_administrative=True, is_shipping=True)

        readiness = build_shipper_readiness(self.profile)

        self.assertFalse(readiness.is_ready)
        self.assertIn(MISSING_VALIDATED_RECIPIENT, readiness.missing_codes)

    def test_readiness_fails_when_contact_address_is_incomplete(self):
        self._create_portal_contact(
            is_administrative=True,
            is_shipping=True,
            address_line1="",
        )
        self._create_validated_recipient_link()

        readiness = build_shipper_readiness(self.profile)

        self.assertFalse(readiness.is_ready)
        self.assertIn(MISSING_ADMIN_CONTACT, readiness.missing_codes)
        self.assertIn(MISSING_PREPARATION_CONTACT, readiness.missing_codes)

    def test_readiness_passes_with_complete_contacts_and_validated_linked_recipient(self):
        self._create_portal_contact(is_administrative=True, is_shipping=True)
        self._create_validated_recipient_link()

        readiness = build_shipper_readiness(self.profile)

        self.assertTrue(readiness.is_ready)
        self.assertEqual(readiness.missing_codes, [])
