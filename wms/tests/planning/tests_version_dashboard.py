from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import (
    CommunicationChannel,
    CommunicationDraft,
    PlanningArtifact,
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
from wms.planning.stats import build_version_stats
from wms.planning.version_dashboard import build_version_dashboard


class PlanningVersionDashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dashboard-planner",
            email="dashboard@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.parameter_set = PlanningParameterSet.objects.create(
            name="Dashboard semaine",
            is_current=True,
            created_by=self.user,
        )
        self.run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            flight_mode="hybrid",
            status=PlanningRunStatus.SOLVED,
            created_by=self.user,
            solver_result={"unassigned_reasons": {}},
        )

    def test_build_version_dashboard_groups_assignments_by_flight(self):
        version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.DRAFT,
            created_by=self.user,
        )
        volunteer_alice = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Alice",
        )
        volunteer_bob = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Bob",
        )
        shipment_1 = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="SHP-001",
            shipper_name="Association A",
            destination_iata="RUN",
            priority=1,
            carton_count=3,
            equivalent_units=3,
        )
        shipment_2 = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="SHP-002",
            shipper_name="Association B",
            destination_iata="ABJ",
            priority=2,
            carton_count=2,
            equivalent_units=2,
        )
        flight_1 = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF652",
            departure_date="2026-03-10",
            destination_iata="RUN",
            capacity_units=20,
            payload={"departure_time": "18:20"},
        )
        flight_2 = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF702",
            departure_date="2026-03-11",
            destination_iata="ABJ",
            capacity_units=10,
            payload={"departure_time": "14:10"},
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment_1,
            volunteer_snapshot=volunteer_alice,
            flight_snapshot=flight_1,
            assigned_carton_count=3,
            source=PlanningAssignmentSource.SOLVER,
            sequence=1,
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment_2,
            volunteer_snapshot=volunteer_bob,
            flight_snapshot=flight_2,
            assigned_carton_count=2,
            source=PlanningAssignmentSource.MANUAL,
            sequence=2,
        )

        dashboard = build_version_dashboard(version)

        self.assertEqual(dashboard["header"]["version_number"], version.number)
        self.assertEqual(dashboard["header"]["flight_mode"], "hybrid")
        self.assertEqual(len(dashboard["flight_groups"]), 2)
        self.assertEqual(dashboard["flight_groups"][0]["flight_number"], "AF652")
        self.assertEqual(dashboard["flight_groups"][0]["used_cartons"], 3)
        self.assertEqual(
            dashboard["flight_groups"][0]["assignments"][0]["shipment_reference"],
            "SHP-001",
        )

    def test_build_version_dashboard_lists_unassigned_shipments_with_reason(self):
        version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.DRAFT,
            created_by=self.user,
        )
        unassigned = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="SHP-UNASSIGNED",
            shipper_name="Association C",
            destination_iata="DSS",
            priority=3,
            carton_count=4,
            equivalent_units=4,
        )
        self.run.solver_result = {
            "unassigned_reasons": {str(unassigned.pk): "no_compatible_candidate"}
        }
        self.run.save(update_fields=["solver_result", "updated_at"])

        dashboard = build_version_dashboard(version)

        self.assertEqual(len(dashboard["unassigned_shipments"]), 1)
        self.assertEqual(
            dashboard["unassigned_shipments"][0]["shipment_reference"],
            "SHP-UNASSIGNED",
        )
        self.assertEqual(
            dashboard["unassigned_shipments"][0]["reason"],
            "Aucune compatibilite complete",
        )

    def test_build_version_dashboard_groups_drafts_and_parent_diff_summary(self):
        volunteer_alice = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Alice",
        )
        volunteer_bob = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Bob",
        )
        shipment = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="SHP-001",
            shipper_name="Association A",
            destination_iata="RUN",
            priority=1,
            carton_count=3,
            equivalent_units=3,
        )
        flight_1 = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF652",
            departure_date="2026-03-10",
            destination_iata="RUN",
            capacity_units=20,
            payload={"departure_time": "18:20"},
        )
        flight_2 = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF456",
            departure_date="2026-03-11",
            destination_iata="RUN",
            capacity_units=20,
            payload={"departure_time": "19:10"},
        )
        previous = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.PUBLISHED,
            created_by=self.user,
        )
        current = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.DRAFT,
            based_on=previous,
            created_by=self.user,
            change_reason="Maj vendredi",
        )
        PlanningAssignment.objects.create(
            version=previous,
            shipment_snapshot=shipment,
            volunteer_snapshot=volunteer_alice,
            flight_snapshot=flight_1,
            assigned_carton_count=3,
            source=PlanningAssignmentSource.SOLVER,
            sequence=1,
        )
        PlanningAssignment.objects.create(
            version=current,
            shipment_snapshot=shipment,
            volunteer_snapshot=volunteer_bob,
            flight_snapshot=flight_2,
            assigned_carton_count=3,
            source=PlanningAssignmentSource.MANUAL,
            sequence=1,
        )
        CommunicationDraft.objects.create(
            version=current,
            channel=CommunicationChannel.EMAIL,
            recipient_label="Bob",
            recipient_contact="bob@example.com",
            subject="Planning Bob",
            body="Vol AF456",
        )
        PlanningArtifact.objects.create(
            version=current,
            artifact_type="planning_workbook",
            label="Planning v2",
            file_path="/tmp/planning-v2.xlsx",
        )

        dashboard = build_version_dashboard(current)

        self.assertTrue(dashboard["history"]["has_parent"])
        self.assertEqual(dashboard["history"]["assignment_changes"]["changed_count"], 1)
        self.assertEqual(dashboard["communications"]["groups"][0]["recipient_label"], "Bob")
        self.assertTrue(dashboard["communications"]["groups"][0]["changed_since_parent"])
        self.assertEqual(dashboard["exports"]["artifacts"][0]["label"], "Planning v2")

    def test_build_version_stats_exposes_unassigned_and_breakdowns(self):
        version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.PUBLISHED,
            created_by=self.user,
        )
        volunteer = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Alice",
        )
        assigned = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="SHP-001",
            shipper_name="Association A",
            destination_iata="RUN",
            priority=1,
            carton_count=3,
            equivalent_units=3,
        )
        PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="SHP-002",
            shipper_name="Association B",
            destination_iata="DSS",
            priority=2,
            carton_count=4,
            equivalent_units=4,
        )
        flight = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF652",
            departure_date="2026-03-10",
            destination_iata="RUN",
            capacity_units=20,
            payload={"departure_time": "18:20"},
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=assigned,
            volunteer_snapshot=volunteer,
            flight_snapshot=flight,
            assigned_carton_count=3,
            source=PlanningAssignmentSource.MANUAL,
            sequence=1,
        )

        stats = build_version_stats(version)

        self.assertEqual(stats["unassigned_count"], 1)
        self.assertEqual(stats["destination_breakdown"][0]["destination_iata"], "RUN")
        self.assertEqual(stats["volunteer_breakdown"][0]["volunteer_label"], "Alice")
        self.assertEqual(stats["flight_load_breakdown"][0]["flight_number"], "AF652")
