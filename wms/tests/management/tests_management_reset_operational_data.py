from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationPortalContact,
    AssociationProfile,
    AssociationRecipient,
    CartonSequence,
    Destination,
    Location,
    OrganizationRole,
    OrganizationRoleAssignment,
    PlanningDestinationRule,
    PlanningParameterSet,
    PublicAccountRequest,
    ReceiptDonorSequence,
    RecipientBinding,
    ShipperScope,
    Warehouse,
    WmsRuntimeSettings,
)


class ResetOperationalDataCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="association-test",
            email="association@example.com",
        )
        self.warehouse = Warehouse.objects.create(name="Main Warehouse")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="1",
            shelf="1",
        )
        self.runtime_settings, _ = WmsRuntimeSettings.objects.get_or_create(pk=1)
        self.correspondent = Contact.objects.create(
            name="Correspondent A",
            contact_type=ContactType.ORGANIZATION,
        )
        self.association = Contact.objects.create(
            name="Association A",
            contact_type=ContactType.ORGANIZATION,
            email="association@example.com",
        )
        self.destination = Destination.objects.create(
            city="Paris",
            iata_code="CDG",
            country="France",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.recipient = Contact.objects.create(
            name="Recipient A",
            contact_type=ContactType.ORGANIZATION,
            email="recipient@example.com",
        )
        self.donor = Contact.objects.create(
            name="Donor A",
            contact_type=ContactType.ORGANIZATION,
        )
        self.receipt_donor_sequence = ReceiptDonorSequence.objects.create(
            year=2026,
            donor=self.donor,
            last_number=3,
        )
        self.carton_sequence = CartonSequence.objects.create(
            family="MM",
            last_number=7,
        )
        self.parameter_set = PlanningParameterSet.objects.create(name="Main Planning Set")
        self.destination_rule = PlanningDestinationRule.objects.create(
            parameter_set=self.parameter_set,
            destination=self.destination,
            label="CDG Rule",
            is_active=True,
        )
        self.profile = AssociationProfile.objects.create(
            user=self.user,
            contact=self.association,
        )
        self.portal_contact = AssociationPortalContact.objects.create(
            profile=self.profile,
            first_name="Alice",
            last_name="Admin",
            email="alice@example.com",
            is_administrative=True,
        )
        self.association_recipient = AssociationRecipient.objects.create(
            association_contact=self.association,
            destination=self.destination,
            name="Association Recipient",
            address_line1="1 rue de Paris",
            city="Paris",
            country="France",
        )
        self.public_account_request = PublicAccountRequest.objects.create(
            contact=self.association,
            association_name="Association A",
            email="association@example.com",
            address_line1="1 rue de Paris",
            city="Paris",
            country="France",
        )
        self.shipper_assignment = OrganizationRoleAssignment.objects.create(
            organization=self.association,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        self.recipient_assignment = OrganizationRoleAssignment.objects.create(
            organization=self.recipient,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )
        self.shipper_scope = ShipperScope.objects.create(
            role_assignment=self.shipper_assignment,
            destination=self.destination,
            all_destinations=False,
            is_active=True,
        )
        self.recipient_binding = RecipientBinding.objects.create(
            shipper_org=self.association,
            recipient_org=self.recipient,
            destination=self.destination,
            is_active=True,
        )

    def test_dry_run_reports_deleted_and_preserved_models_without_writing(self):
        stdout = StringIO()

        call_command("reset_operational_data", "--dry-run", stdout=stdout)

        self.assertIn("DRY RUN", stdout.getvalue())
        self.assertTrue(Contact.objects.filter(pk=self.correspondent.pk).exists())
        self.assertTrue(Destination.objects.filter(pk=self.destination.pk).exists())
        self.assertTrue(AssociationProfile.objects.filter(pk=self.profile.pk).exists())
        self.assertTrue(AssociationPortalContact.objects.filter(pk=self.portal_contact.pk).exists())
        self.assertTrue(
            AssociationRecipient.objects.filter(pk=self.association_recipient.pk).exists()
        )
        self.assertTrue(
            PublicAccountRequest.objects.filter(pk=self.public_account_request.pk).exists()
        )
        self.assertTrue(
            OrganizationRoleAssignment.objects.filter(pk=self.shipper_assignment.pk).exists()
        )
        self.assertTrue(ShipperScope.objects.filter(pk=self.shipper_scope.pk).exists())
        self.assertTrue(RecipientBinding.objects.filter(pk=self.recipient_binding.pk).exists())
        self.assertTrue(
            PlanningDestinationRule.objects.filter(pk=self.destination_rule.pk).exists()
        )
        self.assertTrue(
            ReceiptDonorSequence.objects.filter(pk=self.receipt_donor_sequence.pk).exists()
        )
        self.assertTrue(CartonSequence.objects.filter(pk=self.carton_sequence.pk).exists())
        self.assertTrue(Warehouse.objects.filter(pk=self.warehouse.pk).exists())
        self.assertTrue(Location.objects.filter(pk=self.location.pk).exists())
        self.assertTrue(WmsRuntimeSettings.objects.filter(pk=self.runtime_settings.pk).exists())
        self.assertTrue(PlanningParameterSet.objects.filter(pk=self.parameter_set.pk).exists())

    def test_apply_deletes_operational_models_and_preserves_reference_models(self):
        stdout = StringIO()

        call_command("reset_operational_data", "--apply", stdout=stdout)

        self.assertIn("APPLY", stdout.getvalue())
        self.assertFalse(Contact.objects.exists())
        self.assertFalse(Destination.objects.exists())
        self.assertFalse(AssociationProfile.objects.exists())
        self.assertFalse(AssociationPortalContact.objects.exists())
        self.assertFalse(AssociationRecipient.objects.exists())
        self.assertFalse(PublicAccountRequest.objects.exists())
        self.assertFalse(OrganizationRoleAssignment.objects.exists())
        self.assertFalse(ShipperScope.objects.exists())
        self.assertFalse(RecipientBinding.objects.exists())
        self.assertFalse(PlanningDestinationRule.objects.exists())
        self.assertFalse(ReceiptDonorSequence.objects.exists())
        self.assertFalse(CartonSequence.objects.exists())
        self.assertTrue(Warehouse.objects.filter(pk=self.warehouse.pk).exists())
        self.assertTrue(Location.objects.filter(pk=self.location.pk).exists())
        self.assertTrue(WmsRuntimeSettings.objects.filter(pk=self.runtime_settings.pk).exists())
        self.assertTrue(PlanningParameterSet.objects.filter(pk=self.parameter_set.pk).exists())
