from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contacts.models import Contact
from wms.models import (
    Destination,
    OpsEscalation,
    OpsPilotageSnapshot,
    Order,
    OrderReviewStatus,
    Shipment,
    ShipmentStatus,
    ShipmentWorkflowProjection,
)


class ScanPilotageViewTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-pilotage-staff",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )
        self.basic_user = get_user_model().objects.create_user(
            username="scan-pilotage-basic",
            password="pass1234",  # pragma: allowlist secret
        )
        self.client.force_login(self.staff_user)

        correspondent = Contact.objects.create(name="Pilotage Correspondent", is_active=True)
        destination = Destination.objects.create(
            city="DAKAR",
            iata_code="DKR",
            country="SENEGAL",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipment = Shipment.objects.create(
            reference="EXP-PILOTAGE-001",
            status=ShipmentStatus.PLANNED,
            shipper_name="Shipper",
            recipient_name="Recipient",
            correspondent_name="Correspondent",
            destination=destination,
            destination_address=str(destination),
            destination_country=destination.country,
            created_by=self.staff_user,
        )
        ShipmentWorkflowProjection.objects.create(
            shipment=shipment,
            destination=destination,
            reference=shipment.reference,
            tracking_token=shipment.tracking_token,
            destination_label=str(destination),
            shipment_status=shipment.status,
            current_segment="planned_to_boarding",
            segment_age_hours=168.0,
            is_closed=False,
            has_open_dispute=True,
            dispute_reason="docs_missing",
            dispute_owner="qualite",
            delay_state="critical",
            current_delay_hours=96.0,
            active_blockage_category="suivi",
            projected_at=timezone.now(),
        )
        Order.objects.create(
            reference="CMD-PILOTAGE-001",
            review_status=OrderReviewStatus.PENDING,
            shipper_name="Shipper",
            recipient_name="Recipient",
            destination_address="42 Rue Portail",
            created_by=self.staff_user,
        )
        Order.objects.update(created_at=timezone.now() - timedelta(hours=36))

        snapshot_date = timezone.localdate()
        OpsPilotageSnapshot.objects.create(
            snapshot_date=snapshot_date,
            scope_type="global",
            scope_key="all",
            metric_key="sla_critical_count",
            metric_value=2,
            payload={},
        )
        OpsPilotageSnapshot.objects.create(
            snapshot_date=snapshot_date,
            scope_type="planning_export",
            scope_key="12",
            metric_key="planning_pdf_ok",
            metric_value=0,
            payload={"version_id": 12, "run_id": 4},
        )
        OpsPilotageSnapshot.objects.create(
            snapshot_date=snapshot_date,
            scope_type="planning_export",
            scope_key="12",
            metric_key="planning_workbook_ok",
            metric_value=1,
            payload={"version_id": 12, "run_id": 4},
        )
        OpsEscalation.objects.create(
            escalation_key="planning_pdf_missing:version:12",
            category="planning_pdf_missing",
            scope_type="planning_version",
            scope_key="12",
            severity="high",
            owner="admin",
            status="open",
            payload={"version_id": 12, "run_id": 4},
        )

    def test_scan_pilotage_renders_transverse_sections(self):
        response = self.client.get(reverse("scan:scan_pilotage"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Priorites du jour")
        self.assertContains(response, "Escalades persistantes")
        self.assertContains(response, "Exports planning")
        self.assertContains(response, "Backlog portail")

    def test_scan_pilotage_links_back_to_scan_portal_and_planning_surfaces(self):
        response = self.client.get(reverse("scan:scan_pilotage"))

        self.assertContains(response, reverse("scan:scan_dashboard"))
        self.assertContains(response, reverse("portal:portal_dashboard"))
        self.assertContains(response, reverse("planning:run_list"))

    def test_scan_pilotage_requires_staff(self):
        self.client.force_login(self.basic_user)

        response = self.client.get(reverse("scan:scan_pilotage"))

        self.assertEqual(response.status_code, 403)
