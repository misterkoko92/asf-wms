from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    CartonSequence,
    Destination,
    Location,
    PlanningDestinationRule,
    PlanningParameterSet,
    ReceiptDonorSequence,
    Warehouse,
    WmsRuntimeSettings,
)


class ResetOperationalDataCommandTests(TestCase):
    def setUp(self):
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
        self.destination = Destination.objects.create(
            city="Paris",
            iata_code="CDG",
            country="France",
            correspondent_contact=self.correspondent,
            is_active=True,
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

    def test_dry_run_reports_deleted_and_preserved_models_without_writing(self):
        stdout = StringIO()

        call_command("reset_operational_data", "--dry-run", stdout=stdout)

        self.assertIn("DRY RUN", stdout.getvalue())
        self.assertTrue(Contact.objects.filter(pk=self.correspondent.pk).exists())
        self.assertTrue(Destination.objects.filter(pk=self.destination.pk).exists())
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
        self.assertFalse(PlanningDestinationRule.objects.exists())
        self.assertFalse(ReceiptDonorSequence.objects.exists())
        self.assertFalse(CartonSequence.objects.exists())
        self.assertTrue(Warehouse.objects.filter(pk=self.warehouse.pk).exists())
        self.assertTrue(Location.objects.filter(pk=self.location.pk).exists())
        self.assertTrue(WmsRuntimeSettings.objects.filter(pk=self.runtime_settings.pk).exists())
        self.assertTrue(PlanningParameterSet.objects.filter(pk=self.parameter_set.pk).exists())
