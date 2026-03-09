from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import (
    PlanningFlightSnapshot,
    PlanningRun,
    PlanningRunStatus,
    PlanningShipmentSnapshot,
    PlanningVolunteerSnapshot,
)
from wms.planning.solver import solve_run


class SolverOrtoolsTests(TestCase):
    def test_solve_run_uses_ortools_and_persists_a_version(self):
        user = get_user_model().objects.create_user(
            username="planner-ortools@example.com",
            email="planner-ortools@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            status=PlanningRunStatus.READY,
            created_by=user,
        )
        PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="EXP-PLAN-ORT-001",
            shipper_name="Association shipper",
            destination_iata="ABJ",
            priority=5,
            carton_count=3,
            equivalent_units=6,
        )
        PlanningVolunteerSnapshot.objects.create(
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
        PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF702",
            departure_date=date(2026, 3, 10),
            destination_iata="ABJ",
            capacity_units=12,
            payload={"departure_time": "10:00", "routing": "CDG-ABJ", "route_pos": 1},
        )

        version = solve_run(run)

        run.refresh_from_db()
        self.assertEqual(run.solver_result["solver"], "ortools_cp_sat_v1")
        self.assertIn(run.solver_result["status"], {"OPTIMAL", "FEASIBLE"})
        self.assertEqual(version.run_id, run.id)
        self.assertEqual(version.assignments.count(), 1)
        self.assertEqual(run.solver_result["candidate_count"], 1)
