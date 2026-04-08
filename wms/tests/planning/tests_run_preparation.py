from datetime import UTC, date, datetime, time, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationPortalContact,
    AssociationProfile,
    Carton,
    CartonItem,
    Destination,
    Flight,
    FlightSourceBatch,
    Location,
    PlanningDestinationRule,
    PlanningFlightSnapshot,
    PlanningIssue,
    PlanningParameterSet,
    PlanningRun,
    PlanningRunStatus,
    PlanningShipmentSnapshot,
    PlanningVolunteerSnapshot,
    Product,
    ProductCategory,
    ProductLot,
    Shipment,
    ShipmentStatus,
    ShipmentUnitEquivalenceRule,
    VolunteerAvailability,
    VolunteerConstraint,
    VolunteerProfile,
    Warehouse,
)
from wms.planning.flight_providers import PlanningFlightProviderError
from wms.planning.snapshots import prepare_run_inputs


class PlanningRunPreparationTests(TestCase):
    def setUp(self):
        self.planner = get_user_model().objects.create_user(
            username="planner@example.com",
            email="planner@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.week_start = date(2026, 3, 9)
        self.week_end = date(2026, 3, 15)
        self.parameter_set = PlanningParameterSet.objects.create(
            name="Semaine 11",
            is_current=True,
        )
        self.run = PlanningRun.objects.create(
            week_start=self.week_start,
            week_end=self.week_end,
            parameter_set=self.parameter_set,
            created_by=self.planner,
        )

        self.shipper_contact = Contact.objects.create(
            name="Association shipper",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.correspondent_contact = Contact.objects.create(
            name="Correspondent ABJ",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="CI",
            correspondent_contact=self.correspondent_contact,
        )

    def _create_shipment(self):
        shipment = Shipment.objects.create(
            reference="EXP-PLAN-001",
            status=ShipmentStatus.PACKED,
            shipper_name="Association shipper",
            shipper_contact_ref=self.shipper_contact,
            recipient_name="Recipient ABJ",
            destination=self.destination,
            destination_address="Airport road",
            destination_country="Cote d'Ivoire",
            ready_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
            created_by=self.planner,
        )
        warehouse = Warehouse.objects.create(name="Main warehouse", code="WH1")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="01",
        )
        category = ProductCategory.objects.create(name="Medical")
        product = Product.objects.create(
            name="Wheelchair",
            category=category,
            default_location=location,
        )
        lot = ProductLot.objects.create(
            product=product,
            location=location,
            quantity_on_hand=10,
        )
        carton = Carton.objects.create(
            code="CARTON-PLAN-001",
            shipment=shipment,
            current_location=location,
        )
        CartonItem.objects.create(
            carton=carton,
            product_lot=lot,
            quantity=3,
        )
        ShipmentUnitEquivalenceRule.objects.create(
            label="Medical x2",
            category=category,
            units_per_item=2,
        )
        return shipment

    def test_prepare_run_records_issue_for_missing_destination_rule(self):
        shipment = self._create_shipment()

        prepare_run_inputs(self.run)

        self.run.refresh_from_db()
        issue = PlanningIssue.objects.get(run=self.run, code="missing_destination_rule")

        self.assertEqual(self.run.status, PlanningRunStatus.VALIDATION_FAILED)
        self.assertEqual(issue.source_pk, shipment.pk)

    def test_prepare_run_creates_shipments_volunteers_and_flight_snapshots(self):
        PlanningDestinationRule.objects.create(
            parameter_set=self.parameter_set,
            destination=self.destination,
            label="ABJ weekly",
            weekly_frequency=2,
            max_cartons_per_flight=12,
            priority=5,
        )
        shipment = self._create_shipment()

        association_user = get_user_model().objects.create_user(
            username="shipper@example.com",
            email="shipper@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        profile = AssociationProfile.objects.create(
            user=association_user,
            contact=self.shipper_contact,
            notification_emails="ops@example.com",
        )
        AssociationPortalContact.objects.create(
            profile=profile,
            first_name="Ada",
            last_name="Ops",
            email="shipping@example.com",
            is_shipping=True,
        )

        volunteer_user = get_user_model().objects.create_user(
            username="volunteer@example.com",
            email="volunteer@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        volunteer = VolunteerProfile.objects.create(user=volunteer_user)
        VolunteerConstraint.objects.create(volunteer=volunteer, max_colis_vol=4)
        VolunteerAvailability.objects.create(
            volunteer=volunteer,
            date=self.week_start + timedelta(days=1),
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        batch = FlightSourceBatch.objects.create(
            source="excel",
            period_start=self.week_start,
            period_end=self.week_end,
            status="imported",
        )
        flight = Flight.objects.create(
            batch=batch,
            flight_number="AF702",
            departure_date=self.week_start + timedelta(days=1),
            departure_time=time(9, 45),
            destination_iata="ABJ",
            origin_iata="CDG",
            routing="CDG-ABJ",
            route_pos=1,
            destination=self.destination,
            capacity_units=20,
        )
        self.run.flight_batch = batch
        self.run.save(update_fields=["flight_batch"])

        prepare_run_inputs(self.run)

        self.run.refresh_from_db()
        shipment_snapshot = PlanningShipmentSnapshot.objects.get(run=self.run, shipment=shipment)
        volunteer_snapshot = PlanningVolunteerSnapshot.objects.get(
            run=self.run, volunteer=volunteer
        )
        flight_snapshot = PlanningFlightSnapshot.objects.get(run=self.run, flight=flight)

        self.assertEqual(self.run.status, PlanningRunStatus.READY)
        self.assertEqual(shipment_snapshot.carton_count, 1)
        self.assertEqual(shipment_snapshot.equivalent_units, 6)
        self.assertEqual(
            shipment_snapshot.payload["shipper_reference"]["notification_emails"],
            ["shipping@example.com"],
        )
        self.assertEqual(volunteer_snapshot.max_colis_vol, 4)
        self.assertEqual(volunteer_snapshot.availability_summary["slot_count"], 1)
        self.assertEqual(flight_snapshot.capacity_units, 20)
        self.assertEqual(flight_snapshot.payload["departure_time"], "09:45")
        self.assertEqual(flight_snapshot.payload["origin_iata"], "CDG")
        self.assertEqual(flight_snapshot.payload["routing"], "CDG-ABJ")
        self.assertEqual(flight_snapshot.payload["route_pos"], 1)

    @mock.patch("wms.planning.snapshots.collect_flight_batches")
    def test_prepare_run_collects_api_flights_when_run_uses_api_mode(
        self,
        collect_flight_batches_mock,
    ):
        PlanningDestinationRule.objects.create(
            parameter_set=self.parameter_set,
            destination=self.destination,
            label="ABJ weekly",
            weekly_frequency=2,
            max_cartons_per_flight=12,
            priority=5,
        )
        self._create_shipment()

        volunteer_user = get_user_model().objects.create_user(
            username="volunteer-api@example.com",
            email="volunteer-api@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        volunteer = VolunteerProfile.objects.create(user=volunteer_user)
        VolunteerAvailability.objects.create(
            volunteer=volunteer,
            date=self.week_start + timedelta(days=1),
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        api_batch = FlightSourceBatch.objects.create(
            source="api",
            period_start=self.week_start,
            period_end=self.week_end,
            status="imported",
        )
        api_flight = Flight.objects.create(
            batch=api_batch,
            flight_number="AF702",
            departure_date=self.week_start + timedelta(days=1),
            departure_time=time(9, 45),
            destination_iata="ABJ",
            origin_iata="CDG",
            routing="CDG-ABJ",
            route_pos=1,
            destination=self.destination,
            capacity_units=20,
        )
        self.run.flight_mode = "api"
        self.run.save(update_fields=["flight_mode"])
        collect_flight_batches_mock.return_value = [api_batch]

        prepare_run_inputs(self.run)

        self.run.refresh_from_db()
        collect_flight_batches_mock.assert_called_once_with(
            flight_mode="api",
            start_date=self.week_start,
            end_date=self.week_end,
            excel_batch=None,
            destination_codes=["ABJ"],
        )
        self.assertEqual(self.run.status, PlanningRunStatus.READY)
        self.assertEqual(self.run.flight_batch, api_batch)
        self.assertEqual(
            list(
                PlanningFlightSnapshot.objects.filter(run=self.run).values_list(
                    "flight_id",
                    flat=True,
                )
            ),
            [api_flight.id],
        )
        self.assertEqual(self.run.validation_summary["flight_count"], 1)

    @mock.patch("wms.planning.snapshots.collect_flight_batches")
    def test_prepare_run_combines_excel_and_api_flights_when_run_uses_hybrid_mode(
        self,
        collect_flight_batches_mock,
    ):
        PlanningDestinationRule.objects.create(
            parameter_set=self.parameter_set,
            destination=self.destination,
            label="ABJ weekly",
            weekly_frequency=2,
            max_cartons_per_flight=12,
            priority=5,
        )
        self._create_shipment()

        volunteer_user = get_user_model().objects.create_user(
            username="volunteer-hybrid@example.com",
            email="volunteer-hybrid@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        VolunteerProfile.objects.create(user=volunteer_user)
        VolunteerAvailability.objects.create(
            volunteer=VolunteerProfile.objects.get(user=volunteer_user),
            date=self.week_start + timedelta(days=1),
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        excel_batch = FlightSourceBatch.objects.create(
            source="excel",
            period_start=self.week_start,
            period_end=self.week_end,
            status="imported",
        )
        excel_flight = Flight.objects.create(
            batch=excel_batch,
            flight_number="AF701",
            departure_date=self.week_start + timedelta(days=1),
            departure_time=time(8, 30),
            destination_iata="ABJ",
            origin_iata="CDG",
            routing="CDG-ABJ",
            route_pos=1,
            destination=self.destination,
            capacity_units=12,
        )
        api_batch = FlightSourceBatch.objects.create(
            source="api",
            period_start=self.week_start,
            period_end=self.week_end,
            status="imported",
        )
        api_flight = Flight.objects.create(
            batch=api_batch,
            flight_number="AF702",
            departure_date=self.week_start + timedelta(days=2),
            departure_time=time(9, 45),
            destination_iata="ABJ",
            origin_iata="CDG",
            routing="CDG-ABJ",
            route_pos=1,
            destination=self.destination,
            capacity_units=20,
        )
        self.run.flight_mode = "hybrid"
        self.run.flight_batch = excel_batch
        self.run.save(update_fields=["flight_mode", "flight_batch"])
        collect_flight_batches_mock.return_value = [excel_batch, api_batch]

        prepare_run_inputs(self.run)

        self.run.refresh_from_db()
        collect_flight_batches_mock.assert_called_once_with(
            flight_mode="hybrid",
            start_date=self.week_start,
            end_date=self.week_end,
            excel_batch=excel_batch,
            destination_codes=["ABJ"],
        )
        self.assertEqual(self.run.status, PlanningRunStatus.READY)
        self.assertEqual(self.run.flight_batch, excel_batch)
        self.assertCountEqual(
            list(
                PlanningFlightSnapshot.objects.filter(run=self.run).values_list(
                    "flight_id",
                    flat=True,
                )
            ),
            [excel_flight.id, api_flight.id],
        )
        self.assertEqual(self.run.validation_summary["flight_count"], 2)

    @mock.patch("wms.planning.snapshots.collect_flight_batches")
    def test_prepare_run_records_blocking_issue_when_api_flight_import_fails(
        self,
        collect_flight_batches_mock,
    ):
        PlanningDestinationRule.objects.create(
            parameter_set=self.parameter_set,
            destination=self.destination,
            label="ABJ weekly",
            weekly_frequency=2,
            max_cartons_per_flight=12,
            priority=5,
        )
        self._create_shipment()
        self.run.flight_mode = "api"
        self.run.save(update_fields=["flight_mode"])
        collect_flight_batches_mock.side_effect = PlanningFlightProviderError(
            "API down",
        )

        prepare_run_inputs(self.run)

        self.run.refresh_from_db()
        issue = PlanningIssue.objects.get(run=self.run, code="flight_import_failed")
        self.assertEqual(self.run.status, PlanningRunStatus.VALIDATION_FAILED)
        self.assertEqual(issue.message, "Impossible de charger les vols: API down")
        self.assertEqual(self.run.validation_summary["flight_count"], 0)
        self.assertEqual(self.run.validation_summary["error_count"], 1)

    @mock.patch("wms.planning.snapshots.collect_flight_batches")
    def test_prepare_run_uses_destination_rules_when_no_shipment_is_ready(
        self,
        collect_flight_batches_mock,
    ):
        PlanningDestinationRule.objects.create(
            parameter_set=self.parameter_set,
            destination=self.destination,
            label="ABJ weekly",
            weekly_frequency=2,
            max_cartons_per_flight=12,
            priority=5,
        )
        self.run.flight_mode = "api"
        self.run.save(update_fields=["flight_mode"])
        collect_flight_batches_mock.return_value = []

        prepare_run_inputs(self.run)

        collect_flight_batches_mock.assert_called_once_with(
            flight_mode="api",
            start_date=self.week_start,
            end_date=self.week_end,
            excel_batch=None,
            destination_codes=["ABJ"],
        )
