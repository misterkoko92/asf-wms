from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from contacts.models import Contact
from wms.models import (
    Destination,
    PlanningRun,
    PlanningVersion,
    PlanningVersionStatus,
    Shipment,
    ShipmentStatus,
    ShipmentWorkflowProjection,
)
from wms.ops_escalations import evaluate_ops_escalations


class OpsEscalationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ops-escalation-user",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )
        self.correspondent = Contact.objects.create(
            name="Ops Escalation Contact",
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="BAMAKO",
            iata_code="BKO",
            country="MALI",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.shipment = Shipment.objects.create(
            reference="EXP-ESC-001",
            status=ShipmentStatus.PLANNED,
            shipper_name="Shipper",
            recipient_name="Recipient",
            correspondent_name="Correspondent",
            destination=self.destination,
            destination_address=str(self.destination),
            destination_country=self.destination.country,
            created_by=self.user,
            is_disputed=True,
            dispute_owner="",
            dispute_reason="docs_missing",
            dispute_opened_at=timezone.now() - timedelta(hours=48),
        )
        ShipmentWorkflowProjection.objects.create(
            shipment=self.shipment,
            destination=self.destination,
            reference=self.shipment.reference,
            destination_label=str(self.destination),
            shipment_status=self.shipment.status,
            current_segment="planned_to_boarding",
            segment_age_hours=144.0,
            is_closed=False,
            has_open_dispute=True,
            dispute_reason="docs_missing",
            dispute_owner="",
            dispute_opened_at=timezone.now() - timedelta(hours=48),
            delay_state="persistent",
            current_delay_hours=72.0,
            active_blockage_category="suivi",
        )
        self.run = PlanningRun.objects.create(
            week_start="2026-03-30",
            week_end="2026-04-05",
            created_by=self.user,
        )
        self.version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.PUBLISHED,
            created_by=self.user,
        )

    def test_evaluate_ops_escalations_opens_unassigned_dispute_and_sla_persistent_alerts(self):
        escalations = evaluate_ops_escalations(now=timezone.now())

        categories = {item["category"] for item in escalations}

        self.assertIn("dispute_unassigned", categories)
        self.assertIn("sla_persistent", categories)

    def test_evaluate_ops_escalations_detects_planning_pdf_missing(self):
        escalations = evaluate_ops_escalations(now=timezone.now())

        self.assertTrue(any(item["category"] == "planning_pdf_missing" for item in escalations))
