from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import (
    CommunicationChannel,
    CommunicationDraft,
    CommunicationTemplate,
    PlanningArtifact,
    PlanningAssignment,
    PlanningAssignmentSource,
    PlanningFlightSnapshot,
    PlanningRun,
    PlanningShipmentSnapshot,
    PlanningVersion,
    PlanningVersionStatus,
    PlanningVolunteerSnapshot,
)
from wms.planning.communications import generate_version_drafts
from wms.planning.exports import export_version_workbook
from wms.planning.stats import build_version_stats


class PlanningOutputTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="planner@example.com",
            email="planner@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            created_by=self.user,
        )
        self.shipment_snapshot = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="SHP-001",
            carton_count=4,
            equivalent_units=4,
        )
        self.volunteer_snapshot = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Alice",
        )
        self.flight_snapshot = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF123",
            departure_date="2026-03-10",
            destination_iata="CDG",
        )
        self.template = CommunicationTemplate.objects.create(
            label="Mail planning",
            channel=CommunicationChannel.EMAIL,
            subject="Planning v{{ version_number }} pour {{ volunteer }}",
            body=(
                "Bonjour {{ volunteer }}, "
                "vol {{ flight }} pour {{ shipment_reference }} "
                "({{ cartons }} colis)."
            ),
        )

    def make_published_version(
        self,
        *,
        based_on=None,
        volunteer_label="Alice",
        flight_number="AF123",
        cartons=4,
    ):
        volunteer_snapshot = self.volunteer_snapshot
        if volunteer_label != self.volunteer_snapshot.volunteer_label:
            volunteer_snapshot = PlanningVolunteerSnapshot.objects.create(
                run=self.run,
                volunteer_label=volunteer_label,
            )

        flight_snapshot = self.flight_snapshot
        if flight_number != self.flight_snapshot.flight_number:
            flight_snapshot = PlanningFlightSnapshot.objects.create(
                run=self.run,
                flight_number=flight_number,
                departure_date="2026-03-11",
                destination_iata="NCE",
            )

        version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.PUBLISHED,
            based_on=based_on,
            created_by=self.user,
        )
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=self.shipment_snapshot,
            volunteer_snapshot=volunteer_snapshot,
            flight_snapshot=flight_snapshot,
            assigned_carton_count=cartons,
            source=PlanningAssignmentSource.MANUAL,
            sequence=1,
        )
        return version

    def test_generate_drafts_and_excel_artifact_for_version(self):
        version = self.make_published_version()

        drafts = generate_version_drafts(version)
        artifact = export_version_workbook(version)
        stats = build_version_stats(version)

        self.assertEqual(len(drafts), 1)
        draft = CommunicationDraft.objects.get(version=version)
        self.assertIn("Planning v1 pour Alice", draft.subject)
        self.assertIn("AF123", draft.body)
        self.assertIn("SHP-001", draft.body)

        self.assertIsInstance(artifact, PlanningArtifact)
        self.assertEqual(artifact.artifact_type, "planning_workbook")
        self.assertTrue(artifact.file_path.endswith(".xlsx"))
        self.assertTrue(Path(artifact.file_path).exists())

        self.assertEqual(
            stats,
            {
                "assignment_count": 1,
                "carton_total": 4,
                "volunteer_count": 1,
                "flight_count": 1,
                "manual_adjustment_count": 1,
            },
        )

    def test_generate_drafts_keeps_separate_series_per_version(self):
        version_1 = self.make_published_version()
        version_2 = self.make_published_version(
            based_on=version_1,
            volunteer_label="Bob",
            flight_number="AF456",
            cartons=5,
        )

        drafts_v1 = generate_version_drafts(version_1)
        drafts_v2 = generate_version_drafts(version_2)

        self.assertEqual(len(drafts_v1), 1)
        self.assertEqual(len(drafts_v2), 1)
        self.assertEqual(
            list(
                CommunicationDraft.objects.filter(version=version_1).values_list(
                    "recipient_label",
                    flat=True,
                )
            ),
            ["Alice"],
        )
        self.assertEqual(
            list(
                CommunicationDraft.objects.filter(version=version_2).values_list(
                    "recipient_label",
                    flat=True,
                )
            ),
            ["Bob"],
        )
