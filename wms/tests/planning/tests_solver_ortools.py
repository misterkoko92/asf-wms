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
    PlanningRunStatus,
    PlanningShipmentSnapshot,
    PlanningVolunteerSnapshot,
)
from wms.planning import solver as planning_solver
from wms.planning.solver import solve_run


class SolverOrtoolsTests(TestCase):
    def test_configure_cp_solver_uses_deterministic_settings(self):
        if planning_solver.cp_model is None:
            self.skipTest("ortools is not installed")

        solver = planning_solver.cp_model.CpSolver()

        planning_solver.configure_cp_solver(solver)

        self.assertEqual(solver.parameters.max_time_in_seconds, 30.0)
        self.assertEqual(solver.parameters.num_search_workers, 8)
        self.assertEqual(solver.parameters.random_seed, 0)

    def test_canonicalize_equal_weight_assignments_spans_multiple_shippers(self):
        payload = {
            "shipments": [
                {
                    "snapshot_id": 1,
                    "reference": "250705",
                    "shipper_name": "ASF",
                    "destination_iata": "RUN",
                    "priority": 5,
                    "priority_rank": 5,
                    "carton_count": 10,
                    "equivalent_units": 10,
                    "payload": {
                        "legacy_date_impression": "2025-11-17",
                        "legacy_date_conditionnement": "2026-02-18",
                        "legacy_date_depart_mag": "",
                    },
                },
                {
                    "snapshot_id": 2,
                    "reference": "250706",
                    "shipper_name": "ASF",
                    "destination_iata": "RUN",
                    "priority": 5,
                    "priority_rank": 5,
                    "carton_count": 10,
                    "equivalent_units": 10,
                    "payload": {
                        "legacy_date_impression": "2025-11-17",
                        "legacy_date_conditionnement": "2026-02-25",
                        "legacy_date_depart_mag": "",
                    },
                },
                {
                    "snapshot_id": 3,
                    "reference": "250719",
                    "shipper_name": "AR MADA",
                    "destination_iata": "RUN",
                    "priority": 2,
                    "priority_rank": 5,
                    "carton_count": 10,
                    "equivalent_units": 10,
                    "payload": {
                        "legacy_date_impression": "2025-11-18",
                        "legacy_date_conditionnement": "2025-11-20",
                        "legacy_date_depart_mag": "",
                    },
                },
                {
                    "snapshot_id": 4,
                    "reference": "250722",
                    "shipper_name": "AR MADA",
                    "destination_iata": "RUN",
                    "priority": 2,
                    "priority_rank": 5,
                    "carton_count": 10,
                    "equivalent_units": 10,
                    "payload": {
                        "legacy_date_impression": "2025-11-18",
                        "legacy_date_conditionnement": "2025-12-09",
                        "legacy_date_depart_mag": "",
                    },
                },
                {
                    "snapshot_id": 5,
                    "reference": "250723",
                    "shipper_name": "AR MADA",
                    "destination_iata": "RUN",
                    "priority": 2,
                    "priority_rank": 5,
                    "carton_count": 10,
                    "equivalent_units": 10,
                    "payload": {
                        "legacy_date_impression": "2025-11-18",
                        "legacy_date_conditionnement": "2025-12-09",
                        "legacy_date_depart_mag": "",
                    },
                },
                {
                    "snapshot_id": 6,
                    "reference": "250729",
                    "shipper_name": "AR MADA",
                    "destination_iata": "RUN",
                    "priority": 2,
                    "priority_rank": 5,
                    "carton_count": 10,
                    "equivalent_units": 10,
                    "payload": {
                        "legacy_date_impression": "2025-11-18",
                        "legacy_date_conditionnement": "2025-12-09",
                        "legacy_date_depart_mag": "2026-01-23",
                    },
                },
                {
                    "snapshot_id": 7,
                    "reference": "250771",
                    "shipper_name": "AR MADA",
                    "destination_iata": "RUN",
                    "priority": 2,
                    "priority_rank": 5,
                    "carton_count": 10,
                    "equivalent_units": 10,
                    "payload": {
                        "legacy_date_impression": "2025-12-08",
                        "legacy_date_conditionnement": "2025-12-09",
                        "legacy_date_depart_mag": "",
                    },
                },
            ],
            "flights": [
                {
                    "snapshot_id": 29,
                    "flight_number": "AF652",
                    "departure_date": "2026-03-04",
                    "departure_time": "18:20",
                },
                {
                    "snapshot_id": 55,
                    "flight_number": "AF652",
                    "departure_date": "2026-03-06",
                    "departure_time": "18:20",
                },
            ],
        }
        compatibility = {
            shipment["snapshot_id"]: [(29, 13), (55, 19)] for shipment in payload["shipments"]
        }
        assignments = [
            {
                "shipment_snapshot_id": 3,
                "flight_snapshot_id": 29,
                "volunteer_snapshot_id": 13,
                "assigned_carton_count": 10,
                "equivalent_units": 10,
                "priority": 2,
                "priority_rank": 5,
                "route_pos": 1,
                "physical_flight_key": "2026-03-04|18:20|AF652",
                "reference": "250719",
                "departure_date": "2026-03-04",
            },
            {
                "shipment_snapshot_id": 4,
                "flight_snapshot_id": 29,
                "volunteer_snapshot_id": 13,
                "assigned_carton_count": 10,
                "equivalent_units": 10,
                "priority": 2,
                "priority_rank": 5,
                "route_pos": 1,
                "physical_flight_key": "2026-03-04|18:20|AF652",
                "reference": "250722",
                "departure_date": "2026-03-04",
            },
            {
                "shipment_snapshot_id": 5,
                "flight_snapshot_id": 55,
                "volunteer_snapshot_id": 19,
                "assigned_carton_count": 10,
                "equivalent_units": 10,
                "priority": 2,
                "priority_rank": 5,
                "route_pos": 1,
                "physical_flight_key": "2026-03-06|18:20|AF652",
                "reference": "250723",
                "departure_date": "2026-03-06",
            },
            {
                "shipment_snapshot_id": 6,
                "flight_snapshot_id": 55,
                "volunteer_snapshot_id": 19,
                "assigned_carton_count": 10,
                "equivalent_units": 10,
                "priority": 2,
                "priority_rank": 5,
                "route_pos": 1,
                "physical_flight_key": "2026-03-06|18:20|AF652",
                "reference": "250729",
                "departure_date": "2026-03-06",
            },
        ]

        canonicalized = planning_solver._canonicalize_legacy_equal_weight_assignments(
            assignments,
            payload=payload,
            compatibility=compatibility,
        )

        self.assertEqual(
            sorted(
                (
                    item["reference"],
                    item["flight_snapshot_id"],
                    item["volunteer_snapshot_id"],
                )
                for item in canonicalized
            ),
            [
                ("250706", 55, 19),
                ("250722", 29, 13),
                ("250729", 29, 13),
                ("250771", 55, 19),
            ],
        )

    def _create_parameter_set_with_destination_rules(self, *, user):
        parameter_set = PlanningParameterSet.objects.create(
            name="Legacy parity mini case",
            created_by=user,
        )
        for iata_code, city, country, max_cartons in (
            ("NSI", "YAOUNDE", "CAMEROUN", 20),
            ("RUN", "LA REUNION", "REUNION", 40),
        ):
            correspondent = Contact.objects.create(
                name=f"Legacy {iata_code}",
                contact_type=ContactType.ORGANIZATION,
                is_active=True,
            )
            destination = Destination.objects.create(
                city=city,
                iata_code=iata_code,
                country=country,
                correspondent_contact=correspondent,
            )
            PlanningDestinationRule.objects.create(
                parameter_set=parameter_set,
                destination=destination,
                label=city,
                weekly_frequency=0,
                max_cartons_per_flight=max_cartons,
                priority=0,
            )
        return parameter_set

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

    def test_solve_run_prefers_lower_legacy_priority_values_when_capacity_is_limited(self):
        user = get_user_model().objects.create_user(
            username="planner-ortools-priority@example.com",
            email="planner-ortools-priority@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        run = PlanningRun.objects.create(
            week_start="2026-03-02",
            week_end="2026-03-08",
            status=PlanningRunStatus.READY,
            created_by=user,
        )
        PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="BE-PRIO-005",
            shipper_name="ASF",
            destination_iata="RUN",
            priority=5,
            carton_count=10,
            equivalent_units=10,
        )
        for reference in ("BE-PRIO-002-A", "BE-PRIO-002-B"):
            PlanningShipmentSnapshot.objects.create(
                run=run,
                shipment_reference=reference,
                shipper_name="AR MADA",
                destination_iata="RUN",
                priority=2,
                carton_count=10,
                equivalent_units=10,
            )
        for label in ("FILOU Thierry", "PIERSON Gilles"):
            PlanningVolunteerSnapshot.objects.create(
                run=run,
                volunteer_label=label,
                availability_summary={
                    "slot_count": 1,
                    "slots": [
                        {
                            "date": "2026-03-04",
                            "start_time": "05:00",
                            "end_time": "21:00",
                        }
                    ],
                },
            )
        PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF652",
            departure_date=date(2026, 3, 4),
            destination_iata="RUN",
            capacity_units=20,
            payload={"departure_time": "18:20", "routing": "CDG-RUN", "route_pos": 1},
        )

        version = solve_run(run)

        assignments = list(
            version.assignments.order_by("shipment_snapshot__shipment_reference").values_list(
                "shipment_snapshot__shipment_reference",
                flat=True,
            )
        )
        self.assertEqual(assignments, ["BE-PRIO-002-A", "BE-PRIO-002-B"])

    def test_solve_run_prefers_type_priority_rank_from_payload_over_snapshot_priority(self):
        user = get_user_model().objects.create_user(
            username="planner-ortools-type-priority@example.com",
            email="planner-ortools-type-priority@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        run = PlanningRun.objects.create(
            week_start="2026-03-02",
            week_end="2026-03-08",
            status=PlanningRunStatus.READY,
            created_by=user,
        )
        PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="BE-TYPE-MM",
            shipper_name="ASF",
            destination_iata="RUN",
            priority=2,
            carton_count=10,
            equivalent_units=10,
            payload={"legacy_type_priority": 5},
        )
        for reference in ("BE-TYPE-CN-A", "BE-TYPE-CN-B"):
            PlanningShipmentSnapshot.objects.create(
                run=run,
                shipment_reference=reference,
                shipper_name="ASF",
                destination_iata="RUN",
                priority=5,
                carton_count=10,
                equivalent_units=10,
                payload={"legacy_type_priority": 4},
            )
        for label in ("FILOU Thierry", "PIERSON Gilles"):
            PlanningVolunteerSnapshot.objects.create(
                run=run,
                volunteer_label=label,
                availability_summary={
                    "slot_count": 1,
                    "slots": [
                        {
                            "date": "2026-03-04",
                            "start_time": "05:00",
                            "end_time": "21:00",
                        }
                    ],
                },
            )
        PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF652",
            departure_date=date(2026, 3, 4),
            destination_iata="RUN",
            capacity_units=20,
            payload={"departure_time": "18:20", "routing": "CDG-RUN", "route_pos": 1},
        )

        version = solve_run(run)

        assignments = list(
            version.assignments.order_by("shipment_snapshot__shipment_reference").values_list(
                "shipment_snapshot__shipment_reference",
                flat=True,
            )
        )
        self.assertEqual(assignments, ["BE-TYPE-CN-A", "BE-TYPE-CN-B"])

    def test_solve_run_matches_legacy_mini_case_for_flight_choice_and_run_subset(self):
        user = get_user_model().objects.create_user(
            username="planner-ortools-legacy-mini@example.com",
            email="planner-ortools-legacy-mini@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        parameter_set = self._create_parameter_set_with_destination_rules(user=user)
        run = PlanningRun.objects.create(
            week_start="2026-03-02",
            week_end="2026-03-08",
            status=PlanningRunStatus.READY,
            created_by=user,
            parameter_set=parameter_set,
        )

        for reference, priority, type_priority in (
            ("250705", 5, 5),
            ("250706", 5, 5),
            ("250719", 2, 5),
            ("250722", 2, 5),
            ("250723", 2, 5),
            ("250724", 2, 5),
            ("250729", 2, 5),
            ("250771", 2, 5),
        ):
            PlanningShipmentSnapshot.objects.create(
                run=run,
                shipment_reference=reference,
                shipper_name="ASF",
                destination_iata="RUN",
                priority=priority,
                carton_count=10,
                equivalent_units=10,
                payload={"legacy_type_priority": type_priority},
            )

        PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="260098",
            shipper_name="ASF",
            destination_iata="NSI",
            priority=4,
            carton_count=10,
            equivalent_units=10,
            payload={"legacy_type_priority": 4},
        )

        PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="COURTOIS Alain",
            availability_summary={
                "slot_count": 2,
                "slots": [
                    {
                        "date": "2026-03-02",
                        "start_time": "06:30",
                        "end_time": "14:00",
                    },
                    {
                        "date": "2026-03-03",
                        "start_time": "06:30",
                        "end_time": "14:00",
                    },
                ],
            },
            payload={"legacy_id": 14},
        )
        PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="FILOU Thierry",
            availability_summary={
                "slot_count": 1,
                "slots": [
                    {
                        "date": "2026-03-04",
                        "start_time": "10:00",
                        "end_time": "18:30",
                    }
                ],
            },
            payload={"legacy_id": 19},
        )
        PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="PIERSON Gilles",
            availability_summary={
                "slot_count": 2,
                "slots": [
                    {
                        "date": "2026-03-03",
                        "start_time": "05:00",
                        "end_time": "21:00",
                    },
                    {
                        "date": "2026-03-06",
                        "start_time": "05:00",
                        "end_time": "21:00",
                    },
                ],
            },
            payload={"legacy_id": 25},
        )

        for flight_number, departure_date, destination_iata, departure_time, routing, route_pos in (
            ("AF908", date(2026, 3, 2), "NSI", "11:10", "CDG-NDJ-NSI", 2),
            ("AF910", date(2026, 3, 3), "NSI", "11:00", "CDG-NSI", 1),
            ("AF652", date(2026, 3, 4), "RUN", "18:20", "CDG-RUN", 1),
            ("AF652", date(2026, 3, 6), "RUN", "18:20", "CDG-RUN", 1),
        ):
            PlanningFlightSnapshot.objects.create(
                run=run,
                flight_number=flight_number,
                departure_date=departure_date,
                destination_iata=destination_iata,
                capacity_units=40 if destination_iata == "RUN" else 20,
                payload={
                    "departure_time": departure_time,
                    "routing": routing,
                    "route_pos": route_pos,
                },
            )

        version = solve_run(run)

        assignments = set(
            version.assignments.values_list(
                "shipment_snapshot__shipment_reference",
                "flight_snapshot__flight_number",
                "volunteer_snapshot__volunteer_label",
            )
        )
        self.assertEqual(version.assignments.count(), 5)
        self.assertTrue(
            any(
                reference == "260098" and flight in {"AF908", "AF910"}
                for reference, flight, _volunteer in assignments
            )
        )
