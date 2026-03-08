from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import (
    PlanningAssignment,
    PlanningFlightSnapshot,
    PlanningRun,
    PlanningRunStatus,
    PlanningShipmentSnapshot,
    PlanningVersion,
    PlanningVersionStatus,
    PlanningVolunteerSnapshot,
)
from wms.planning.solver import solve_run


class PlanningSolverContractTests(TestCase):
    def test_solve_run_creates_draft_version_and_assignments(self):
        user = get_user_model().objects.create_user(
            username="planner@example.com",
            email="planner@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            status=PlanningRunStatus.READY,
            created_by=user,
        )
        shipment = PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="EXP-PLAN-001",
            shipper_name="Association shipper",
            destination_iata="ABJ",
            priority=5,
            carton_count=3,
            equivalent_units=6,
        )
        volunteer = PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="Ada Volunteer",
            max_colis_vol=4,
            availability_summary={
                "slot_count": 1,
                "slots": [
                    {
                        "date": "2026-03-10",
                        "start_time": "09:00",
                        "end_time": "12:00",
                    }
                ],
            },
        )
        flight = PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF702",
            departure_date=date(2026, 3, 10),
            destination_iata="ABJ",
            capacity_units=12,
        )

        version = solve_run(run)

        run.refresh_from_db()
        assignment = PlanningAssignment.objects.get(version=version)

        self.assertIsInstance(version, PlanningVersion)
        self.assertEqual(version.status, PlanningVersionStatus.DRAFT)
        self.assertEqual(run.status, PlanningRunStatus.SOLVED)
        self.assertEqual(assignment.shipment_snapshot, shipment)
        self.assertEqual(assignment.volunteer_snapshot, volunteer)
        self.assertEqual(assignment.flight_snapshot, flight)
        self.assertEqual(run.solver_result["assignment_count"], 1)
        self.assertEqual(len(run.solver_payload["shipments"]), 1)
