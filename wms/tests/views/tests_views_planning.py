from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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
)


class PlanningViewTests(TestCase):
    def setUp(self):
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

    def test_run_detail_shows_issues_and_solve_button(self):
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            status=PlanningRunStatus.READY,
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
        self.assertContains(response, "Lancer le solveur")

    @mock.patch("wms.views_planning.solve_run")
    def test_run_solve_post_redirects_to_created_version(self, solve_run_mock):
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            status=PlanningRunStatus.READY,
            created_by=self.staff_user,
        )
        version = PlanningVersion.objects.create(run=run, created_by=self.staff_user)
        solve_run_mock.return_value = version
        self.client.force_login(self.staff_user)

        response = self.client.post(reverse("planning:run_solve", args=[run.pk]))

        solve_run_mock.assert_called_once_with(run)
        self.assertRedirects(response, reverse("planning:version_detail", args=[version.pk]))

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
