from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from openpyxl import load_workbook

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
from wms.planning.legacy_communications import CommunicationFamily
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
            scope=CommunicationFamily.EMAIL_ASF,
            subject="Planning v{{ version_number }} pour ASF interne",
            body="Bonjour ASF, semaine {{ week }}.",
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

        self.assertEqual(len(drafts), 3)
        draft = CommunicationDraft.objects.get(
            version=version,
            family=CommunicationFamily.EMAIL_ASF,
        )
        self.assertEqual(draft.subject, "Planning v1 pour ASF interne v1")
        self.assertEqual(draft.body, "Bonjour ASF, semaine 11.")

        self.assertIsInstance(artifact, PlanningArtifact)
        self.assertEqual(artifact.artifact_type, "planning_workbook")
        self.assertTrue(artifact.file_path.endswith(".xlsx"))
        self.assertTrue(Path(artifact.file_path).exists())
        workbook = load_workbook(artifact.file_path)
        sheet = workbook["Planning"]
        self.assertEqual(
            [cell.value for cell in sheet[1]],
            [
                "Date",
                "Flight",
                "Destination",
                "DepartureTime",
                "Volunteer",
                "Shipment",
                "Shipper",
                "Cartons",
                "Status",
                "Source",
                "Notes",
            ],
        )
        self.assertEqual(
            [cell.value for cell in sheet[2]],
            [
                "2026-03-10",
                "AF123",
                "CDG",
                None,
                "Alice",
                "SHP-001",
                None,
                4,
                "proposed",
                "manual",
                None,
            ],
        )

        self.assertEqual(stats["assignment_count"], 1)
        self.assertEqual(stats["carton_total"], 4)
        self.assertEqual(stats["volunteer_count"], 1)
        self.assertEqual(stats["flight_count"], 1)
        self.assertEqual(stats["manual_adjustment_count"], 1)
        self.assertEqual(stats["unassigned_count"], 0)
        self.assertEqual(
            stats["destination_breakdown"],
            [
                {
                    "destination_iata": "CDG",
                    "assignment_count": 1,
                    "carton_total": 4,
                    "equivalent_total": 4,
                }
            ],
        )
        self.assertEqual(
            stats["volunteer_breakdown"],
            [
                {
                    "volunteer_label": "Alice",
                    "assignment_count": 1,
                    "carton_total": 4,
                    "equivalent_total": 4,
                }
            ],
        )
        self.assertEqual(
            stats["flight_load_breakdown"],
            [
                {
                    "flight_snapshot_id": self.flight_snapshot.pk,
                    "flight_number": "AF123",
                    "departure_date": date(2026, 3, 10),
                    "departure_time": "",
                    "destination_iata": "CDG",
                    "capacity_units": None,
                    "assignment_count": 1,
                    "carton_total": 4,
                    "equivalent_total": 4,
                }
            ],
        )

    def test_generate_drafts_aggregates_multiple_assignments_for_same_recipient(self):
        second_shipment = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="SHP-002",
            carton_count=2,
            equivalent_units=2,
        )
        second_flight = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF456",
            departure_date="2026-03-11",
            destination_iata="NCE",
        )
        version = self.make_published_version()
        PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=second_shipment,
            volunteer_snapshot=self.volunteer_snapshot,
            flight_snapshot=second_flight,
            assigned_carton_count=2,
            source=PlanningAssignmentSource.MANUAL,
            sequence=2,
        )

        drafts = generate_version_drafts(version)

        self.assertEqual(len(drafts), 3)
        whatsapp_draft = next(
            draft for draft in drafts if draft.family == CommunicationFamily.WHATSAPP_BENEVOLE
        )
        self.assertEqual(whatsapp_draft.recipient_label, "Alice")
        self.assertIn("AF 123", whatsapp_draft.body)
        self.assertIn("AF 456", whatsapp_draft.body)
        self.assertIn("BE 000001", whatsapp_draft.body)
        self.assertIn("BE 000002", whatsapp_draft.body)

    def test_generate_drafts_creates_cancellation_message_for_removed_recipient(self):
        self.template.is_active = False
        self.template.save(update_fields=["is_active", "updated_at"])
        version_1 = self.make_published_version()
        version_2 = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.PUBLISHED,
            based_on=version_1,
            created_by=self.user,
        )

        drafts_v2 = generate_version_drafts(version_2)

        self.assertEqual(len(drafts_v2), 3)
        whatsapp_draft = next(
            draft for draft in drafts_v2 if draft.family == CommunicationFamily.WHATSAPP_BENEVOLE
        )
        self.assertEqual(whatsapp_draft.recipient_label, "Alice")
        self.assertIn("AF 123", whatsapp_draft.body)

    def test_generate_drafts_keeps_multiple_active_templates_on_same_channel(self):
        second_template = CommunicationTemplate.objects.create(
            label="Mail air france",
            channel=CommunicationChannel.EMAIL,
            scope=CommunicationFamily.EMAIL_AIRFRANCE,
            subject="Second {{ recipient_label }}",
            body="Second template pour {{ recipient_label }}",
        )
        version = self.make_published_version()

        drafts = generate_version_drafts(version)

        self.assertEqual(len(drafts), 3)
        self.assertEqual(
            sorted(draft.template_id for draft in drafts if draft.template_id),
            sorted([self.template.pk, second_template.pk]),
        )
        self.assertEqual(
            sorted(
                CommunicationDraft.objects.filter(
                    version=version, template__isnull=False
                ).values_list(
                    "template__label",
                    flat=True,
                )
            ),
            ["Mail air france", "Mail planning"],
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

        self.assertEqual(len(drafts_v1), 3)
        self.assertEqual(len(drafts_v2), 4)
        self.assertEqual(
            sorted(
                CommunicationDraft.objects.filter(version=version_2).values_list(
                    "family",
                    "recipient_label",
                )
            ),
            sorted(
                [
                    (CommunicationFamily.EMAIL_AIRFRANCE, "Air France"),
                    (CommunicationFamily.EMAIL_ASF, "ASF interne"),
                    (CommunicationFamily.WHATSAPP_BENEVOLE, "Alice"),
                    (CommunicationFamily.WHATSAPP_BENEVOLE, "Bob"),
                ]
            ),
        )
