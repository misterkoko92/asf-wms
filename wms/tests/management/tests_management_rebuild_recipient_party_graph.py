from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from contacts.capabilities import ContactCapabilityType, ensure_contact_capability
from contacts.models import Contact, ContactType
from wms.models import (
    AssociationProfile,
    AssociationRecipient,
    Destination,
    PortalAccessGrant,
    PortalAccessRole,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)


class RebuildRecipientPartyGraphCommandTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="recipient-graph-command-user",
            password="pass1234",  # pragma: allowlist secret
        )
        self.shipper_contact = Contact.objects.create(
            name="Command Association",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.shipper_referent = Contact.objects.create(
            name="Command Association Referent",
            first_name="Command",
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
        AssociationProfile.objects.create(
            user=self.user,
            contact=self.shipper_contact,
        )
        self.correspondent = Contact.objects.create(
            name="Recipient Graph Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.recipient_organization_contact = Contact.objects.create(
            name="Recipient Graph Structure",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.recipient_referent = Contact.objects.create(
            name="Recipient Graph Referent",
            first_name="Aicha",
            last_name="Diallo",
            email="aicha.diallo@example.org",
            phone="0102030405",
            contact_type=ContactType.PERSON,
            organization=self.recipient_organization_contact,
            is_active=True,
        )
        self.recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=self.recipient_organization_contact,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        self.shipment_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=self.recipient_organization,
            contact=self.recipient_referent,
            is_active=True,
        )
        self.shipper_link = ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipper,
            recipient_organization=self.recipient_organization,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=self.shipper_link,
            recipient_contact=self.shipment_recipient_contact,
            is_default=True,
            is_active=True,
        )
        self.legacy_projection = AssociationRecipient.objects.create(
            association_contact=self.shipper_contact,
            synced_contact=self.recipient_organization_contact,
            destination=self.destination,
            name="Legacy Recipient Graph",
            structure_name="Legacy Recipient Graph",
            address_line1="1 rue legacy",
            city="Paris",
            country="France",
        )
        self.unrelated_contact = Contact.objects.create(
            name="Unrelated Donor",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        ensure_contact_capability(self.unrelated_contact, ContactCapabilityType.DONOR)

    @mock.patch(
        "wms.management.commands.rebuild_recipient_party_graph.rebuild_recipient_party_graph"
    )
    def test_rebuild_recipient_party_graph_dry_run_reports_duplicates(self, rebuild_mock):
        rebuild_mock.return_value = {
            "mode": "DRY RUN",
            "recipient_organizations_scanned": 3,
            "duplicate_scopes": [
                {
                    "organization_id": 10,
                    "organization_name": "Hopital Test",
                    "destination_id": 5,
                    "destination_label": "Bamako (BKO) - Mali",
                    "recipient_organization_ids": [41, 42],
                }
            ],
            "recipient_organizations_merged": 0,
            "shipper_grants_created": 0,
            "recipient_grants_reassigned": 0,
            "legacy_projections_refreshed": 0,
        }
        stdout = StringIO()

        call_command("rebuild_recipient_party_graph", "--dry-run", stdout=stdout)

        rebuild_mock.assert_called_once_with(apply=False)
        output = stdout.getvalue()
        self.assertIn("Recipient party graph rebuild [DRY RUN]", output)
        self.assertIn("- Recipient organizations scanned: 3", output)
        self.assertIn("- Duplicate scopes: 1", output)
        self.assertIn("Hopital Test", output)
        self.assertIn("41, 42", output)

    def test_rebuild_recipient_party_graph_apply_rebuilds_grants_and_projections(self):
        stdout = StringIO()

        call_command("rebuild_recipient_party_graph", "--apply", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Recipient party graph rebuild [APPLY]", output)
        self.assertIn("- Shipper grants created: 1", output)
        self.assertIn("- Legacy projections refreshed: 1", output)
        self.assertTrue(
            PortalAccessGrant.objects.filter(
                user=self.user,
                role=PortalAccessRole.SHIPPER_ADMIN,
                shipper=self.shipper,
                is_active=True,
            ).exists()
        )
        self.legacy_projection.refresh_from_db()
        self.assertEqual(
            self.legacy_projection.synced_contact,
            self.recipient_organization_contact,
        )
        self.assertEqual(
            self.legacy_projection.structure_name,
            self.recipient_organization_contact.name,
        )
        self.assertTrue(
            self.unrelated_contact.capabilities.filter(
                capability=ContactCapabilityType.DONOR,
                is_active=True,
            ).exists()
        )
