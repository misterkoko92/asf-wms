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
from wms.planning.communications import generate_version_drafts
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

    def test_build_version_dashboard_formats_operator_header_summary(self):
        version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.DRAFT,
            created_by=self.user,
        )
        volunteer = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="COURTOIS Alain",
        )
        shipment = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="260128",
            shipper_name="ASF",
            destination_iata="NSI",
            priority=1,
            carton_count=10,
            equivalent_units=10,
            payload={
                "legacy_type": "MM",
                "legacy_destinataire": "CORRESPONDANT",
            },
        )
        flight = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF908",
            departure_date="2026-03-10",
            destination_iata="NSI",
            capacity_units=20,
            payload={"departure_time": "11:10", "routing": "CDG-NSI"},
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment,
            volunteer_snapshot=volunteer,
            flight_snapshot=flight,
            assigned_carton_count=10,
            source=PlanningAssignmentSource.SOLVER,
            sequence=1,
        )

        dashboard = build_version_dashboard(version)

        self.assertEqual(
            dashboard["header"]["title"],
            "Planning Semaine 11 (du 09/03/26 au 15/03/26)",
        )
        self.assertEqual(dashboard["header"]["status_badge"], "Brouillon")
        self.assertEqual(dashboard["header"]["summary"]["flight_mode"], "hybrid")
        self.assertEqual(dashboard["header"]["summary"]["used_flight_count"], 1)
        self.assertEqual(dashboard["header"]["summary"]["available_carton_count"], 10)
        self.assertEqual(dashboard["header"]["summary"]["assigned_carton_count"], 10)
        self.assertEqual(dashboard["header"]["summary"]["available_volunteer_count"], 1)
        self.assertEqual(dashboard["header"]["summary"]["assigned_volunteer_count"], 1)

    def test_build_version_dashboard_exposes_detailed_planning_rows(self):
        version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.DRAFT,
            created_by=self.user,
        )
        volunteer = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="COURTOIS Alain",
        )
        shipment = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="260128",
            shipper_name="ASF",
            destination_iata="NSI",
            priority=1,
            carton_count=10,
            equivalent_units=10,
            payload={
                "legacy_type": "MM",
                "legacy_destinataire": "CORRESPONDANT",
            },
        )
        flight = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF908",
            departure_date="2026-03-10",
            destination_iata="NSI",
            capacity_units=20,
            payload={"departure_time": "11:10", "routing": "CDG-NSI"},
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment,
            volunteer_snapshot=volunteer,
            flight_snapshot=flight,
            assigned_carton_count=10,
            source=PlanningAssignmentSource.SOLVER,
            sequence=1,
        )

        dashboard = build_version_dashboard(version)

        self.assertEqual(len(dashboard["planning_rows"]), 1)
        row = dashboard["planning_rows"][0]
        self.assertEqual(row["assignment_id"], version.assignments.get().pk)
        self.assertEqual(row["flight_date_label"], "Mardi 10/03/2026")
        self.assertEqual(row["flight_time_label"], "11h10")
        self.assertEqual(row["flight_number_label"], "AF 908")
        self.assertEqual(row["destination_iata"], "NSI")
        self.assertEqual(row["routing"], "CDG-NSI")
        self.assertEqual(row["shipment_reference"], "260128")
        self.assertEqual(row["assigned_carton_count"], 10)
        self.assertEqual(row["equivalent_units"], 10)
        self.assertEqual(row["volunteer_label"], "COURTOIS Alain")
        self.assertEqual(row["shipment_type"], "MM")
        self.assertEqual(row["shipper_name"], "ASF")
        self.assertEqual(row["recipient_label"], "CORRESPONDANT")
        self.assertEqual(row["status"], "proposed")
        self.assertEqual(row["notes"], "")
        self.assertEqual(row["source"], "solver")

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

    def test_build_version_dashboard_exposes_week_view_tables(self):
        version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.DRAFT,
            created_by=self.user,
        )
        volunteer_alice = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Alice",
            availability_summary={
                "slots": [
                    {"date": "2026-03-10", "start_time": "07:00", "end_time": "18:00"},
                    {"date": "2026-03-11", "start_time": "08:00", "end_time": "17:00"},
                ],
                "unavailable_dates": [],
            },
        )
        PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Bob",
            availability_summary={
                "slots": [{"date": "2026-03-11", "start_time": "09:00", "end_time": "12:00"}],
                "unavailable_dates": [],
            },
        )
        shipment_nsi_a = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="260128",
            shipper_name="ASF",
            destination_iata="NSI",
            priority=1,
            carton_count=4,
            equivalent_units=4,
        )
        PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="260129",
            shipper_name="ASF",
            destination_iata="NSI",
            priority=2,
            carton_count=2,
            equivalent_units=2,
        )
        shipment_run = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="260130",
            shipper_name="ASF",
            destination_iata="RUN",
            priority=3,
            carton_count=3,
            equivalent_units=3,
        )
        flight_nsi = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF908",
            departure_date="2026-03-10",
            destination_iata="NSI",
            capacity_units=10,
            payload={"departure_time": "11:10", "routing": "CDG-NSI"},
        )
        PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF910",
            departure_date="2026-03-11",
            destination_iata="NSI",
            capacity_units=8,
            payload={"departure_time": "13:10", "routing": "CDG-NSI"},
        )
        flight_run = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF652",
            departure_date="2026-03-11",
            destination_iata="RUN",
            capacity_units=12,
            payload={"departure_time": "18:20", "routing": "CDG-RUN"},
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment_run,
            volunteer_snapshot=volunteer_alice,
            flight_snapshot=flight_run,
            assigned_carton_count=3,
            source=PlanningAssignmentSource.SOLVER,
            sequence=1,
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment_nsi_a,
            volunteer_snapshot=volunteer_alice,
            flight_snapshot=flight_nsi,
            assigned_carton_count=4,
            source=PlanningAssignmentSource.SOLVER,
            sequence=2,
        )

        dashboard = build_version_dashboard(version)

        self.assertEqual(
            [item["short_label"] for item in dashboard["week_view"]["day_labels"][:3]],
            ["Lun 09/03", "Mar 10/03", "Mer 11/03"],
        )
        volunteer_row = dashboard["week_view"]["volunteer_rows"][0]
        self.assertEqual(volunteer_row["display_label"], "Alice (2)")
        self.assertEqual(volunteer_row["cells"][1]["label"], "07h00-18h00")
        self.assertEqual(volunteer_row["cells"][1]["status"], "available")
        self.assertEqual(volunteer_row["cells"][2]["label"], "08h00-17h00")
        flight_row_nsi = dashboard["week_view"]["flight_rows"][0]
        self.assertEqual(flight_row_nsi["destination_label"], "NSI (6)")
        self.assertEqual(
            flight_row_nsi["cells"][1]["entries"][0]["label"],
            "11h10 · AF 908 · CDG-NSI",
        )
        self.assertEqual(flight_row_nsi["cells"][1]["entries"][0]["status"], "used")

    def test_build_version_dashboard_exposes_planning_summary_per_volunteer(self):
        version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.DRAFT,
            created_by=self.user,
        )
        volunteer_alice = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Alice",
            availability_summary={
                "slots": [
                    {"date": "2026-03-10", "start_time": "07:00", "end_time": "18:00"},
                    {"date": "2026-03-11", "start_time": "08:00", "end_time": "17:00"},
                ],
                "unavailable_dates": [],
            },
        )
        PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Bob",
            availability_summary={"slots": [], "unavailable_dates": []},
        )
        shipment_a = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="260128",
            shipper_name="ASF",
            destination_iata="NSI",
            priority=1,
            carton_count=4,
            equivalent_units=4,
        )
        shipment_b = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="260129",
            shipper_name="ASF",
            destination_iata="RUN",
            priority=2,
            carton_count=2,
            equivalent_units=2,
        )
        flight_a = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF908",
            departure_date="2026-03-10",
            destination_iata="NSI",
            capacity_units=10,
            payload={"departure_time": "11:10", "routing": "CDG-NSI"},
        )
        flight_b = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF652",
            departure_date="2026-03-11",
            destination_iata="RUN",
            capacity_units=12,
            payload={"departure_time": "18:20", "routing": "CDG-RUN"},
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment_a,
            volunteer_snapshot=volunteer_alice,
            flight_snapshot=flight_a,
            assigned_carton_count=4,
            source=PlanningAssignmentSource.SOLVER,
            sequence=1,
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment_b,
            volunteer_snapshot=volunteer_alice,
            flight_snapshot=flight_b,
            assigned_carton_count=2,
            source=PlanningAssignmentSource.MANUAL,
            sequence=2,
        )

        dashboard = build_version_dashboard(version)

        alice_row = dashboard["planning_summary"]["volunteer_rows"][0]
        self.assertEqual(alice_row["volunteer_label"], "Alice")
        self.assertEqual(alice_row["availability_count"], 2)
        self.assertEqual(alice_row["assigned_day_count"], 2)
        self.assertEqual(alice_row["assigned_flight_count"], 2)
        self.assertEqual(alice_row["assigned_shipment_count"], 2)
        self.assertEqual(alice_row["assigned_carton_count"], 6)
        self.assertEqual(alice_row["assigned_equivalent_units"], 6)
        self.assertEqual(
            alice_row["availability_label"],
            "10/03/26 07h00-18h00, 11/03/26 08h00-17h00",
        )

    def test_build_version_dashboard_exposes_destination_summary_rows(self):
        version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.DRAFT,
            created_by=self.user,
        )
        volunteer_alice = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Alice",
        )
        shipment_planned = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="260128",
            shipper_name="ASF",
            destination_iata="NSI",
            priority=1,
            carton_count=5,
            equivalent_units=5,
            payload={
                "legacy_type": "MM",
                "legacy_destinataire": "CORRESPONDANT",
            },
        )
        shipment_unplanned = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="260129",
            shipper_name="ASF 2",
            destination_iata="NSI",
            priority=2,
            carton_count=3,
            equivalent_units=4,
            payload={
                "legacy_type": "AR",
                "legacy_destinataire": "HOPITAL",
            },
        )
        flight = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF908",
            departure_date="2026-03-10",
            destination_iata="NSI",
            capacity_units=12,
            payload={"departure_time": "11:10", "routing": "CDG-NSI"},
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment_planned,
            volunteer_snapshot=volunteer_alice,
            flight_snapshot=flight,
            assigned_carton_count=5,
            source=PlanningAssignmentSource.SOLVER,
            sequence=1,
        )

        dashboard = build_version_dashboard(version)

        self.assertIn("destination_groups", dashboard["planning_summary"])
        self.assertEqual(len(dashboard["planning_summary"]["destination_groups"]), 1)
        group = dashboard["planning_summary"]["destination_groups"][0]
        summary_row = group["summary_row"]
        self.assertEqual(group["destination_iata"], "NSI")
        self.assertEqual(summary_row["destination_iata"], "NSI")
        self.assertEqual(summary_row["shipment_reference"], "1 / 2")
        self.assertEqual(summary_row["status_label"], "1 / 2")
        self.assertEqual(summary_row["carton_count_label"], "5 / 8")
        self.assertEqual(summary_row["equivalent_units_label"], "5 / 9")
        self.assertEqual(summary_row["shipment_type"], "")
        self.assertEqual(summary_row["shipper_name"], "")
        self.assertEqual(summary_row["recipient_label"], "")

        self.assertEqual(len(group["shipment_rows"]), 2)
        planned_row = group["shipment_rows"][0]
        unplanned_row = group["shipment_rows"][1]
        self.assertEqual(planned_row["shipment_reference"], "260128")
        self.assertEqual(planned_row["status_label"], "Planifié")
        self.assertEqual(planned_row["carton_count"], 5)
        self.assertEqual(planned_row["equivalent_units"], 5)
        self.assertEqual(planned_row["shipment_type"], "MM")
        self.assertEqual(planned_row["shipper_name"], "ASF")
        self.assertEqual(planned_row["recipient_label"], "CORRESPONDANT")
        self.assertEqual(unplanned_row["shipment_reference"], "260129")
        self.assertEqual(unplanned_row["status_label"], "Non partant")
        self.assertEqual(unplanned_row["carton_count"], 3)
        self.assertEqual(unplanned_row["equivalent_units"], 4)
        self.assertEqual(unplanned_row["shipment_type"], "AR")
        self.assertEqual(unplanned_row["shipper_name"], "ASF 2")
        self.assertEqual(unplanned_row["recipient_label"], "HOPITAL")

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
            channel=CommunicationChannel.WHATSAPP,
            family="whatsapp_benevole",
            recipient_label="Bob",
            recipient_contact="",
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
        self.assertEqual(len(dashboard["communications"]["groups"]), 5)
        self.assertEqual(
            dashboard["communications"]["groups"][0]["family_key"], "whatsapp_benevole"
        )
        whatsapp_drafts = {
            draft["recipient_label"]: draft
            for draft in dashboard["communications"]["groups"][0]["drafts"]
        }
        self.assertEqual(
            whatsapp_drafts["Bob"]["change_status"],
            "new",
        )
        self.assertEqual(
            whatsapp_drafts["Bob"]["subject"],
            "Planning Bob",
        )
        self.assertEqual(
            whatsapp_drafts["Alice"]["change_status"],
            "cancelled",
        )
        self.assertEqual(dashboard["exports"]["artifacts"][0]["label"], "Planning v2")

    def test_build_version_dashboard_prioritizes_changed_communication_groups(self):
        volunteer_alice = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Alice",
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
            status=PlanningVersionStatus.PUBLISHED,
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
            volunteer_snapshot=volunteer_alice,
            flight_snapshot=flight_2,
            assigned_carton_count=3,
            source=PlanningAssignmentSource.MANUAL,
            sequence=1,
        )
        generate_version_drafts(current)

        dashboard = build_version_dashboard(current)

        self.assertEqual(dashboard["communications"]["groups"][0]["change_status"], "changed")
        self.assertTrue(dashboard["communications"]["groups"][0]["is_priority"])
        self.assertFalse(dashboard["communications"]["groups"][0]["is_collapsed"])

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
