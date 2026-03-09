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


class SolverDiagnosticsTests(TestCase):
    def test_solver_result_exposes_unassigned_reasons_and_flight_usage(self):
        user = get_user_model().objects.create_user(
            username="planner-diagnostics@example.com",
            email="planner-diagnostics@example.com",
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
            shipment_reference="EXP-DIAG-001",
            shipper_name="Association shipper",
            destination_iata="ABJ",
            priority=5,
            carton_count=2,
            equivalent_units=2,
        )
        PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="Late Volunteer",
            max_colis_vol=4,
            availability_summary={
                "slot_count": 1,
                "slots": [
                    {
                        "date": "2026-03-10",
                        "start_time": "11:00",
                        "end_time": "11:05",
                    }
                ],
            },
        )
        PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF703",
            departure_date=date(2026, 3, 10),
            destination_iata="ABJ",
            capacity_units=12,
            payload={"departure_time": "10:00", "routing": "CDG-ABJ", "route_pos": 1},
        )

        solve_run(run)

        run.refresh_from_db()
        result = run.solver_result

        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["assignment_count_by_flight"], {})
        self.assertEqual(
            result["unassigned_reasons"], {str(shipment.pk): "no_compatible_candidate"}
        )
        self.assertEqual(result["nb_vols_sans_benevole_compatible"], 1)
        self.assertEqual(result["vols_diagnostics"][0]["benevole_compat_count"], 0)
        self.assertFalse(result["vols_diagnostics"][0]["used"])
