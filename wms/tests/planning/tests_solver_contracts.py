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
from wms.planning.solver import solve_run, summarize_solver_result


class PlanningSolverContractTests(TestCase):
    def test_summarize_solver_result_exposes_candidate_and_unassigned_diagnostics(self):
        payload = {
            "shipments": [
                {
                    "snapshot_id": 101,
                    "reference": "EXP-PLAN-101",
                }
            ],
            "volunteers": [
                {
                    "snapshot_id": 201,
                    "label": "Ada Volunteer",
                }
            ],
            "flights": [
                {
                    "snapshot_id": 301,
                    "flight_number": "AF702",
                }
            ],
        }

        summary = summarize_solver_result(
            payload=payload,
            assignments=[],
            unassigned=[101],
            compatibility={101: [(301, 201)]},
        )

        self.assertEqual(summary["candidate_count"], 1)
        self.assertEqual(summary["assignment_count"], 0)
        self.assertEqual(summary["unassigned_reasons"], {"101": "no_selected_candidate"})
        self.assertEqual(summary["flight_usage"], {"301": 0})
        self.assertEqual(summary["volunteer_usage"], {"201": 0})

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

    def test_solve_run_prefers_first_stop_on_same_physical_flight(self):
        user = get_user_model().objects.create_user(
            username="planner-routing@example.com",
            email="planner-routing@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            status=PlanningRunStatus.READY,
            created_by=user,
        )
        shipment_nkc = PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="EXP-NKC-001",
            shipper_name="Association shipper",
            destination_iata="NKC",
            priority=5,
            carton_count=2,
            equivalent_units=2,
        )
        PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="EXP-CKY-001",
            shipper_name="Association shipper",
            destination_iata="CKY",
            priority=5,
            carton_count=2,
            equivalent_units=2,
        )
        volunteer = PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="Alice Volunteer",
            max_colis_vol=10,
            availability_summary={
                "slot_count": 1,
                "slots": [
                    {
                        "date": "2026-03-10",
                        "start_time": "08:00",
                        "end_time": "18:00",
                    }
                ],
            },
        )
        flight_nkc = PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF1234",
            departure_date=date(2026, 3, 10),
            destination_iata="NKC",
            capacity_units=20,
            payload={
                "departure_time": "10:00",
                "routing": "CDG-NKC-CKY",
                "route_pos": 1,
            },
        )
        PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF1234",
            departure_date=date(2026, 3, 10),
            destination_iata="CKY",
            capacity_units=20,
            payload={
                "departure_time": "10:00",
                "routing": "CDG-NKC-CKY",
                "route_pos": 2,
            },
        )

        version = solve_run(run)

        run.refresh_from_db()
        assignments = list(version.assignments.order_by("sequence", "id"))

        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].shipment_snapshot, shipment_nkc)
        self.assertEqual(assignments[0].volunteer_snapshot, volunteer)
        self.assertEqual(assignments[0].flight_snapshot, flight_nkc)
        self.assertEqual(run.solver_result["assignment_count"], 1)
