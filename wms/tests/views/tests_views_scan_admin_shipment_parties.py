import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)


class ScanAdminShipmentPartiesViewTests(TestCase):
    def _normalize_html(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="scan-shipment-parties-superuser",
            password="pass1234",
            email="scan-shipment-parties-superuser@example.com",
        )
        self.correspondent_org = Contact.objects.create(
            name="Correspondant Bamako",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=self.correspondent_org,
            is_active=True,
        )
        self.shipper_org = Contact.objects.create(
            name="Shipper Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.shipper_person = Contact.objects.create(
            name="Alice Shipper",
            first_name="Alice",
            last_name="Shipper",
            contact_type=ContactType.PERSON,
            organization=self.shipper_org,
            is_active=True,
        )
        self.shipper = ShipmentShipper.objects.create(
            organization=self.shipper_org,
            default_contact=self.shipper_person,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        self.recipient_org = Contact.objects.create(
            name="Hopital Bamako",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=self.recipient_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
            is_correspondent=True,
        )
        self.recipient_person = Contact.objects.create(
            name="Dr Truc",
            first_name="Dr",
            last_name="Truc",
            contact_type=ContactType.PERSON,
            organization=self.recipient_org,
            is_active=True,
        )
        self.recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=self.recipient_organization,
            contact=self.recipient_person,
            is_active=True,
        )
        self.link = ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipper,
            recipient_organization=self.recipient_organization,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=self.link,
            recipient_contact=self.recipient_contact,
            is_default=True,
            is_active=True,
        )

    def test_scan_admin_contacts_renders_shipment_party_cockpit(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_admin_contacts"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pilotage contacts expédition")
        self.assertContains(response, "Expéditeurs")
        self.assertContains(response, "Structures destinataires")
        self.assertContains(response, "Correspondants d'escale")
        self.assertContains(response, "Définir le référent destinataire par défaut")
        normalized_html = self._normalize_html(response.content.decode("utf-8"))
        self.assertIn(
            'name="action" value="set_default_authorized_recipient_contact"',
            normalized_html,
        )
        self.assertIn(
            'name="action" value="set_stopover_correspondent_recipient_organization"',
            normalized_html,
        )
        self.assertIn(
            'name="action" value="merge_shipment_recipient_organizations"',
            normalized_html,
        )
        self.assertEqual(response.context["cockpit_mode"], "shipment_parties")
        self.assertEqual(
            [shipper.id for shipper in response.context["cockpit_shipment_shippers"]],
            [self.shipper.id],
        )
        self.assertEqual(
            [
                recipient.id
                for recipient in response.context["cockpit_shipment_recipient_organizations"]
            ],
            [self.recipient_organization.id],
        )
        self.assertEqual(
            [link.id for link in response.context["cockpit_shipment_links"]],
            [self.link.id],
        )

    def test_admin_can_set_default_authorized_recipient_contact(self):
        self.client.force_login(self.superuser)
        other_person = Contact.objects.create(
            name="Dr Machin",
            first_name="Dr",
            last_name="Machin",
            contact_type=ContactType.PERSON,
            organization=self.recipient_org,
            is_active=True,
        )
        other_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=self.recipient_organization,
            contact=other_person,
            is_active=True,
        )
        other_authorization = ShipmentAuthorizedRecipientContact.objects.create(
            link=self.link,
            recipient_contact=other_recipient_contact,
            is_default=False,
            is_active=True,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "set_default_authorized_recipient_contact",
                "link_id": str(self.link.id),
                "recipient_contact_id": str(other_recipient_contact.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        other_authorization.refresh_from_db()
        default_authorization = ShipmentAuthorizedRecipientContact.objects.get(
            link=self.link,
            recipient_contact=self.recipient_contact,
        )
        self.assertTrue(other_authorization.is_default)
        self.assertFalse(default_authorization.is_default)

    def test_admin_can_switch_active_stopover_correspondent(self):
        self.client.force_login(self.superuser)
        other_org = Contact.objects.create(
            name="Hopital Secondaire",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        other_recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=other_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
            is_correspondent=False,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "set_stopover_correspondent_recipient_organization",
                "recipient_organization_id": str(other_recipient_organization.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.recipient_organization.refresh_from_db()
        other_recipient_organization.refresh_from_db()
        self.assertFalse(self.recipient_organization.is_correspondent)
        self.assertTrue(other_recipient_organization.is_correspondent)

    def test_admin_can_merge_recipient_structures(self):
        self.client.force_login(self.superuser)
        source_org = Contact.objects.create(
            name="Hopital Bamako Duplicate",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        source_recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=source_org,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
            is_correspondent=False,
        )
        source_person = Contact.objects.create(
            name="Dr Machin",
            first_name="Dr",
            last_name="Machin",
            contact_type=ContactType.PERSON,
            organization=source_org,
            is_active=True,
        )
        source_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=source_recipient_organization,
            contact=source_person,
            is_active=True,
        )
        source_link = ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipper,
            recipient_organization=source_recipient_organization,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=source_link,
            recipient_contact=source_recipient_contact,
            is_default=False,
            is_active=True,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "merge_shipment_recipient_organizations",
                "source_recipient_organization_id": str(source_recipient_organization.id),
                "target_recipient_organization_id": str(self.recipient_organization.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        source_recipient_organization.refresh_from_db()
        source_org.refresh_from_db()
        self.assertFalse(source_recipient_organization.is_active)
        self.assertFalse(source_org.is_active)
        migrated_contact = ShipmentRecipientContact.objects.get(contact=source_person)
        self.assertEqual(migrated_contact.recipient_organization_id, self.recipient_organization.id)
        self.assertEqual(migrated_contact.contact.organization_id, self.recipient_org.id)
        self.assertFalse(
            ShipmentShipperRecipientLink.objects.filter(pk=source_link.pk).exists()
        )
        self.assertTrue(
            ShipmentAuthorizedRecipientContact.objects.filter(
                link=self.link,
                recipient_contact=migrated_contact,
                is_active=True,
            ).exists()
        )
