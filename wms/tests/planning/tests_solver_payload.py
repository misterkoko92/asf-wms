from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    PlanningDestinationRule,
    PlanningFlightSnapshot,
    PlanningParameterSet,
    PlanningRun,
    PlanningShipmentSnapshot,
    PlanningVolunteerSnapshot,
)
from wms.planning.rules import compile_run_solver_payload


class SolverPayloadTests(TestCase):
    def test_payload_includes_route_frequency_and_capacity_fields(self):
        planner = get_user_model().objects.create_user(
            username="planner-payload@example.com",
            email="planner-payload@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        correspondent = Contact.objects.create(
            name="Correspondent ABJ",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="CI",
            correspondent_contact=correspondent,
        )
        parameter_set = PlanningParameterSet.objects.create(
            name="Payload semaine 11",
            is_current=True,
        )
        PlanningDestinationRule.objects.create(
            parameter_set=parameter_set,
            destination=destination,
            label="ABJ weekly",
            weekly_frequency=2,
            max_cartons_per_flight=12,
            priority=5,
        )
        run = PlanningRun.objects.create(
            week_start=date(2026, 3, 9),
            week_end=date(2026, 3, 15),
            parameter_set=parameter_set,
            created_by=planner,
        )
        PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="EXP-PLAN-001",
            destination_iata="ABJ",
            priority=5,
            carton_count=3,
            equivalent_units=6,
        )
        PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="Ada Volunteer",
            max_colis_vol=4,
            availability_summary={},
        )
        PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF702",
            departure_date=date(2026, 3, 10),
            destination_iata="ABJ",
            capacity_units=20,
            payload={
                "departure_time": "09:45",
                "origin_iata": "CDG",
                "routing": "CDG-ABJ",
                "route_pos": 1,
            },
        )

        payload = compile_run_solver_payload(run)
        flight = payload["flights"][0]

        self.assertEqual(payload["destination_rules_by_iata"]["ABJ"]["weekly_frequency"], 2)
        self.assertEqual(flight["routing"], "CDG-ABJ")
        self.assertEqual(flight["route_pos"], 1)
        self.assertEqual(flight["origin_iata"], "CDG")
        self.assertEqual(flight["weekly_frequency"], 2)
        self.assertEqual(flight["max_cartons_per_flight"], 12)
        self.assertEqual(flight["physical_flight_key"], "2026-03-10|09:45|AF702")
