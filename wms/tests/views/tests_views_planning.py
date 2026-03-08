from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from wms.models import (
    PlanningIssue,
    PlanningParameterSet,
    PlanningRun,
    PlanningRunStatus,
    PlanningVersion,
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
