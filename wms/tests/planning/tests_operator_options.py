from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import (
    PlanningAssignment,
    PlanningAssignmentSource,
    PlanningFlightSnapshot,
    PlanningParameterSet,
    PlanningRun,
    PlanningRunStatus,
    PlanningShipmentSnapshot,
    PlanningVersion,
    PlanningVersionStatus,
    PlanningVolunteerSnapshot,
)
from wms.planning.operator_options import (
    build_assignment_editor_options,
    build_unassigned_editor_options,
)


class PlanningOperatorOptionsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="operator-options",
            email="operator-options@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.parameter_set = PlanningParameterSet.objects.create(
            name="Operator options",
            is_current=True,
            created_by=self.user,
        )
        self.run = PlanningRun.objects.create(
            week_start=date(2026, 3, 9),
            week_end=date(2026, 3, 15),
            parameter_set=self.parameter_set,
            status=PlanningRunStatus.SOLVED,
            created_by=self.user,
        )
        self.version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.DRAFT,
            created_by=self.user,
        )

    def test_build_assignment_editor_options_exposes_colored_dates_flights_and_volunteers(
        self,
    ):
        target_shipment = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="260128",
            shipper_name="ASF",
            destination_iata="NSI",
            carton_count=4,
            equivalent_units=4,
            payload={"legacy_type": "MM", "legacy_destinataire": "CORRESPONDANT"},
        )
        other_shipment = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="260129",
            shipper_name="ASF",
            destination_iata="NSI",
            carton_count=2,
            equivalent_units=2,
        )
        volunteer_green = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="COURTOIS Alain",
            availability_summary={
                "slots": [{"date": "2026-03-10", "start_time": "07:00", "end_time": "18:00"}],
                "unavailable_dates": [],
            },
        )
        volunteer_orange = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="PIERSON Gilles",
            availability_summary={
                "slots": [{"date": "2026-03-10", "start_time": "07:00", "end_time": "18:00"}],
                "unavailable_dates": [],
            },
        )
        volunteer_red = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="FILOU Thierry",
            availability_summary={"slots": [], "unavailable_dates": ["2026-03-10"]},
        )
        flight_used = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF908",
            departure_date=date(2026, 3, 10),
            destination_iata="NSI",
            capacity_units=10,
            payload={"departure_time": "11:10", "routing": "CDG-NSI"},
        )
        flight_green = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF910",
            departure_date=date(2026, 3, 11),
            destination_iata="NSI",
            capacity_units=10,
            payload={"departure_time": "13:10", "routing": "CDG-NSI"},
        )
        flight_red = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF974",
            departure_date=date(2026, 3, 12),
            destination_iata="NSI",
            capacity_units=3,
            payload={"departure_time": "12:00", "routing": "CDG-NSI"},
        )
        assignment = PlanningAssignment.objects.create(
            version=self.version,
            shipment_snapshot=target_shipment,
            volunteer_snapshot=volunteer_green,
            flight_snapshot=flight_used,
            assigned_carton_count=4,
            source=PlanningAssignmentSource.MANUAL,
            sequence=1,
        )
        PlanningAssignment.objects.create(
            version=self.version,
            shipment_snapshot=other_shipment,
            volunteer_snapshot=volunteer_orange,
            flight_snapshot=PlanningFlightSnapshot.objects.create(
                run=self.run,
                flight_number="AF456",
                departure_date=date(2026, 3, 10),
                destination_iata="RUN",
                capacity_units=10,
                payload={"departure_time": "10:00", "routing": "CDG-RUN"},
            ),
            assigned_carton_count=2,
            source=PlanningAssignmentSource.MANUAL,
            sequence=2,
        )

        options = build_assignment_editor_options(self.version, assignment=assignment)

        date_tones = {item["value"]: item["tone"] for item in options["date_options"]}
        self.assertEqual(date_tones["2026-03-10"], "orange")
        self.assertEqual(date_tones["2026-03-11"], "green")
        self.assertEqual(date_tones["2026-03-12"], "red")

        flight_tones = {item["value"]: item["tone"] for item in options["flight_options"]}
        self.assertEqual(flight_tones[str(flight_used.pk)], "orange")
        self.assertEqual(flight_tones[str(flight_green.pk)], "green")
        self.assertEqual(flight_tones[str(flight_red.pk)], "red")

        volunteer_tones = {item["label"]: item["tone"] for item in options["volunteer_options"]}
        self.assertEqual(volunteer_tones["COURTOIS Alain"], "green")
        self.assertEqual(volunteer_tones["PIERSON Gilles"], "orange")
        self.assertEqual(volunteer_tones["FILOU Thierry"], "red")

        volunteer_by_label = {item["label"]: item for item in options["volunteer_options"]}
        self.assertEqual(
            volunteer_by_label["COURTOIS Alain"]["tones_by_flight"][str(flight_used.pk)],
            "green",
        )
        self.assertEqual(
            volunteer_by_label["PIERSON Gilles"]["tones_by_flight"][str(flight_used.pk)],
            "orange",
        )
        self.assertEqual(
            volunteer_by_label["FILOU Thierry"]["tones_by_flight"][str(flight_green.pk)],
            "green",
        )

    def test_build_unassigned_editor_options_preselects_first_compatible_volunteer(self):
        shipment = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="260200",
            shipper_name="ASF",
            destination_iata="NSI",
            carton_count=2,
            equivalent_units=2,
        )
        volunteer_red = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="ALPHA Red",
            availability_summary={"slots": [], "unavailable_dates": ["2026-03-11"]},
        )
        volunteer_green = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="BRAVO Green",
            availability_summary={
                "slots": [{"date": "2026-03-11", "start_time": "07:00", "end_time": "18:00"}],
                "unavailable_dates": [],
            },
        )
        flight = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF910",
            departure_date=date(2026, 3, 11),
            destination_iata="NSI",
            capacity_units=10,
            payload={"departure_time": "13:10", "routing": "CDG-NSI"},
        )

        options = build_unassigned_editor_options(self.version, shipment_snapshot=shipment)

        self.assertEqual(options["selected_flight_id"], str(flight.pk))
        volunteer_by_label = {item["label"]: item for item in options["volunteer_options"]}
        self.assertEqual(volunteer_by_label["ALPHA Red"]["tone"], "red")
        self.assertEqual(volunteer_by_label["BRAVO Green"]["tone"], "green")
        self.assertTrue(volunteer_by_label["BRAVO Green"]["selected"])
        self.assertFalse(volunteer_by_label["ALPHA Red"]["selected"])

    def test_build_unassigned_editor_options_prefers_assignable_flight_volunteer_pair(self):
        shipment = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="260201",
            shipper_name="ASF",
            destination_iata="NSI",
            carton_count=2,
            equivalent_units=2,
        )
        volunteer = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="BRAVO Green",
            availability_summary={
                "slots": [{"date": "2026-03-12", "start_time": "07:00", "end_time": "18:00"}],
                "unavailable_dates": [],
            },
        )
        early_flight = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF908",
            departure_date=date(2026, 3, 11),
            destination_iata="NSI",
            capacity_units=10,
            payload={"departure_time": "11:10", "routing": "CDG-NSI"},
        )
        late_flight = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF910",
            departure_date=date(2026, 3, 12),
            destination_iata="NSI",
            capacity_units=10,
            payload={"departure_time": "13:10", "routing": "CDG-NSI"},
        )

        options = build_unassigned_editor_options(self.version, shipment_snapshot=shipment)

        self.assertEqual(options["selected_flight_id"], str(late_flight.pk))
        self.assertTrue(options["has_assignable_pair"])
        volunteer_by_label = {item["label"]: item for item in options["volunteer_options"]}
        self.assertTrue(volunteer_by_label["BRAVO Green"]["selected"])
        self.assertEqual(
            volunteer_by_label["BRAVO Green"]["tones_by_flight"][str(early_flight.pk)],
            "red",
        )
        self.assertEqual(
            volunteer_by_label["BRAVO Green"]["tones_by_flight"][str(late_flight.pk)],
            "green",
        )
