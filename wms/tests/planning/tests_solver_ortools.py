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
            max_colis_vol=8,
            availability_summary={
                "slot_count": 1,
                "slots": [
                    {
                        "date": "2026-03-10",
                        "start_time": "07:00",
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

    def test_solve_run_requires_multiple_volunteers_when_equivalent_load_exceeds_legacy_capacity(
        self,
    ):
        user = get_user_model().objects.create_user(
            username="planner-ortools-capacity@example.com",
            email="planner-ortools-capacity@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            status=PlanningRunStatus.READY,
            created_by=user,
        )
        for idx in range(1, 4):
            PlanningShipmentSnapshot.objects.create(
                run=run,
                shipment_reference=f"EXP-PLAN-ORT-CAP-{idx:03d}",
                shipper_name="Association shipper",
                destination_iata="RUN",
                priority=5,
                carton_count=10,
                equivalent_units=10,
            )
        for label in ("Ada Volunteer", "Bob Volunteer"):
            PlanningVolunteerSnapshot.objects.create(
                run=run,
                volunteer_label=label,
                availability_summary={
                    "slot_count": 1,
                    "slots": [
                        {
                            "date": "2026-03-10",
                            "start_time": "05:00",
                            "end_time": "21:00",
                        }
                    ],
                },
            )
        PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF652",
            departure_date=date(2026, 3, 10),
            destination_iata="RUN",
            capacity_units=40,
            payload={"departure_time": "18:20", "routing": "CDG-RUN", "route_pos": 1},
        )

        version = solve_run(run)

        assigned_volunteers = set(
            version.assignments.values_list("volunteer_snapshot__volunteer_label", flat=True)
        )
        self.assertEqual(version.assignments.count(), 3)
        self.assertEqual(len(assigned_volunteers), 2)

    def test_solve_run_reassigns_same_flight_load_using_legacy_volunteer_order(self):
        user = get_user_model().objects.create_user(
            username="planner-ortools-legacy-order@example.com",
            email="planner-ortools-legacy-order@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            status=PlanningRunStatus.READY,
            created_by=user,
        )
        for ref in ("250722", "250723", "250724"):
            PlanningShipmentSnapshot.objects.create(
                run=run,
                shipment_reference=ref,
                shipper_name="AR MADA",
                destination_iata="RUN",
                priority=2,
                carton_count=10,
                equivalent_units=10,
            )
        PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="PIERSON Gilles",
            availability_summary={
                "slot_count": 1,
                "slots": [
                    {
                        "date": "2026-03-11",
                        "start_time": "05:00",
                        "end_time": "21:00",
                    }
                ],
            },
            payload={"legacy_id": 25},
        )
        PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="GUEDON Bernard",
            availability_summary={
                "slot_count": 1,
                "slots": [
                    {
                        "date": "2026-03-11",
                        "start_time": "05:00",
                        "end_time": "21:00",
                    }
                ],
            },
            payload={"legacy_id": 33},
        )
        PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF652",
            departure_date=date(2026, 3, 11),
            destination_iata="RUN",
            capacity_units=40,
            payload={"departure_time": "18:20", "routing": "CDG-RUN", "route_pos": 1},
        )

        version = solve_run(run)

        assignments = list(
            version.assignments.order_by("shipment_snapshot__shipment_reference").values_list(
                "shipment_snapshot__shipment_reference",
                "volunteer_snapshot__volunteer_label",
            )
        )
        self.assertEqual(
            assignments,
            [
                ("250722", "PIERSON Gilles"),
                ("250723", "PIERSON Gilles"),
                ("250724", "GUEDON Bernard"),
            ],
        )
