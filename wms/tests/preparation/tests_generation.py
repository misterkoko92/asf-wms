from datetime import UTC, date, datetime, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    Flight,
    FlightSourceBatch,
    FlightSourceBatchStatus,
    Location,
    PreparationDestinationRule,
    PreparationParameterSet,
    PreparationRun,
    PreparationRunNeedSnapshot,
    PreparationRunStatus,
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
    ShipmentRecipientOrganization,
    ShipmentShipper,
    Warehouse,
)
from wms.planning.flight_providers import (
    PlanningFlightProviderConfigurationError,
    PlanningFlightProviderError,
)
from wms.preparation.generation import generate_preparation_run


class PreparationGenerationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="prep-generation@example.com",
            email="prep-generation@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.parameter_set = PreparationParameterSet.objects.create(
            name="Run magasin W19",
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
        self.warehouse = Warehouse.objects.create(name="Main", code="WH-GEN")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.category_l2 = ProductCategory.objects.create(name="Kits")
        self.category_l3 = ProductCategory.objects.create(
            name="Obstetrique",
            parent=self.category_l2,
        )
        self.product = Product.objects.create(
            name="Kit Accouchement",
            category=self.category_l3,
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
        self.run = PreparationRun.objects.create(
            parameter_set=self.parameter_set,
            created_by=self.user,
            target_equivalent_units=12,
            target_shipment_count=3,
            target_shipment_size_units=10,
            min_shipment_size_units=5,
            max_shipment_size_units=12,
            flight_window_start=date(2026, 5, 4),
            flight_window_end=date(2026, 5, 10),
            status=PreparationRunStatus.DRAFT,
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
        RecurringPreparationNeed.objects.create(
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

    def _create_batch(self, *, imported_at=None, capacity_units=30):
        batch = FlightSourceBatch.objects.create(
            source="api",
            period_start=self.run.flight_window_start,
            period_end=self.run.flight_window_end,
            status=FlightSourceBatchStatus.IMPORTED,
            imported_at=imported_at or timezone.now(),
        )
        Flight.objects.create(
            batch=batch,
            flight_number="AF702",
            departure_date=self.run.flight_window_start,
            departure_time=time(9, 45),
            destination_iata="ABJ",
            origin_iata="CDG",
            routing="CDG-ABJ",
            route_pos=1,
            destination=self.destination,
            capacity_units=capacity_units,
        )
        return batch

    def test_generation_snapshots_needs_and_parameters_and_creates_proposals(self):
        batch = self._create_batch(capacity_units=20)

        generated_run = generate_preparation_run(
            run=self.run,
            shippers=[self.shipper],
            destinations=[self.destination],
            api_batch_loader=lambda *, start_date, end_date: batch,
        )

        generated_run.refresh_from_db()
        proposal = generated_run.shipment_proposals.get()
        carton = proposal.carton_proposals.get()

        self.assertEqual(generated_run.status, PreparationRunStatus.GENERATED)
        self.assertEqual(PreparationRunNeedSnapshot.objects.filter(run=generated_run).count(), 1)
        self.assertEqual(proposal.equivalent_units_total, 12)
        self.assertEqual(carton.quantity, 12)
        self.assertEqual(carton.product, self.product)
        self.assertEqual(carton.reservations.count(), 1)
        self.assertEqual(
            generated_run.parameter_snapshot["inputs"]["shipper_ids"],
            [self.shipper.id],
        )
        self.assertEqual(
            generated_run.parameter_snapshot["inputs"]["destination_ids"],
            [self.destination.id],
        )
        self.assertEqual(
            generated_run.parameter_snapshot["flight_source"]["batch_id"],
            batch.id,
        )
        self.assertFalse(generated_run.parameter_snapshot["flight_source"]["used_fallback"])

    def test_generation_respects_target_size_and_backlogs_small_remainder(self):
        self.run.target_equivalent_units = 24
        self.run.target_shipment_count = 4
        self.run.target_shipment_size_units = 10
        self.run.min_shipment_size_units = 5
        self.run.max_shipment_size_units = 10
        self.run.save(
            update_fields=[
                "target_equivalent_units",
                "target_shipment_count",
                "target_shipment_size_units",
                "min_shipment_size_units",
                "max_shipment_size_units",
            ]
        )
        destination_rule = PreparationDestinationRule.objects.get(
            parameter_set=self.parameter_set,
            destination=self.destination,
        )
        destination_rule.max_equivalent_units_per_flight = 30
        destination_rule.max_equivalent_units_per_week = 30
        destination_rule.save(
            update_fields=[
                "max_equivalent_units_per_flight",
                "max_equivalent_units_per_week",
            ]
        )
        recurring_need = RecurringPreparationNeed.objects.get(
            shipper=self.shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
        )
        recurring_need.target_equivalent_units = 24
        recurring_need.save(update_fields=["target_equivalent_units"])
        preference = RecipientProductPreference.objects.get(
            recipient_organization=self.recipient,
            product=self.product,
        )
        preference.quantity_target = 24
        preference.save(update_fields=["quantity_target"])
        batch = self._create_batch(capacity_units=30)

        generated_run = generate_preparation_run(
            run=self.run,
            shippers=[self.shipper],
            destinations=[self.destination],
            api_batch_loader=lambda *, start_date, end_date: batch,
        )

        shipment_totals = list(
            generated_run.shipment_proposals.order_by("sequence").values_list(
                "equivalent_units_total",
                flat=True,
            )
        )

        self.assertEqual(shipment_totals, [10, 10])
        self.assertEqual(
            generated_run.parameter_snapshot["backlog"],
            [
                {
                    "shipper_id": self.shipper.id,
                    "recipient_organization_id": self.recipient.id,
                    "destination_id": self.destination.id,
                    "equivalent_units": 4,
                    "reason": "below_min_shipment_size",
                }
            ],
        )

    def test_generation_uses_last_exploitable_batch_on_api_failure(self):
        fallback_batch = self._create_batch(
            imported_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
            capacity_units=18,
        )

        def failing_loader(*, start_date, end_date):
            raise PlanningFlightProviderError("upstream unavailable")

        generated_run = generate_preparation_run(
            run=self.run,
            shippers=[self.shipper],
            destinations=[self.destination],
            api_batch_loader=failing_loader,
        )

        flight_source = generated_run.parameter_snapshot["flight_source"]

        self.assertEqual(flight_source["batch_id"], fallback_batch.id)
        self.assertEqual(flight_source["mode"], "fallback")
        self.assertTrue(flight_source["used_fallback"])
        self.assertEqual(flight_source["fallback_reason"], "upstream unavailable")
        self.assertEqual(flight_source["freshness_days"], 3)

    def test_generation_uses_previous_batch_pattern_when_api_is_unconfigured(self):
        self.run.flight_window_start = date(2026, 5, 12)
        self.run.flight_window_end = date(2026, 5, 18)
        self.run.save(update_fields=["flight_window_start", "flight_window_end"])
        fallback_batch = FlightSourceBatch.objects.create(
            source="api",
            period_start=date(2026, 5, 4),
            period_end=date(2026, 5, 10),
            status=FlightSourceBatchStatus.IMPORTED,
            imported_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        )
        Flight.objects.create(
            batch=fallback_batch,
            flight_number="AF702",
            departure_date=date(2026, 5, 5),
            departure_time=time(9, 45),
            destination_iata="ABJ",
            origin_iata="CDG",
            routing="CDG-ABJ",
            route_pos=1,
            destination=self.destination,
            capacity_units=18,
        )

        def unconfigured_loader(*, start_date, end_date):
            raise PlanningFlightProviderConfigurationError("PLANNING_FLIGHT_API_KEY is required.")

        generated_run = generate_preparation_run(
            run=self.run,
            shippers=[self.shipper],
            destinations=[self.destination],
            api_batch_loader=unconfigured_loader,
        )

        flight_source = generated_run.parameter_snapshot["flight_source"]

        self.assertEqual(flight_source["batch_id"], fallback_batch.id)
        self.assertEqual(flight_source["mode"], "fallback")
        self.assertTrue(flight_source["used_fallback"])
        self.assertEqual(flight_source["fallback_reason"], "PLANNING_FLIGHT_API_KEY is required.")
        self.assertEqual(generated_run.shipment_proposals.count(), 1)
