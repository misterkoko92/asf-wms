from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    Location,
    PreparationCartonProposal,
    PreparationDecisionAction,
    PreparationDecisionLog,
    PreparationDestinationRule,
    PreparationParameterSet,
    PreparationProposalSource,
    PreparationReservation,
    PreparationReservationStatus,
    PreparationRun,
    PreparationRunNeedSnapshot,
    PreparationRunStatus,
    PreparationShipmentProposal,
    PreparationShipmentProposalStatus,
    PreparationShipperMode,
    PreparationShipperRule,
    Product,
    ProductLot,
    ProductLotStatus,
    RecurringPreparationNeed,
    RecurringPreparationPeriodUnit,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    Warehouse,
)


class PreparationModelsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="prep-models@example.com",
            email="prep-models@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.parameter_set = PreparationParameterSet.objects.create(
            name="Run magasin W15",
            created_by=self.user,
        )
        self.shipper_contact = Contact.objects.create(
            name="Association Source",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.recipient_contact = Contact.objects.create(
            name="Association Destinataire",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.correspondent_contact = Contact.objects.create(
            first_name="Corinne",
            last_name="Correspondante",
            email="correspondant@example.com",
            organization=self.recipient_contact,
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="CI",
            correspondent_contact=self.correspondent_contact,
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
        self.recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=self.recipient_contact,
            destination=self.destination,
            validation_status="validated",
        )
        self.run = PreparationRun.objects.create(
            parameter_set=self.parameter_set,
            created_by=self.user,
            target_equivalent_units=40,
            target_shipment_count=4,
            target_shipment_size_units=10,
            flight_window_start=date(2026, 4, 6),
            flight_window_end=date(2026, 4, 13),
            status=PreparationRunStatus.DRAFT,
        )

    def test_parameter_set_and_scoped_rules_can_be_created(self):
        destination_rule = PreparationDestinationRule.objects.create(
            parameter_set=self.parameter_set,
            destination=self.destination,
            max_equivalent_units_per_flight=20,
            max_usable_flights_per_week=2,
            allowed_weekdays=["mon", "thu"],
        )
        shipper_rule = PreparationShipperRule.objects.create(
            parameter_set=self.parameter_set,
            shipper=self.shipper,
            mode=PreparationShipperMode.ASF_COMPLEMENT_ALLOWED,
            score_coefficient="1.00",
        )

        self.assertEqual(destination_rule.destination, self.destination)
        self.assertEqual(shipper_rule.mode, PreparationShipperMode.ASF_COMPLEMENT_ALLOWED)

    def test_scoped_rules_are_unique(self):
        PreparationDestinationRule.objects.create(
            parameter_set=self.parameter_set,
            destination=self.destination,
            max_equivalent_units_per_flight=20,
        )
        PreparationShipperRule.objects.create(
            parameter_set=self.parameter_set,
            shipper=self.shipper,
            mode=PreparationShipperMode.DEPOSIT_ONLY,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PreparationDestinationRule.objects.create(
                    parameter_set=self.parameter_set,
                    destination=self.destination,
                    max_equivalent_units_per_flight=30,
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PreparationShipperRule.objects.create(
                    parameter_set=self.parameter_set,
                    shipper=self.shipper,
                    mode=PreparationShipperMode.ASF_AUTO_ALLOWED,
                )

    def test_recurring_need_is_unique_per_shipper_recipient_destination(self):
        RecurringPreparationNeed.objects.create(
            shipper=self.shipper,
            recipient_organization=self.recipient_organization,
            destination=self.destination,
            period_unit=RecurringPreparationPeriodUnit.WEEK,
            target_equivalent_units=12,
            is_active=True,
            created_by=self.user,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RecurringPreparationNeed.objects.create(
                    shipper=self.shipper,
                    recipient_organization=self.recipient_organization,
                    destination=self.destination,
                    period_unit=RecurringPreparationPeriodUnit.WEEK,
                    target_equivalent_units=6,
                    is_active=True,
                    created_by=self.user,
                )

    def test_recurring_need_rejects_destination_mismatch(self):
        other_destination = Destination.objects.create(
            city="Douala",
            iata_code="DLA",
            country="CM",
            correspondent_contact=self.correspondent_contact,
        )
        recurring_need = RecurringPreparationNeed(
            shipper=self.shipper,
            recipient_organization=self.recipient_organization,
            destination=other_destination,
            period_unit=RecurringPreparationPeriodUnit.WEEK,
            target_equivalent_units=12,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            recurring_need.full_clean()

    def test_shipment_proposal_is_unique_per_run_scope_and_sequence(self):
        proposal = PreparationShipmentProposal.objects.create(
            run=self.run,
            shipper=self.shipper,
            recipient_organization=self.recipient_organization,
            destination=self.destination,
            sequence=1,
            source=PreparationProposalSource.MIXED,
            status=PreparationShipmentProposalStatus.PROPOSED,
            equivalent_units_total=10,
        )
        PreparationCartonProposal.objects.create(
            shipment_proposal=proposal,
            source=PreparationProposalSource.ASF_STOCK,
            status=PreparationShipmentProposalStatus.PROPOSED,
            quantity=4,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PreparationShipmentProposal.objects.create(
                    run=self.run,
                    shipper=self.shipper,
                    recipient_organization=self.recipient_organization,
                    destination=self.destination,
                    sequence=1,
                    source=PreparationProposalSource.MIXED,
                    status=PreparationShipmentProposalStatus.PROPOSED,
                    equivalent_units_total=8,
                )

    def test_need_snapshot_reservation_and_decision_log_persist_required_audit_fields(self):
        need = RecurringPreparationNeed.objects.create(
            shipper=self.shipper,
            recipient_organization=self.recipient_organization,
            destination=self.destination,
            period_unit=RecurringPreparationPeriodUnit.WEEK,
            target_equivalent_units=14,
            is_active=True,
            created_by=self.user,
        )
        snapshot = PreparationRunNeedSnapshot.objects.create(
            run=self.run,
            recurring_need=need,
            shipper=self.shipper,
            recipient_organization=self.recipient_organization,
            destination=self.destination,
            period_unit=RecurringPreparationPeriodUnit.WEEK,
            target_equivalent_units=14,
            snapshot_payload={"copied": True},
        )
        warehouse = Warehouse.objects.create(name="Main", code="WH-PREP")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        product = Product.objects.create(
            name="Kit Hygiene",
            category=None,
            default_location=location,
        )
        lot = ProductLot.objects.create(
            product=product,
            location=location,
            quantity_on_hand=20,
            quantity_reserved=0,
            status=ProductLotStatus.AVAILABLE,
        )
        proposal = PreparationShipmentProposal.objects.create(
            run=self.run,
            shipper=self.shipper,
            recipient_organization=self.recipient_organization,
            destination=self.destination,
            sequence=2,
            source=PreparationProposalSource.ASF_STOCK,
            status=PreparationShipmentProposalStatus.PROPOSED,
            equivalent_units_total=12,
        )
        carton_proposal = PreparationCartonProposal.objects.create(
            shipment_proposal=proposal,
            product=product,
            source=PreparationProposalSource.ASF_STOCK,
            status=PreparationShipmentProposalStatus.PROPOSED,
            quantity=12,
        )

        reservation = PreparationReservation.objects.create(
            run=self.run,
            shipment_proposal=proposal,
            carton_proposal=carton_proposal,
            product_lot=lot,
            quantity=12,
            status=PreparationReservationStatus.ACTIVE,
            created_by=self.user,
        )
        decision = PreparationDecisionLog.objects.create(
            run=self.run,
            shipment_proposal=proposal,
            carton_proposal=carton_proposal,
            reservation=reservation,
            action=PreparationDecisionAction.ACCEPT,
            note="Validation operator",
            created_by=self.user,
        )

        self.assertEqual(snapshot.snapshot_payload["copied"], True)
        self.assertEqual(reservation.created_by, self.user)
        self.assertEqual(decision.action, PreparationDecisionAction.ACCEPT)
