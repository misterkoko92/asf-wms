from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.artifacts.planning import build_planning_artifacts
from wms.models import (
    PlanningCommunicationArtifact,
    PlanningRun,
    PlanningVersion,
    PlanningVersionStatus,
)


class PlanningArtifactServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="planning-artifacts@example.com",
            email="planning-artifacts@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            created_by=self.user,
        )
        self.version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.PUBLISHED,
            created_by=self.user,
        )

    def test_build_planning_artifacts_returns_workbook_and_pdf_metadata(self):
        PlanningCommunicationArtifact.objects.create(
            planning_version=self.version,
            output_type="planning_workbook",
            status="ready",
            backend="openpyxl",
            file_name="planning-v1.xlsx",
        )
        PlanningCommunicationArtifact.objects.create(
            planning_version=self.version,
            output_type="planning_pdf",
            status="failed",
            backend="excel_desktop",
            file_name="planning-v1.pdf",
            error_message="Excel indisponible",
        )

        result = build_planning_artifacts(self.version)

        self.assertEqual(result["workbook"]["output_type"], "planning_workbook")
        self.assertEqual(result["workbook"]["status"], "ready")
        self.assertEqual(result["workbook"]["backend"], "openpyxl")
        self.assertEqual(result["pdf"]["output_type"], "planning_pdf")
        self.assertEqual(result["pdf"]["status"], "failed")
        self.assertEqual(result["pdf"]["backend"], "excel_desktop")
        self.assertEqual(result["pdf"]["error_message"], "Excel indisponible")
