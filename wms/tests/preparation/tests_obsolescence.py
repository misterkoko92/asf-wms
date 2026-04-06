from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Carton,
    CartonItem,
    Destination,
    Flight,
    FlightSourceBatch,
    FlightSourceBatchStatus,
    Location,
    PreparationDestinationRule,
    PreparationParameterSet,
    PreparationRun,
    PreparationShipmentProposalStatus,
    PreparationShipperMode,
    PreparationShipperRule,
    Product,
    ProductCategory,
    ProductLot,
    ProductLotStatus,
    RecipientProductPreference,
    RecipientProductPreferencePeriodUnit,
    RecipientProductPreferenceStatus,
    RecurringPreparationNeed,
    RecurringPreparationPeriodUnit,
    Shipment,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentStatus,
    Warehouse,
)
from wms.preparation.generation import generate_preparation_run
from wms.preparation.obsolescence import (
    mark_open_preparation_runs_stale_for_shipment,
    mark_open_preparation_runs_stale_for_stock,
    recalculate_preparation_run,
)


class PreparationObsolescenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="prep-obsolescence@example.com",
            email="prep-obsolescence@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.parameter_set = PreparationParameterSet.objects.create(
            name="Run magasin W20",
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
        self.warehouse = Warehouse.objects.create(name="Main", code="WH-OBS")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.category = ProductCategory.objects.create(name="Kits")
        self.product = Product.objects.create(
            name="Kit Accouchement",
            category=self.category,
            default_location=self.location,
        )
        self.lot = ProductLot.objects.create(
            product=self.product,
            location=self.location,
            quantity_on_hand=40,
            quantity_reserved=0,
            status=ProductLotStatus.AVAILABLE,
            expires_on=date(2026, 7, 1),
        )
        PreparationDestinationRule.objects.create(
            parameter_set=self.parameter_set,
            destination=self.destination,
            max_equivalent_units_per_flight=20,
            max_usable_flights_per_week=1,
            max_equivalent_units_per_week=20,
        )
        PreparationShipperRule.objects.create(
            parameter_set=self.parameter_set,
            shipper=self.shipper,
            mode=PreparationShipperMode.ASF_AUTO_ALLOWED,
            score_coefficient="1.00",
        )
        self.recurring_need = RecurringPreparationNeed.objects.create(
            shipper=self.shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            period_unit=RecurringPreparationPeriodUnit.WEEK,
            target_equivalent_units=12,
            is_active=True,
            created_by=self.user,
        )
        RecipientProductPreference.objects.create(
            recipient_organization=self.recipient,
            product=self.product,
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=12,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            created_by=self.user,
        )
        self.batch = FlightSourceBatch.objects.create(
            source="api",
            period_start=date(2026, 5, 11),
            period_end=date(2026, 5, 17),
            status=FlightSourceBatchStatus.IMPORTED,
        )
        Flight.objects.create(
            batch=self.batch,
            flight_number="AF702",
            departure_date=date(2026, 5, 11),
            departure_time=time(9, 45),
            destination_iata="ABJ",
            origin_iata="CDG",
            routing="CDG-ABJ",
            route_pos=1,
            destination=self.destination,
            capacity_units=20,
        )
        self.run = PreparationRun.objects.create(
            parameter_set=self.parameter_set,
            created_by=self.user,
            target_equivalent_units=12,
            target_shipment_count=2,
            target_shipment_size_units=10,
            min_shipment_size_units=5,
            max_shipment_size_units=12,
            flight_window_start=date(2026, 5, 11),
            flight_window_end=date(2026, 5, 17),
        )
        generate_preparation_run(
            run=self.run,
            shippers=[self.shipper],
            destinations=[self.destination],
            api_batch_loader=lambda *, start_date, end_date: self.batch,
        )

    def _create_manual_shipment(self, *, quantity):
        shipment = Shipment.objects.create(
            reference=f"EXP-MANUAL-{quantity}",
            status=ShipmentStatus.PACKED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            destination=self.destination,
            destination_address="Airport road",
            destination_country="CI",
            created_by=self.user,
        )
        carton = Carton.objects.create(
            code=f"CARTON-MANUAL-{quantity}",
            shipment=shipment,
            current_location=self.location,
        )
        CartonItem.objects.create(
            carton=carton,
            product_lot=self.lot,
            quantity=quantity,
        )
        return shipment

    def test_manual_shipment_creation_marks_impacted_proposals_needs_recalc(self):
        proposal = self.run.shipment_proposals.get()
        carton = proposal.carton_proposals.get()
        original_total = proposal.equivalent_units_total
        original_quantity = carton.quantity
        manual_shipment = self._create_manual_shipment(quantity=3)

        mark_open_preparation_runs_stale_for_shipment(shipment=manual_shipment)

        proposal.refresh_from_db()
        carton.refresh_from_db()
        self.assertEqual(proposal.status, PreparationShipmentProposalStatus.NEEDS_RECALC)
        self.assertEqual(carton.status, PreparationShipmentProposalStatus.NEEDS_RECALC)
        self.assertEqual(proposal.equivalent_units_total, original_total)
        self.assertEqual(carton.quantity, original_quantity)

    def test_manual_stock_consumption_marks_impacted_proposals_needs_recalc(self):
        proposal = self.run.shipment_proposals.get()
        carton = proposal.carton_proposals.get()
        self.lot.quantity_on_hand = 5
        self.lot.save(update_fields=["quantity_on_hand"])

        mark_open_preparation_runs_stale_for_stock(product=self.product)

        proposal.refresh_from_db()
        carton.refresh_from_db()
        self.assertEqual(proposal.status, PreparationShipmentProposalStatus.NEEDS_RECALC)
        self.assertEqual(carton.status, PreparationShipmentProposalStatus.NEEDS_RECALC)

    def test_recalculate_creates_a_new_run_instead_of_mutating_the_old_one(self):
        original_run_id = self.run.id
        original_proposal = self.run.shipment_proposals.get()
        self.recurring_need.target_equivalent_units = 8
        self.recurring_need.save(update_fields=["target_equivalent_units"])
        preference = RecipientProductPreference.objects.get(
            recipient_organization=self.recipient,
            product=self.product,
        )
        preference.quantity_target = 8
        preference.save(update_fields=["quantity_target"])

        new_run = recalculate_preparation_run(
            run=self.run,
            created_by=self.user,
            api_batch_loader=lambda *, start_date, end_date: self.batch,
        )

        self.assertNotEqual(new_run.id, original_run_id)
        self.assertEqual(self.run.shipment_proposals.get().id, original_proposal.id)
        self.assertEqual(self.run.shipment_proposals.get().equivalent_units_total, 12)
        self.assertEqual(new_run.shipment_proposals.get().equivalent_units_total, 8)
        self.assertEqual(new_run.parameter_snapshot["recalculated_from_run_id"], self.run.id)

    def test_obsolescence_helpers_noop_when_scope_is_not_impacted(self):
        shipment = Shipment.objects.create(
            reference="EXP-NOOP",
            status=ShipmentStatus.PACKED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            destination=None,
            destination_address="Airport road",
            destination_country="CI",
            created_by=self.user,
        )

        stale_for_shipment = mark_open_preparation_runs_stale_for_shipment(shipment=shipment)
        stale_for_stock = mark_open_preparation_runs_stale_for_stock(product=self.product)

        self.assertEqual(stale_for_shipment, 0)
        self.assertEqual(stale_for_stock, 0)
