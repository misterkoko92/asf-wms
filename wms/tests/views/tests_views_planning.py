import re
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import FileResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from wms.helper_install import build_helper_install_context
from wms.models import (
    PlanningAssignment,
    PlanningAssignmentSource,
    PlanningFlightSnapshot,
    PlanningIssue,
    PlanningParameterSet,
    PlanningRun,
    PlanningRunStatus,
    PlanningShipmentSnapshot,
    PlanningVersion,
    PlanningVersionStatus,
    PlanningVolunteerSnapshot,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
)
from wms.planning.communications import generate_version_drafts


class PlanningViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.staff_user = get_user_model().objects.create_user(
            username="planning-staff",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="planning-admin",
            email="planning-admin@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.parameter_set = PlanningParameterSet.objects.create(
            name="Semaine 11",
            is_current=True,
        )

    def make_version_with_assignment(self, *, status=PlanningVersionStatus.DRAFT):
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            status=PlanningRunStatus.SOLVED,
            created_by=self.staff_user,
        )
        version = PlanningVersion.objects.create(
            run=run,
            status=status,
            created_by=self.staff_user,
        )
        shipment_snapshot = PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="SHP-001",
            carton_count=3,
            equivalent_units=3,
        )
        volunteer_alice = PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="Alice",
        )
        volunteer_bob = PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="Bob",
        )
        flight_af123 = PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF123",
            departure_date="2026-03-10",
            destination_iata="CDG",
        )
        flight_af456 = PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF456",
            departure_date="2026-03-11",
            destination_iata="NCE",
        )
        assignment = PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment_snapshot,
            volunteer_snapshot=volunteer_alice,
            flight_snapshot=flight_af123,
            assigned_carton_count=3,
            source=PlanningAssignmentSource.SOLVER,
            sequence=1,
        )
        return version, assignment, volunteer_bob, flight_af456

    def make_operator_version(self):
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            status=PlanningRunStatus.SOLVED,
            created_by=self.staff_user,
        )
        version = PlanningVersion.objects.create(
            run=run,
            status=PlanningVersionStatus.DRAFT,
            created_by=self.staff_user,
        )
        assigned_shipment = PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="260128",
            shipper_name="ASF",
            destination_iata="NSI",
            carton_count=4,
            equivalent_units=4,
            payload={"legacy_type": "MM", "legacy_destinataire": "CORRESPONDANT"},
        )
        unassigned_shipment = PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="260129",
            shipper_name="ASF",
            destination_iata="NSI",
            carton_count=2,
            equivalent_units=2,
            payload={"legacy_type": "MM", "legacy_destinataire": "DESTINATAIRE"},
        )
        volunteer_alice = PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="Alice",
            availability_summary={
                "slots": [
                    {"date": "2026-03-10", "start_time": "07:00", "end_time": "18:00"},
                    {"date": "2026-03-11", "start_time": "07:00", "end_time": "18:00"},
                ],
                "unavailable_dates": [],
            },
        )
        volunteer_bob = PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="Bob",
            availability_summary={
                "slots": [{"date": "2026-03-11", "start_time": "07:00", "end_time": "18:00"}],
                "unavailable_dates": [],
            },
        )
        flight_af908 = PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF908",
            departure_date="2026-03-10",
            destination_iata="NSI",
            capacity_units=10,
            payload={"departure_time": "11:10", "routing": "CDG-NSI"},
        )
        flight_af910 = PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF910",
            departure_date="2026-03-11",
            destination_iata="NSI",
            capacity_units=10,
            payload={"departure_time": "13:10", "routing": "CDG-NSI"},
        )
        assignment = PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=assigned_shipment,
            volunteer_snapshot=volunteer_alice,
            flight_snapshot=flight_af908,
            assigned_carton_count=4,
            source=PlanningAssignmentSource.SOLVER,
            sequence=1,
        )
        return {
            "version": version,
            "assignment": assignment,
            "assigned_shipment": assigned_shipment,
            "unassigned_shipment": unassigned_shipment,
            "volunteer_alice": volunteer_alice,
            "volunteer_bob": volunteer_bob,
            "flight_af908": flight_af908,
            "flight_af910": flight_af910,
        }

    def make_published_version_with_live_shipment(self):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.PACKED,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
        )
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            status=PlanningRunStatus.SOLVED,
            created_by=self.staff_user,
        )
        version = PlanningVersion.objects.create(
            run=run,
            status=PlanningVersionStatus.PUBLISHED,
            created_by=self.staff_user,
        )
        shipment_snapshot = PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment=shipment,
            shipment_reference=shipment.reference,
            carton_count=3,
            equivalent_units=3,
        )
        volunteer = PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="Alice",
        )
        flight = PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF123",
            departure_date="2026-03-10",
            destination_iata="CDG",
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment_snapshot,
            volunteer_snapshot=volunteer,
            flight_snapshot=flight,
            assigned_carton_count=3,
            source=PlanningAssignmentSource.MANUAL,
            sequence=1,
        )
        return version, shipment

    def make_published_version_with_communication_drafts(
        self, *, recipient_email="destinataire@example.com"
    ):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.PACKED,
            shipper_name="Hopital Saint Joseph",
            recipient_name="Centre Medical",
            destination_address="1 Rue Test",
            destination_country="Cameroun",
            created_by=self.staff_user,
        )
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            status=PlanningRunStatus.SOLVED,
            created_by=self.staff_user,
        )
        version = PlanningVersion.objects.create(
            run=run,
            status=PlanningVersionStatus.PUBLISHED,
            created_by=self.staff_user,
        )
        shipment_snapshot = PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment=shipment,
            shipment_reference=shipment.reference,
            shipper_name="Hopital Saint Joseph",
            destination_iata="NSI",
            carton_count=10,
            equivalent_units=12,
            payload={
                "destination_city": "YAOUNDE",
                "legacy_type": "MM",
                "legacy_destinataire": "Centre Medical",
                "shipper_reference": {
                    "contact_name": "Hopital Saint Joseph",
                    "notification_emails": ["expediteur@example.com"],
                },
                "recipient_reference": {
                    "contact_name": "Centre Medical",
                    "notification_emails": [recipient_email] if recipient_email else [],
                },
                "correspondent_reference": {
                    "contact_name": "Jean Dupont",
                    "contact_title": "M.",
                    "contact_first_name": "Jean",
                    "contact_last_name": "Dupont",
                    "notification_emails": ["correspondant@example.com"],
                    "phone": "0601020304",
                },
            },
        )
        volunteer = PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="COURTOIS Alain",
            payload={"phone": "0611223344", "first_name": "Alain", "last_name": "COURTOIS"},
        )
        flight = PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF908",
            departure_date="2026-03-09",
            destination_iata="NSI",
            capacity_units=20,
            payload={"departure_time": "11:10", "routing": "CDG-NSI"},
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment_snapshot,
            volunteer_snapshot=volunteer,
            flight_snapshot=flight,
            assigned_carton_count=10,
            source=PlanningAssignmentSource.MANUAL,
            sequence=1,
        )
        generate_version_drafts(version)
        return {
            "version": version,
            "shipment": shipment,
            "shipment_snapshot": shipment_snapshot,
        }

    def test_planning_run_list_requires_staff(self):
        response = self.client.get(reverse("planning:run_list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_staff_can_open_planning_run_list(self):
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            created_by=self.staff_user,
        )
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:run_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2026-03-09")
        self.assertEqual(response.context["active"], "planning_runs")

    def test_run_create_page_keeps_primary_and_cancel_actions(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:run_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="week_start"')
        self.assertContains(response, 'name="week_end"')
        self.assertContains(response, 'name="parameter_set"')
        self.assertContains(response, 'name="flight_mode"')
        self.assertContains(
            response,
            '<button type="submit" class="btn btn-primary">Creer</button>',
            html=True,
        )
        self.assertContains(
            response,
            f'<a class="btn btn-tertiary" href="{reverse("planning:run_list")}">Annuler</a>',
            html=True,
        )

    def test_staff_can_create_run(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("planning:run_create"),
            {
                "week_start": "2026-03-16",
                "week_end": "2026-03-22",
                "parameter_set": str(self.parameter_set.pk),
                "flight_mode": "hybrid",
            },
        )

        run = PlanningRun.objects.get(week_start="2026-03-16")
        self.assertRedirects(response, reverse("planning:run_detail", args=[run.pk]))
        self.assertEqual(run.created_by, self.staff_user)

    def test_run_detail_shows_issues_and_generate_button_for_draft_run(self):
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            status=PlanningRunStatus.DRAFT,
            created_by=self.staff_user,
        )
        PlanningIssue.objects.create(
            run=run,
            severity="warning",
            code="missing_shipper_reference",
            message="Portal contact missing",
        )
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:run_detail", args=[run.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Portal contact missing")
        self.assertContains(response, reverse("planning:run_solve", args=[run.pk]))
        self.assertContains(response, "Generer le planning")

    @mock.patch("wms.views_planning.solve_run")
    @mock.patch("wms.views_planning.prepare_run_inputs")
    def test_run_solve_post_prepares_draft_run_then_redirects_to_created_version(
        self,
        prepare_run_inputs_mock,
        solve_run_mock,
    ):
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            status=PlanningRunStatus.DRAFT,
            created_by=self.staff_user,
        )
        version = PlanningVersion.objects.create(run=run, created_by=self.staff_user)

        def prepare_stub(prepared_run):
            prepared_run.status = PlanningRunStatus.READY
            prepared_run.save(update_fields=["status", "updated_at"])
            return prepared_run

        prepare_run_inputs_mock.side_effect = prepare_stub
        solve_run_mock.return_value = version
        self.client.force_login(self.staff_user)

        response = self.client.post(reverse("planning:run_solve", args=[run.pk]))

        prepare_run_inputs_mock.assert_called_once()
        solve_run_mock.assert_called_once_with(run)
        self.assertRedirects(response, reverse("planning:version_detail", args=[version.pk]))

    @mock.patch("wms.views_planning.solve_run")
    @mock.patch("wms.views_planning.prepare_run_inputs")
    def test_run_solve_post_redirects_back_to_run_when_validation_fails(
        self,
        prepare_run_inputs_mock,
        solve_run_mock,
    ):
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            status=PlanningRunStatus.DRAFT,
            created_by=self.staff_user,
        )
        PlanningIssue.objects.create(
            run=run,
            severity="error",
            code="missing_destination_rule",
            message="Destination rule missing",
        )

        def prepare_stub(prepared_run):
            prepared_run.status = PlanningRunStatus.VALIDATION_FAILED
            prepared_run.save(update_fields=["status", "updated_at"])
            return prepared_run

        prepare_run_inputs_mock.side_effect = prepare_stub
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("planning:run_solve", args=[run.pk]),
            follow=True,
        )

        solve_run_mock.assert_not_called()
        self.assertRedirects(response, reverse("planning:run_detail", args=[run.pk]))
        self.assertContains(response, "Destination rule missing")

    def test_staff_can_update_draft_version_assignments(self):
        version, assignment, volunteer_bob, flight_af456 = self.make_version_with_assignment()
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("planning:version_detail", args=[version.pk]),
            {
                "assignment_action": "save",
                "assignments-TOTAL_FORMS": "1",
                "assignments-INITIAL_FORMS": "1",
                "assignments-MIN_NUM_FORMS": "0",
                "assignments-MAX_NUM_FORMS": "1000",
                "assignments-0-id": str(assignment.pk),
                "assignments-0-volunteer_snapshot": str(volunteer_bob.pk),
                "assignments-0-flight_snapshot": str(flight_af456.pk),
                "assignments-0-assigned_carton_count": "5",
                "assignments-0-notes": "Manual swap",
                "assignments-0-status": "confirmed",
            },
        )

        assignment.refresh_from_db()
        self.assertRedirects(response, reverse("planning:version_detail", args=[version.pk]))
        self.assertEqual(assignment.volunteer_snapshot, volunteer_bob)
        self.assertEqual(assignment.flight_snapshot, flight_af456)
        self.assertEqual(assignment.assigned_carton_count, 5)
        self.assertEqual(assignment.source, PlanningAssignmentSource.MANUAL)

    def test_staff_can_delete_assignment_from_operator_table(self):
        data = self.make_operator_version()
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("planning:version_detail", args=[data["version"].pk]),
            {
                "assignment_action": "delete",
                "assignment_id": str(data["assignment"].pk),
            },
        )

        self.assertRedirects(
            response,
            reverse("planning:version_detail", args=[data["version"].pk]),
        )
        self.assertFalse(PlanningAssignment.objects.filter(pk=data["assignment"].pk).exists())

    def test_staff_can_update_assignment_from_operator_row_form(self):
        data = self.make_operator_version()
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("planning:version_detail", args=[data["version"].pk]),
            {
                "assignment_action": "update",
                "assignment_id": str(data["assignment"].pk),
                "volunteer_snapshot": str(data["volunteer_bob"].pk),
                "flight_snapshot": str(data["flight_af910"].pk),
            },
        )

        data["assignment"].refresh_from_db()
        self.assertRedirects(
            response,
            reverse("planning:version_detail", args=[data["version"].pk]),
        )
        self.assertEqual(data["assignment"].volunteer_snapshot, data["volunteer_bob"])
        self.assertEqual(data["assignment"].flight_snapshot, data["flight_af910"])
        self.assertEqual(data["assignment"].source, PlanningAssignmentSource.MANUAL)

    def test_staff_can_assign_unassigned_shipment_from_operator_block(self):
        data = self.make_operator_version()
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("planning:version_detail", args=[data["version"].pk]),
            {
                "shipment_action": "assign",
                "shipment_snapshot_id": str(data["unassigned_shipment"].pk),
                "volunteer_snapshot": str(data["volunteer_bob"].pk),
                "flight_snapshot": str(data["flight_af910"].pk),
            },
        )

        created = PlanningAssignment.objects.get(
            version=data["version"],
            shipment_snapshot=data["unassigned_shipment"],
        )
        self.assertRedirects(
            response,
            reverse("planning:version_detail", args=[data["version"].pk]),
        )
        self.assertEqual(created.volunteer_snapshot, data["volunteer_bob"])
        self.assertEqual(created.flight_snapshot, data["flight_af910"])
        self.assertEqual(created.source, PlanningAssignmentSource.MANUAL)

    def test_unassigned_operator_block_renders_selected_compatible_volunteer(self):
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            status=PlanningRunStatus.SOLVED,
            created_by=self.staff_user,
        )
        version = PlanningVersion.objects.create(
            run=run,
            status=PlanningVersionStatus.DRAFT,
            created_by=self.staff_user,
        )
        PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="260129",
            shipper_name="ASF",
            destination_iata="NSI",
            carton_count=2,
            equivalent_units=2,
        )
        volunteer_alice = PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="Alice",
            availability_summary={"slots": [], "unavailable_dates": ["2026-03-11"]},
        )
        volunteer_bob = PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="Bob",
            availability_summary={
                "slots": [{"date": "2026-03-12", "start_time": "07:00", "end_time": "18:00"}],
                "unavailable_dates": [],
            },
        )
        PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF908",
            departure_date="2026-03-11",
            destination_iata="NSI",
            capacity_units=10,
            payload={"departure_time": "11:10", "routing": "CDG-NSI"},
        )
        late_flight = PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF910",
            departure_date="2026-03-12",
            destination_iata="NSI",
            capacity_units=10,
            payload={"departure_time": "13:10", "routing": "CDG-NSI"},
        )
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:version_detail", args=[version.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content.decode(),
            rf'<option[^>]*value="{volunteer_bob.pk}"[^>]*selected[^>]*>',
        )
        self.assertRegex(
            response.content.decode(),
            rf'<option[^>]*value="{late_flight.pk}"[^>]*selected[^>]*>',
        )

    def test_staff_gets_precise_reason_when_unassigned_shipment_exceeds_remaining_capacity(self):
        data = self.make_operator_version()
        blocking_shipment = PlanningShipmentSnapshot.objects.create(
            run=data["version"].run,
            shipment_reference="260130",
            shipper_name="ASF",
            destination_iata="NSI",
            carton_count=9,
            equivalent_units=9,
        )
        PlanningAssignment.objects.create(
            version=data["version"],
            shipment_snapshot=blocking_shipment,
            volunteer_snapshot=data["volunteer_alice"],
            flight_snapshot=data["flight_af910"],
            assigned_carton_count=9,
            source=PlanningAssignmentSource.MANUAL,
            sequence=2,
        )
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("planning:version_detail", args=[data["version"].pk]),
            {
                "shipment_action": "assign",
                "shipment_snapshot_id": str(data["unassigned_shipment"].pk),
                "volunteer_snapshot": str(data["volunteer_bob"].pk),
                "flight_snapshot": str(data["flight_af910"].pk),
            },
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("planning:version_detail", args=[data["version"].pk]),
        )
        messages = [str(message) for message in response.context["messages"]]
        self.assertIn(
            "Le vol selectionne n'a pas assez de capacite restante pour cette expedition.",
            messages,
            messages,
        )
        self.assertFalse(
            PlanningAssignment.objects.filter(
                version=data["version"],
                shipment_snapshot=data["unassigned_shipment"],
            ).exists()
        )

    def test_version_detail_renders_operator_cockpit_blocks(self):
        version, assignment, _volunteer_bob, _flight_af456 = self.make_version_with_assignment(
            status=PlanningVersionStatus.PUBLISHED
        )
        PlanningShipmentSnapshot.objects.create(
            run=version.run,
            shipment_reference="SHP-UNASSIGNED",
            shipper_name="Association C",
            destination_iata="DSS",
            carton_count=2,
            equivalent_units=2,
        )
        version.run.solver_result = {
            "unassigned_reasons": {
                str(
                    version.run.shipment_snapshots.exclude(pk=assignment.shipment_snapshot_id)
                    .get()
                    .pk
                ): ("no_selected_candidate")
            }
        }
        version.run.save(update_fields=["solver_result", "updated_at"])
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:version_detail", args=[version.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Planning")
        self.assertContains(response, "Non affectes")
        self.assertContains(response, "Communications")
        self.assertContains(response, "Historique des versions")
        self.assertContains(response, "AF 123")
        self.assertContains(response, "SHP-UNASSIGNED")

    def test_version_detail_renders_operator_header_and_detailed_planning_row(self):
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            status=PlanningRunStatus.SOLVED,
            flight_mode="excel",
            created_by=self.staff_user,
        )
        version = PlanningVersion.objects.create(
            run=run,
            status=PlanningVersionStatus.DRAFT,
            created_by=self.staff_user,
        )
        shipment = PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="260128",
            shipper_name="ASF",
            destination_iata="NSI",
            carton_count=10,
            equivalent_units=10,
            payload={
                "legacy_type": "MM",
                "legacy_destinataire": "CORRESPONDANT",
            },
        )
        volunteer = PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="COURTOIS Alain",
        )
        flight = PlanningFlightSnapshot.objects.create(
            run=run,
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
            source=PlanningAssignmentSource.MANUAL,
            sequence=1,
        )
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:version_detail", args=[version.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Planning Semaine 11 (du 09/03/26 au 15/03/26)")
        self.assertContains(response, "Nb vols utilises")
        self.assertContains(response, "Nb colis disponibles")
        self.assertContains(response, "Mardi 10/03/2026")
        self.assertContains(response, "11h10")
        self.assertContains(response, "AF 908")
        self.assertContains(response, "CDG-NSI")
        self.assertContains(response, "COURTOIS Alain")
        self.assertContains(response, "CORRESPONDANT")

    def test_version_detail_uses_scan_table_styles_for_operator_tables(self):
        data = self.make_operator_version()
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:version_detail", args=[data["version"].pk]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertGreaterEqual(content.count("scan-table-wrap table-responsive"), 3)
        self.assertGreaterEqual(content.count("scan-table table table-sm table-hover"), 3)

    def test_version_detail_renders_week_view_and_planning_summary_cards(self):
        data = self.make_operator_version()
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:version_detail", args=[data["version"].pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vue Semaine")
        self.assertContains(response, "Disponibilites benevoles (vue semaine)")
        self.assertContains(response, "Vols disponibles (vue semaine)")
        self.assertContains(response, "Bilan Planning")
        self.assertContains(response, "Bilan Bénévoles")
        self.assertContains(response, "Bilan Expéditions")
        self.assertContains(response, "Alice (2)")
        self.assertContains(response, "NSI (6)")
        self.assertContains(response, "Nb_Dispo")
        self.assertContains(response, "Nb_Jours_Affectes")
        self.assertContains(response, "Nb_Vols_Affectes")
        self.assertContains(response, "Nb_BE_Affectes")
        self.assertContains(response, "Nb Colis Affecté")
        self.assertContains(response, "Nb Equiv Affecté")
        self.assertNotContains(response, "<th>Disponibilites</th>", status_code=200)

    def test_version_detail_renders_destination_bilan_table(self):
        data = self.make_operator_version()
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:version_detail", args=[data["version"].pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Destination")
        self.assertContains(response, "BE_Numero")
        self.assertContains(response, "Etat")
        self.assertContains(response, "BE_Nb_Colis")
        self.assertContains(response, "BE_Nb_Equiv")
        self.assertContains(response, "BE_Type")
        self.assertContains(response, "BE_Expediteur")
        self.assertContains(response, "BE_Destinataire")
        self.assertContains(response, "Tout développer")
        self.assertContains(response, "1 / 2")
        self.assertContains(response, "4 / 6")
        self.assertContains(response, "Planifié")
        self.assertContains(response, "Non partant")

    def test_version_detail_renders_destination_bilan_expand_controls(self):
        data = self.make_operator_version()
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:version_detail", args=[data["version"].pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-planning-destination-table="1"')
        self.assertContains(response, 'data-planning-destination-group="NSI"')
        self.assertContains(response, 'data-planning-destination-row="summary"')
        self.assertContains(response, 'data-planning-destination-row="shipment"')
        self.assertContains(response, 'data-planning-destination-toggle="group"')
        self.assertContains(response, 'data-planning-destination-toggle="all"')

    def test_version_detail_week_view_tables_share_fixed_column_widths(self):
        data = self.make_operator_version()
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:version_detail", args=[data["version"].pk]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertGreaterEqual(content.count('style="width: 16ch;"'), 2)
        self.assertGreaterEqual(content.count('style="width: 24ch;"'), 14)
        self.assertIn("d-flex flex-column align-items-start gap-1", content)
        self.assertGreaterEqual(content.count('data-planning-simple-table="1"'), 3)

    def test_generating_drafts_from_version_detail_regenerates_aggregated_series(self):
        version, _assignment, _volunteer_bob, flight_af456 = self.make_version_with_assignment(
            status=PlanningVersionStatus.PUBLISHED
        )
        second_shipment = PlanningShipmentSnapshot.objects.create(
            run=version.run,
            shipment_reference="SHP-002",
            carton_count=2,
            equivalent_units=2,
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=second_shipment,
            volunteer_snapshot=version.assignments.get().volunteer_snapshot,
            flight_snapshot=flight_af456,
            assigned_carton_count=2,
            source=PlanningAssignmentSource.MANUAL,
            sequence=2,
        )
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("planning:version_detail", args=[version.pk]),
            {"draft_action": "generate"},
        )

        self.assertRedirects(response, reverse("planning:version_detail", args=[version.pk]))
        self.assertEqual(version.communication_drafts.count(), 3)

    def test_generating_drafts_from_draft_version_shows_error(self):
        version, _assignment, _volunteer_bob, _flight_af456 = self.make_version_with_assignment(
            status=PlanningVersionStatus.DRAFT
        )
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("planning:version_detail", args=[version.pk]),
            {"draft_action": "generate"},
            follow=True,
        )

        self.assertRedirects(response, reverse("planning:version_detail", args=[version.pk]))
        self.assertContains(
            response, "Seules les versions publiees peuvent generer des brouillons."
        )
        self.assertEqual(version.communication_drafts.count(), 0)

    def test_version_detail_renders_communication_change_badges(self):
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            status=PlanningRunStatus.SOLVED,
            created_by=self.staff_user,
        )
        shipment_1 = PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="SHP-001",
            carton_count=3,
            equivalent_units=3,
        )
        shipment_2 = PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference="SHP-002",
            carton_count=2,
            equivalent_units=2,
        )
        volunteer_alice = PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="Alice",
        )
        volunteer_bob = PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label="Bob",
        )
        flight_af123 = PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF123",
            departure_date="2026-03-10",
            destination_iata="CDG",
        )
        flight_af456 = PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF456",
            departure_date="2026-03-11",
            destination_iata="NCE",
        )
        flight_af999 = PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number="AF999",
            departure_date="2026-03-12",
            destination_iata="CDG",
        )
        previous = PlanningVersion.objects.create(
            run=run,
            status=PlanningVersionStatus.PUBLISHED,
            created_by=self.staff_user,
        )
        current = PlanningVersion.objects.create(
            run=run,
            status=PlanningVersionStatus.PUBLISHED,
            based_on=previous,
            created_by=self.staff_user,
        )
        PlanningAssignment.objects.create(
            version=previous,
            shipment_snapshot=shipment_1,
            volunteer_snapshot=volunteer_alice,
            flight_snapshot=flight_af123,
            assigned_carton_count=3,
            source=PlanningAssignmentSource.SOLVER,
            sequence=1,
        )
        PlanningAssignment.objects.create(
            version=previous,
            shipment_snapshot=shipment_2,
            volunteer_snapshot=volunteer_bob,
            flight_snapshot=flight_af456,
            assigned_carton_count=2,
            source=PlanningAssignmentSource.SOLVER,
            sequence=2,
        )
        PlanningAssignment.objects.create(
            version=current,
            shipment_snapshot=shipment_1,
            volunteer_snapshot=volunteer_alice,
            flight_snapshot=flight_af999,
            assigned_carton_count=3,
            source=PlanningAssignmentSource.MANUAL,
            sequence=1,
        )
        PlanningAssignment.objects.create(
            version=current,
            shipment_snapshot=shipment_2,
            volunteer_snapshot=volunteer_bob,
            flight_snapshot=flight_af456,
            assigned_carton_count=2,
            source=PlanningAssignmentSource.SOLVER,
            sequence=2,
        )
        generate_version_drafts(current)
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:version_detail", args=[current.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Modifie")
        self.assertContains(response, "Inchange")
        self.assertContains(response, "WhatsApp bénévoles")

    @mock.patch("wms.views_planning._build_strict_packing_list_pdf_response")
    def test_version_detail_communication_helper_endpoints(self, packing_list_pdf_response_mock):
        data = self.make_published_version_with_communication_drafts()
        version = data["version"]
        shipment_snapshot = data["shipment_snapshot"]
        whatsapp_draft = version.communication_drafts.get(family="whatsapp_benevole")
        email_draft = version.communication_drafts.get(family="email_asf")
        expediteur_family = "email_expediteur"
        packing_list_pdf_response_mock.return_value = FileResponse(
            BytesIO(b"%PDF-1.4\n%"),
            content_type="application/pdf",
        )
        self.client.force_login(self.staff_user)

        whatsapp_response = self.client.get(
            reverse(
                "planning:version_communication_draft_action",
                args=[version.pk, whatsapp_draft.pk],
            )
        )
        self.assertEqual(whatsapp_response.status_code, 200)
        self.assertEqual(whatsapp_response.json()["action"], "whatsapp")
        self.assertNotIn("subject", whatsapp_response.json())

        email_response = self.client.get(
            reverse(
                "planning:version_communication_draft_action",
                args=[version.pk, email_draft.pk],
            )
        )
        self.assertEqual(email_response.status_code, 200)
        self.assertEqual(email_response.json()["action"], "email")
        self.assertEqual(
            email_response.json()["attachments"][0]["download_url"],
            reverse("planning:version_communication_workbook", args=[version.pk]),
        )
        self.assertFalse(email_response.json()["attachments"][0]["optional"])

        family_response = self.client.get(
            reverse(
                "planning:version_communication_family_action",
                args=[version.pk, expediteur_family],
            )
        )
        self.assertEqual(family_response.status_code, 200)
        self.assertEqual(family_response.json()["family"], expediteur_family)
        self.assertEqual(len(family_response.json()["drafts"]), 1)
        self.assertEqual(
            family_response.json()["drafts"][0]["attachments"][0]["download_url"],
            reverse(
                "planning:version_communication_packing_list_pdf",
                args=[version.pk, shipment_snapshot.pk],
            ),
        )
        self.assertTrue(family_response.json()["drafts"][0]["attachments"][0]["optional"])

        workbook_response = self.client.get(
            reverse("planning:version_communication_workbook", args=[version.pk])
        )
        try:
            self.assertEqual(workbook_response.status_code, 200)
            self.assertEqual(
                workbook_response["Content-Type"],
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        finally:
            workbook_response.close()

        packing_list_response = self.client.get(
            reverse(
                "planning:version_communication_packing_list_pdf",
                args=[version.pk, shipment_snapshot.pk],
            )
        )
        try:
            self.assertEqual(packing_list_response.status_code, 200)
            self.assertEqual(packing_list_response["Content-Type"], "application/pdf")
        finally:
            packing_list_response.close()

        packing_list_pdf_response_mock.reset_mock()
        packing_list_pdf_response_mock.side_effect = ValidationError(
            "PDF packing list indisponible."
        )

        failed_packing_list_response = self.client.get(
            reverse(
                "planning:version_communication_packing_list_pdf",
                args=[version.pk, shipment_snapshot.pk],
            )
        )
        self.assertEqual(failed_packing_list_response.status_code, 409)
        self.assertEqual(
            failed_packing_list_response.json()["error"],
            "PDF packing list indisponible.",
        )

    def test_version_detail_renders_communication_helper_buttons(self):
        data = self.make_published_version_with_communication_drafts()
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:version_detail", args=[data["version"].pk]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Generer tous les WhatsApp", content)
        self.assertGreaterEqual(content.count("Generer tous les mails"), 3)
        self.assertIn("Ouvrir WhatsApp", content)
        self.assertIn("Ouvrir le brouillon", content)
        self.assertIn('data-planning-communication-helper="1"', content)
        self.assertIn('src="/static/wms/planning_communications_helper.js"', content)
        whatsapp_block = re.search(
            r'<article[^>]+data-family-key="whatsapp_benevole".*?</article>',
            content,
            re.IGNORECASE | re.DOTALL,
        )
        self.assertIsNotNone(whatsapp_block)
        self.assertNotIn("<th>Sujet</th>", whatsapp_block.group(0))

    @mock.patch("wms.views_planning.platform.system", return_value="Darwin")
    def test_version_detail_exposes_helper_bridge_hooks(self, _platform_mock):
        data = self.make_published_version_with_communication_drafts()
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:version_detail", args=[data["version"].pk]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('data-planning-helper-origin="127.0.0.1:38555"', content)
        self.assertIn('data-draft-action-url="/planning/versions/', content)
        self.assertIn('data-family-action-url="/planning/versions/', content)
        self.assertIn('data-planning-helper-install-url="/planning/versions/', content)
        self.assertIn('data-planning-helper-install-command="', content)
        self.assertIn('data-planning-helper-install-available="1"', content)
        self.assertIn('data-planning-helper-minimum-version="0.1.2"', content)
        self.assertIn('data-planning-helper-latest-version="0.1.2"', content)
        self.assertIn('data-draft-id="', content)
        self.assertIn('data-family-key="whatsapp_benevole"', content)
        self.assertIn("Installer le helper", content)
        self.assertIn("Reessayer", content)

    @mock.patch("wms.views_planning.platform.system", return_value="Darwin")
    def test_version_detail_helper_installer_downloads_macos_script(self, _platform_mock):
        data = self.make_published_version_with_communication_drafts()
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("planning:version_communication_helper_installer", args=[data["version"].pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="install-asf-planning-helper.command"',
        )
        content = response.content.decode()
        self.assertIn("#!/bin/zsh", content)
        self.assertIn("tools.planning_comm_helper.autostart install", content)

    @mock.patch("wms.views_planning.platform.system", return_value="Windows")
    def test_version_detail_helper_installer_downloads_windows_script(self, _platform_mock):
        data = self.make_published_version_with_communication_drafts()
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("planning:version_communication_helper_installer", args=[data["version"].pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="install-asf-planning-helper.cmd"',
        )
        content = response.content.decode()
        self.assertIn("@echo off", content)
        self.assertIn("tools.planning_comm_helper.autostart install", content)

    @mock.patch("wms.views_planning.platform.system", return_value="Linux")
    def test_version_detail_helper_installer_rejects_unsupported_platform(self, _platform_mock):
        data = self.make_published_version_with_communication_drafts()
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("planning:version_communication_helper_installer", args=[data["version"].pk])
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"],
            "Installation du helper indisponible sur ce poste.",
        )

    @mock.patch("wms.views_planning.platform.system", return_value="Linux")
    def test_version_detail_helper_installer_detects_macos_client_request(self, _platform_mock):
        data = self.make_published_version_with_communication_drafts()
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("planning:version_communication_helper_installer", args=[data["version"].pk]),
            HTTP_USER_AGENT=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="install-asf-planning-helper.command"',
        )
        self.assertIn("#!/bin/zsh", response.content.decode())

    @mock.patch("wms.views_planning.platform.system", return_value="Linux")
    @mock.patch("wms.helper_install._helper_bundle_base64", return_value="QUJD")
    def test_version_detail_helper_installer_allows_signed_anonymous_request(
        self,
        _bundle_mock,
        _platform_mock,
    ):
        data = self.make_published_version_with_communication_drafts()
        request = self.factory.get(
            reverse("planning:version_detail", args=[data["version"].pk]),
            HTTP_USER_AGENT=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
            ),
        )
        context = build_helper_install_context(
            install_url=reverse(
                "planning:version_communication_helper_installer",
                args=[data["version"].pk],
            ),
            app_label="asf-planning",
            system="Linux",
            request=request,
        )

        self.client.logout()
        response = self.client.get(context["install_url"])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="install-asf-planning-helper.command"',
        )
        self.assertEqual(response["X-ASF-Planning-Version"], str(data["version"].pk))
        self.assertIn("#!/bin/zsh", response.content.decode())

    def test_version_detail_renders_visual_html_editor_for_email_drafts_only(self):
        data = self.make_published_version_with_communication_drafts()
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:version_detail", args=[data["version"].pk]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('src="/static/wms/planning_communications_editor.js"', content)
        email_block = re.search(
            r'<article[^>]+data-family-key="email_expediteur".*?</article>',
            content,
            re.IGNORECASE | re.DOTALL,
        )
        self.assertIsNotNone(email_block)
        self.assertIn('data-planning-email-editor="1"', email_block.group(0))
        self.assertIn('data-planning-email-editor-surface="1"', email_block.group(0))
        self.assertIn('contenteditable="true"', email_block.group(0))
        self.assertIn("Gras", email_block.group(0))
        self.assertIn("Jaune", email_block.group(0))
        whatsapp_block = re.search(
            r'<article[^>]+data-family-key="whatsapp_benevole".*?</article>',
            content,
            re.IGNORECASE | re.DOTALL,
        )
        self.assertIsNotNone(whatsapp_block)
        self.assertNotIn('data-planning-email-editor="1"', whatsapp_block.group(0))

    def test_version_detail_renders_destinataire_card_without_email_button_when_contact_missing(
        self,
    ):
        data = self.make_published_version_with_communication_drafts(recipient_email="")
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:version_detail", args=[data["version"].pk]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        destinataire_block = re.search(
            r'<article[^>]+data-family-key="email_destinataire".*?</article>',
            content,
            re.IGNORECASE | re.DOTALL,
        )
        self.assertIsNotNone(destinataire_block)
        self.assertIn("Mail Destinataires", destinataire_block.group(0))
        self.assertIn("Pas de mail disponible", destinataire_block.group(0))
        self.assertNotIn("Ouvrir le brouillon", destinataire_block.group(0))

    def test_staff_can_clone_published_version(self):
        version, _assignment, _volunteer_bob, _flight_af456 = self.make_version_with_assignment(
            status=PlanningVersionStatus.PUBLISHED
        )
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("planning:version_clone", args=[version.pk]),
            {"change_reason": "Maj vendredi"},
        )

        clone = PlanningVersion.objects.exclude(pk=version.pk).get()
        self.assertRedirects(response, reverse("planning:version_detail", args=[clone.pk]))
        self.assertEqual(clone.based_on, version)
        self.assertEqual(clone.status, PlanningVersionStatus.DRAFT)
        self.assertEqual(clone.change_reason, "Maj vendredi")

    def test_staff_can_publish_draft_version(self):
        published, _assignment, _volunteer_bob, _flight_af456 = self.make_version_with_assignment(
            status=PlanningVersionStatus.PUBLISHED
        )
        draft = PlanningVersion.objects.create(
            run=published.run,
            status=PlanningVersionStatus.DRAFT,
            based_on=published,
            created_by=self.staff_user,
        )
        self.client.force_login(self.staff_user)

        response = self.client.post(reverse("planning:version_publish", args=[draft.pk]))

        published.refresh_from_db()
        draft.refresh_from_db()
        self.assertRedirects(response, reverse("planning:version_detail", args=[draft.pk]))
        self.assertEqual(published.status, PlanningVersionStatus.SUPERSEDED)
        self.assertEqual(draft.status, PlanningVersionStatus.PUBLISHED)

    def test_version_diff_view_shows_changed_assignment(self):
        original, _assignment, volunteer_bob, flight_af456 = self.make_version_with_assignment(
            status=PlanningVersionStatus.PUBLISHED
        )
        updated = PlanningVersion.objects.create(
            run=original.run,
            status=PlanningVersionStatus.DRAFT,
            based_on=original,
            created_by=self.staff_user,
            change_reason="Maj vendredi",
        )
        PlanningAssignment.objects.create(
            version=updated,
            shipment_snapshot=original.assignments.get().shipment_snapshot,
            volunteer_snapshot=volunteer_bob,
            flight_snapshot=flight_af456,
            assigned_carton_count=5,
            notes="Manual swap",
            source=PlanningAssignmentSource.MANUAL,
            sequence=1,
        )
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("planning:version_diff", args=[updated.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SHP-001")
        self.assertContains(response, "Alice")
        self.assertContains(response, "Bob")

    def test_staff_can_apply_published_version_updates_to_shipments(self):
        version, shipment = self.make_published_version_with_live_shipment()
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("planning:version_detail", args=[version.pk]),
            {"shipment_action": "apply_updates"},
        )

        shipment.refresh_from_db()
        self.assertRedirects(response, reverse("planning:version_detail", args=[version.pk]))
        self.assertEqual(shipment.status, ShipmentStatus.PLANNED)
        self.assertTrue(
            ShipmentTrackingEvent.objects.filter(
                shipment=shipment,
                status=ShipmentTrackingStatus.PLANNED,
            ).exists()
        )
