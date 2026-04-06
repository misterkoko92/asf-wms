from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    PreparationParameterSet,
    PreparationRun,
    PreparationRunNeedSnapshot,
    PreparationRunStatus,
    RecurringPreparationNeed,
    RecurringPreparationPeriodUnit,
    ShipmentRecipientOrganization,
    ShipmentShipper,
)
from wms.preparation.needs import (
    override_preparation_need_snapshot,
    snapshot_active_recurring_needs,
)


class PreparationNeedSnapshotTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="prep-needs@example.com",
            email="prep-needs@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.parameter_set = PreparationParameterSet.objects.create(
            name="Run magasin W16",
            created_by=self.user,
        )
        self.shipper_contact = Contact.objects.create(
            name="Association Source",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.shipper = ShipmentShipper.objects.create(
            organization=self.shipper_contact,
            default_contact=Contact.objects.create(
                first_name="Alice",
                last_name="Source",
                email="alice.source@example.com",
                organization=self.shipper_contact,
                contact_type=ContactType.PERSON,
                is_active=True,
            ),
            validation_status="validated",
        )
        self.recipient_contact = Contact.objects.create(
            name="Association Destinataire",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.correspondent = Contact.objects.create(
            first_name="Corinne",
            last_name="Dest",
            email="corinne.dest@example.com",
            organization=self.recipient_contact,
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="CI",
            correspondent_contact=self.correspondent,
        )
        self.recipient = ShipmentRecipientOrganization.objects.create(
            organization=self.recipient_contact,
            destination=self.destination,
            validation_status="validated",
        )
        self.run = PreparationRun.objects.create(
            parameter_set=self.parameter_set,
            created_by=self.user,
            target_equivalent_units=30,
            target_shipment_count=3,
            target_shipment_size_units=10,
            flight_window_start=date(2026, 4, 13),
            flight_window_end=date(2026, 4, 20),
            status=PreparationRunStatus.DRAFT,
        )

    def test_snapshot_active_recurring_needs_copies_only_active_rows(self):
        active_need = RecurringPreparationNeed.objects.create(
            shipper=self.shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            period_unit=RecurringPreparationPeriodUnit.WEEK,
            target_equivalent_units=12,
            is_active=True,
            created_by=self.user,
        )
        other_shipper_contact = Contact.objects.create(
            name="Association Inactive",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        other_shipper = ShipmentShipper.objects.create(
            organization=other_shipper_contact,
            default_contact=Contact.objects.create(
                first_name="Bob",
                last_name="Source",
                email="bob.source@example.com",
                organization=other_shipper_contact,
                contact_type=ContactType.PERSON,
                is_active=True,
            ),
            validation_status="validated",
        )
        inactive_need = RecurringPreparationNeed.objects.create(
            shipper=other_shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            period_unit=RecurringPreparationPeriodUnit.WEEK,
            target_equivalent_units=7,
            is_active=False,
            created_by=self.user,
        )

        snapshots = snapshot_active_recurring_needs(run=self.run)

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].recurring_need, active_need)
        self.assertFalse(
            PreparationRunNeedSnapshot.objects.filter(
                run=self.run,
                recurring_need=inactive_need,
            ).exists()
        )

    def test_snapshot_stays_frozen_when_recurring_need_changes_later(self):
        need = RecurringPreparationNeed.objects.create(
            shipper=self.shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            period_unit=RecurringPreparationPeriodUnit.WEEK,
            target_equivalent_units=14,
            is_active=True,
            created_by=self.user,
        )

        snapshot = snapshot_active_recurring_needs(run=self.run)[0]
        need.target_equivalent_units = 30
        need.save(update_fields=["target_equivalent_units"])
        snapshot.refresh_from_db()

        self.assertEqual(snapshot.recurring_need, need)
        self.assertEqual(snapshot.target_equivalent_units, 14)

    def test_run_local_override_updates_only_the_snapshot(self):
        need = RecurringPreparationNeed.objects.create(
            shipper=self.shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            period_unit=RecurringPreparationPeriodUnit.WEEK,
            target_equivalent_units=10,
            is_active=True,
            created_by=self.user,
        )

        snapshot = snapshot_active_recurring_needs(run=self.run)[0]
        override_preparation_need_snapshot(
            snapshot,
            target_equivalent_units=6,
        )
        need.refresh_from_db()
        snapshot.refresh_from_db()

        self.assertEqual(need.target_equivalent_units, 10)
        self.assertEqual(snapshot.target_equivalent_units, 6)
        self.assertEqual(snapshot.snapshot_payload["override"]["target_equivalent_units"], 6)

    def test_period_override_and_noop_preserve_snapshot_payload_shape(self):
        RecurringPreparationNeed.objects.create(
            shipper=self.shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            period_unit=RecurringPreparationPeriodUnit.WEEK,
            target_equivalent_units=10,
            is_active=True,
            created_by=self.user,
        )

        snapshot = snapshot_active_recurring_needs(run=self.run)[0]
        override_preparation_need_snapshot(
            snapshot,
            period_unit=RecurringPreparationPeriodUnit.MONTH,
        )
        snapshot.refresh_from_db()
        unchanged_payload = dict(snapshot.snapshot_payload)
        override_preparation_need_snapshot(snapshot)
        snapshot.refresh_from_db()

        self.assertEqual(snapshot.period_unit, RecurringPreparationPeriodUnit.MONTH)
        self.assertEqual(snapshot.snapshot_payload["override"]["period_unit"], "month")
        self.assertEqual(snapshot.snapshot_payload, unchanged_payload)

    def test_noop_override_returns_snapshot_without_creating_override_payload(self):
        RecurringPreparationNeed.objects.create(
            shipper=self.shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            period_unit=RecurringPreparationPeriodUnit.WEEK,
            target_equivalent_units=10,
            is_active=True,
            created_by=self.user,
        )

        snapshot = snapshot_active_recurring_needs(run=self.run)[0]
        returned_snapshot = override_preparation_need_snapshot(snapshot)
        snapshot.refresh_from_db()

        self.assertEqual(returned_snapshot.id, snapshot.id)
        self.assertNotIn("override", snapshot.snapshot_payload)
