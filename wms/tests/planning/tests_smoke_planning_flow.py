import os
import tempfile

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from wms.models import PlanningArtifact, PlanningRun, PlanningRunStatus, PlanningVersionStatus
from wms.planning.communications import generate_version_drafts
from wms.planning.exports import export_version_workbook
from wms.planning.versioning import publish_version


class PlanningSmokeFlowTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="planning-smoke-staff",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )

    def test_planning_smoke_flow_seed_to_cockpit(self):
        scenario = "smoke-e2e"
        with tempfile.TemporaryDirectory() as tmp_dir:
            previous_tmp_dir = os.environ.get("ASF_TMP_DIR")
            os.environ["ASF_TMP_DIR"] = tmp_dir
            try:
                call_command("seed_planning_demo_data", scenario=scenario, solve=True)

                run = PlanningRun.objects.select_related("parameter_set").get(
                    parameter_set__name="DEMO smoke-e2e"
                )
                version = run.versions.get(number=1)

                self.assertEqual(run.status, PlanningRunStatus.SOLVED)
                self.assertTrue(version.assignments.exists())

                publish_version(version)
                version.refresh_from_db()
                self.assertEqual(version.status, PlanningVersionStatus.PUBLISHED)

                drafts = generate_version_drafts(version)
                artifact = export_version_workbook(version)

                self.assertTrue(drafts)
                self.assertTrue(version.communication_drafts.exists())
                self.assertIsInstance(artifact, PlanningArtifact)
                self.assertEqual(artifact.version_id, version.id)
                self.assertTrue(version.artifacts.filter(pk=artifact.pk).exists())

                self.client.force_login(self.staff_user)
                response = self.client.get(reverse("planning:version_detail", args=[version.pk]))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f"v{version.number}")
                self.assertContains(response, "Communications")
            finally:
                if previous_tmp_dir is None:
                    os.environ.pop("ASF_TMP_DIR", None)
                else:
                    os.environ["ASF_TMP_DIR"] = previous_tmp_dir
