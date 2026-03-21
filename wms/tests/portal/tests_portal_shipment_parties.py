from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactAddress, ContactType
from wms.models import (
    AssociationProfile,
    AssociationRecipient,
    Destination,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from wms.portal_recipient_sync import sync_association_recipient_to_contact


class PortalShipmentPartyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="portal-shipment-parties",
            email="portal-shipment-parties@example.org",
            password="pass1234",  # pragma: allowlist secret
        )
        self.association = Contact.objects.create(
            name="Association Portail",
            contact_type=ContactType.ORGANIZATION,
            email=self.user.email,
            is_active=True,
        )
        ContactAddress.objects.create(
            contact=self.association,
            address_line1="1 Rue Association",
            city="Paris",
            postal_code="75001",
            country="France",
            is_default=True,
        )
        self.profile = AssociationProfile.objects.create(
            user=self.user,
            contact=self.association,
            must_change_password=False,
        )
        self.client.force_login(self.user)
        self.recipients_url = reverse("portal:portal_recipients")
        self.order_create_url = reverse("portal:portal_order_create")
        self.destination = self._create_destination("BKO", city="Bamako", country="Mali")

    def _create_destination(self, iata_code: str, *, city: str, country: str) -> Destination:
        correspondent = Contact.objects.create(
            name=f"Correspondant {iata_code}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        return Destination.objects.create(
            city=city,
            iata_code=iata_code,
            country=country,
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_shipper(self, name: str) -> ShipmentShipper:
        organization = Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        default_contact = Contact.objects.create(
            name=f"Referent {name}",
            first_name="Referent",
            last_name=name,
            contact_type=ContactType.PERSON,
            organization=organization,
            is_active=True,
        )
        return ShipmentShipper.objects.create(
            organization=organization,
            default_contact=default_contact,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

    def _create_portal_recipient(
        self, *, structure_name: str, email: str, first_name: str, last_name: str
    ):
        return AssociationRecipient.objects.create(
            association_contact=self.association,
            destination=self.destination,
            name=structure_name,
            structure_name=structure_name,
            contact_title="dr",
            contact_first_name=first_name,
            contact_last_name=last_name,
            emails=email,
            email=email,
            phones="+22370000000",
            phone="+22370000000",
            address_line1="Hopital Point G",
            postal_code="BP 333",
            city=self.destination.city,
            country=self.destination.country,
            is_delivery_contact=True,
            is_active=True,
        )

    def test_portal_adds_authorized_contact_to_existing_recipient_structure(self):
        existing_shipper = self._create_shipper("MSF")
        shared_org = Contact.objects.create(
            name="Hopital de Bamako",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ContactAddress.objects.create(
            contact=shared_org,
            address_line1="Ancienne adresse",
            city=self.destination.city,
            country=self.destination.country,
            is_default=True,
        )
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=shared_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        shared_person = Contact.objects.create(
            name="Dr Truc",
            first_name="Dr",
            last_name="Truc",
            email="dr.truc@example.org",
            contact_type=ContactType.PERSON,
            organization=shared_org,
            is_active=True,
        )
        recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_org,
            contact=shared_person,
            is_active=True,
        )
        existing_link = ShipmentShipperRecipientLink.objects.create(
            shipper=existing_shipper,
            recipient_organization=recipient_org,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=existing_link,
            recipient_contact=recipient_contact,
            is_default=True,
            is_active=True,
        )

        recipient = self._create_portal_recipient(
            structure_name="Hopital de Bamako",
            email="dr.truc@example.org",
            first_name="Dr",
            last_name="Truc",
        )

        synced_contact = sync_association_recipient_to_contact(recipient)

        self.assertEqual(synced_contact.id, shared_org.id)
        self.assertEqual(ShipmentRecipientOrganization.objects.count(), 1)
        self.assertEqual(ShipmentRecipientContact.objects.count(), 1)

        shipper = ShipmentShipper.objects.get(organization=self.association)
        link = ShipmentShipperRecipientLink.objects.get(
            shipper=shipper,
            recipient_organization=recipient_org,
        )
        authorized = ShipmentAuthorizedRecipientContact.objects.get(
            link=link,
            recipient_contact=recipient_contact,
        )
        self.assertTrue(authorized.is_active)
        self.assertTrue(authorized.is_default)
        self.assertEqual(
            ShipmentAuthorizedRecipientContact.objects.filter(
                recipient_contact=recipient_contact,
                is_active=True,
            ).count(),
            2,
        )

    def test_portal_sync_preserves_validated_status_on_existing_structure_update(self):
        shared_org = Contact.objects.create(
            name="Hopital de Bamako",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ContactAddress.objects.create(
            contact=shared_org,
            address_line1="Ancienne adresse",
            city="Bamako",
            country="Mali",
            is_default=True,
        )
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=shared_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

        recipient = self._create_portal_recipient(
            structure_name="Hopital de Bamako",
            email="dr.martin@example.org",
            first_name="Claire",
            last_name="Martin",
        )
        recipient.address_line1 = "Nouvelle adresse"
        recipient.city = "Bamako Centre"
        recipient.save(update_fields=["address_line1", "city"])

        sync_association_recipient_to_contact(recipient)
        recipient_org.refresh_from_db()

        self.assertEqual(recipient_org.validation_status, ShipmentValidationStatus.VALIDATED)
        self.assertEqual(
            recipient_org.organization.addresses.get(is_default=True).address_line1,
            "Nouvelle adresse",
        )
        self.assertEqual(
            recipient_org.organization.addresses.get(is_default=True).city,
            "Bamako Centre",
        )

    def test_portal_recipients_expose_duplicate_shared_structures(self):
        shared_org = Contact.objects.create(
            name="Hopital de Bamako",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=shared_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

        response = self.client.post(
            self.recipients_url,
            {
                "action": "create_recipient",
                "destination_id": str(self.destination.id),
                "structure_name": "Hopital de Bamako",
                "contact_title": "dr",
                "contact_last_name": "Martin",
                "contact_first_name": "Claire",
                "emails": "claire.martin@example.org",
                "phones": "+22371111111",
                "address_line1": "",
                "city": "Bamako",
                "country": "Mali",
            },
        )

        self.assertEqual(response.status_code, 200)
        suggestions = response.context["duplicate_recipient_suggestions"]
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["name"], "Hopital de Bamako")
        self.assertEqual(suggestions[0]["validation_status"], ShipmentValidationStatus.VALIDATED)

    def test_portal_can_create_duplicate_structure_when_reuse_is_disabled(self):
        shared_org = Contact.objects.create(
            name="Hopital de Bamako",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ContactAddress.objects.create(
            contact=shared_org,
            address_line1="Adresse partagee",
            city="Bamako",
            country="Mali",
            is_default=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=shared_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

        response = self.client.post(
            self.recipients_url,
            {
                "action": "create_recipient",
                "destination_id": str(self.destination.id),
                "structure_name": "Hopital de Bamako",
                "contact_title": "dr",
                "contact_last_name": "Martin",
                "contact_first_name": "Claire",
                "emails": "claire.martin@example.org",
                "phones": "+22371111111",
                "address_line1": "Adresse locale",
                "city": "Bamako",
                "country": "Mali",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            ShipmentRecipientOrganization.objects.filter(
                destination=self.destination,
                organization__name="Hopital de Bamako",
            ).count(),
            2,
        )

    def test_portal_order_create_reads_allowed_destinations_from_shipment_parties(self):
        shared_org = Contact.objects.create(
            name="Hopital de Bamako",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=shared_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        recipient = self._create_portal_recipient(
            structure_name="Hopital de Bamako",
            email="claire.martin@example.org",
            first_name="Claire",
            last_name="Martin",
        )

        response = self.client.get(self.order_create_url)

        self.assertEqual(response.status_code, 200)
        options_by_id = {
            str(option["id"]): option
            for option in response.context["recipient_options_all"]
            if option["id"] != "self"
        }
        self.assertEqual(
            options_by_id[str(recipient.id)]["allowed_destination_ids"],
            [self.destination.id],
        )
        self.assertIn("Claire MARTIN", options_by_id[str(recipient.id)]["label"])
        self.assertIn("Hopital de Bamako", options_by_id[str(recipient.id)]["label"])
