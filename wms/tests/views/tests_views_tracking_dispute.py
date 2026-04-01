from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from wms.models import (
    Carton,
    CartonStatus,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
)


class ShipmentTrackingDisputeFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tracking-dispute-user",
            password="pass1234",
            is_staff=True,
        )
        self.client.force_login(self.user)

    def _create_shipment(self, *, status=ShipmentStatus.PACKED, is_disputed=False):
        return Shipment.objects.create(
            status=status,
            is_disputed=is_disputed,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.user,
        )

    def test_boarding_step_marks_shipment_and_cartons_shipped(self):
        shipment = self._create_shipment(status=ShipmentStatus.PLANNED)
        carton_a = Carton.objects.create(
            code="CT-DSP-001",
            status=CartonStatus.LABELED,
            shipment=shipment,
        )
        carton_b = Carton.objects.create(
            code="CT-DSP-002",
            status=CartonStatus.LABELED,
            shipment=shipment,
        )

        response = self.client.post(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
            {
                "status": ShipmentTrackingStatus.BOARDING_OK,
                "actor_name": "Agent",
                "actor_structure": "ASF",
                "comments": "embarque",
            },
        )

        self.assertEqual(response.status_code, 302)
        shipment.refresh_from_db()
        carton_a.refresh_from_db()
        carton_b.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.SHIPPED)
        self.assertEqual(carton_a.status, CartonStatus.SHIPPED)
        self.assertEqual(carton_b.status, CartonStatus.SHIPPED)
        self.assertEqual(ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 1)

    def test_planning_step_rejects_unlabeled_cartons(self):
        shipment = self._create_shipment(status=ShipmentStatus.PACKED)
        Carton.objects.create(
            code="CT-DSP-004",
            status=CartonStatus.ASSIGNED,
            shipment=shipment,
        )

        response = self.client.post(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
            {
                "status": ShipmentTrackingStatus.PLANNING_OK,
                "actor_name": "Agent",
                "actor_structure": "ASF",
                "comments": "planning",
            },
        )

        self.assertEqual(response.status_code, 200)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PACKED)
        self.assertEqual(ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 0)

    def test_planned_step_requires_previous_planning_ok_step(self):
        shipment = self._create_shipment(status=ShipmentStatus.PACKED)
        Carton.objects.create(
            code="CT-DSP-005",
            status=CartonStatus.LABELED,
            shipment=shipment,
        )

        response = self.client.post(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
            {
                "status": ShipmentTrackingStatus.PLANNED,
                "actor_name": "Agent",
                "actor_structure": "ASF",
                "comments": "planned",
            },
        )

        self.assertEqual(response.status_code, 200)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PACKED)
        self.assertEqual(ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 0)

    def test_planning_then_planned_updates_shipment_sequence(self):
        shipment = self._create_shipment(status=ShipmentStatus.PACKED)
        Carton.objects.create(
            code="CT-DSP-006",
            status=CartonStatus.LABELED,
            shipment=shipment,
        )
        url = reverse("scan:scan_shipment_track", args=[shipment.tracking_token])

        first = self.client.post(
            url,
            {
                "status": ShipmentTrackingStatus.PLANNING_OK,
                "actor_name": "Agent",
                "actor_structure": "ASF",
                "comments": "planning ok",
            },
        )
        self.assertEqual(first.status_code, 302)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PACKED)
        self.assertEqual(ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 1)

        second = self.client.post(
            url,
            {
                "status": ShipmentTrackingStatus.PLANNED,
                "actor_name": "Agent",
                "actor_structure": "ASF",
                "comments": "planned",
            },
        )
        self.assertEqual(second.status_code, 302)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PLANNED)
        self.assertEqual(ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 2)
        self.assertEqual(shipment.dossier_last_activity_label, "Suivi mis à jour")
        self.assertIsNotNone(shipment.dossier_last_activity_at)

    def test_set_disputed_blocks_tracking_progression(self):
        shipment = self._create_shipment(status=ShipmentStatus.PLANNED)
        url = reverse("scan:scan_shipment_track", args=[shipment.tracking_token])

        with mock.patch("wms.shipment_tracking_handlers.log_shipment_dispute_action") as log_mock:
            response_dispute = self.client.post(
                url,
                {
                    "action": "set_disputed",
                    "dispute_reason": "docs_missing",
                    "dispute_status": "open",
                },
            )
        self.assertEqual(response_dispute.status_code, 302)
        shipment.refresh_from_db()
        self.assertTrue(shipment.is_disputed)
        self.assertIsNotNone(shipment.disputed_at)
        self.assertEqual(shipment.dossier_last_activity_label, "Expédition mise en litige")
        self.assertIsNotNone(shipment.dossier_last_activity_at)
        log_mock.assert_called_once_with(
            shipment=shipment,
            action="set_disputed",
            user=self.user,
            previous_status=ShipmentStatus.PLANNED,
            new_status=ShipmentStatus.PLANNED,
        )

        response_progress = self.client.post(
            url,
            {
                "status": ShipmentTrackingStatus.BOARDING_OK,
                "actor_name": "Agent",
                "actor_structure": "ASF",
                "comments": "ignore",
            },
        )
        self.assertEqual(response_progress.status_code, 302)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PLANNED)
        self.assertEqual(ShipmentTrackingEvent.objects.filter(shipment=shipment).count(), 0)

    def test_set_disputed_stores_structured_reason_owner_status_due_at(self):
        shipment = self._create_shipment(status=ShipmentStatus.PLANNED)
        due_at = timezone.now() + timedelta(days=2)

        response = self.client.post(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
            {
                "action": "set_disputed",
                "dispute_reason": "docs_missing",
                "dispute_owner": "qualite",
                "dispute_status": "open",
                "dispute_due_at": due_at.strftime("%Y-%m-%dT%H:%M"),
            },
        )

        self.assertEqual(response.status_code, 302)
        shipment.refresh_from_db()
        self.assertTrue(shipment.is_disputed)
        self.assertEqual(getattr(shipment, "dispute_reason", ""), "docs_missing")
        self.assertEqual(getattr(shipment, "dispute_owner", ""), "qualite")
        self.assertEqual(getattr(shipment, "dispute_status", ""), "open")
        self.assertIsNotNone(getattr(shipment, "dispute_due_at", None))
        self.assertIsNotNone(getattr(shipment, "dispute_opened_at", None))
        self.assertEqual(getattr(shipment, "dispute_resolution_notes", ""), "")

    def test_set_disputed_defaults_structured_status_to_open(self):
        shipment = self._create_shipment(status=ShipmentStatus.PLANNED)

        response = self.client.post(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
            {
                "action": "set_disputed",
                "dispute_reason": "docs_missing",
            },
        )

        self.assertEqual(response.status_code, 302)
        shipment.refresh_from_db()
        self.assertTrue(shipment.is_disputed)
        self.assertEqual(getattr(shipment, "dispute_status", ""), "open")

    def test_anonymous_user_cannot_set_disputed(self):
        shipment = self._create_shipment(status=ShipmentStatus.PLANNED)
        self.client.logout()

        response = self.client.post(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
            {"action": "set_disputed"},
        )

        self.assertEqual(response.status_code, 302)
        shipment.refresh_from_db()
        self.assertFalse(shipment.is_disputed)
        self.assertIsNone(shipment.disputed_at)

    def test_anonymous_user_cannot_resolve_disputed_shipment(self):
        shipment = self._create_shipment(
            status=ShipmentStatus.SHIPPED,
            is_disputed=True,
        )
        carton = Carton.objects.create(
            code="CT-DSP-ANON",
            status=CartonStatus.SHIPPED,
            shipment=shipment,
        )
        self.client.logout()

        response = self.client.post(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
            {"action": "resolve_dispute"},
        )

        self.assertEqual(response.status_code, 302)
        shipment.refresh_from_db()
        carton.refresh_from_db()
        self.assertTrue(shipment.is_disputed)
        self.assertEqual(shipment.status, ShipmentStatus.SHIPPED)
        self.assertEqual(carton.status, CartonStatus.SHIPPED)

    def test_resolve_dispute_requires_resolution_notes(self):
        shipment = self._create_shipment(
            status=ShipmentStatus.SHIPPED,
            is_disputed=True,
        )

        response = self.client.post(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
            {"action": "resolve_dispute"},
        )

        self.assertEqual(response.status_code, 200)
        shipment.refresh_from_db()
        self.assertTrue(shipment.is_disputed)
        self.assertEqual(shipment.status, ShipmentStatus.SHIPPED)
        self.assertContains(response, "Notes de résolution")

    def test_resolve_dispute_resets_status_to_ready(self):
        shipment = self._create_shipment(
            status=ShipmentStatus.SHIPPED,
            is_disputed=True,
        )
        carton = Carton.objects.create(
            code="CT-DSP-003",
            status=CartonStatus.SHIPPED,
            shipment=shipment,
        )

        with mock.patch("wms.shipment_tracking_handlers.log_shipment_dispute_action") as log_mock:
            response = self.client.post(
                reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
                {
                    "action": "resolve_dispute",
                    "dispute_resolution_notes": "Cartons recontroles et dossier relance.",
                },
            )

        self.assertEqual(response.status_code, 302)
        shipment.refresh_from_db()
        carton.refresh_from_db()
        self.assertFalse(shipment.is_disputed)
        self.assertEqual(shipment.status, ShipmentStatus.PACKED)
        self.assertEqual(carton.status, CartonStatus.LABELED)
        self.assertEqual(shipment.dossier_last_activity_label, "Litige résolu")
        self.assertIsNotNone(shipment.dossier_last_activity_at)
        log_mock.assert_called_once_with(
            shipment=shipment,
            action="resolve_dispute",
            user=self.user,
            previous_status=ShipmentStatus.SHIPPED,
            new_status=ShipmentStatus.PACKED,
        )

    def test_shipments_tracking_list_surfaces_dispute_as_primary_operator_signal(self):
        shipment = self._create_shipment(
            status=ShipmentStatus.PLANNED,
            is_disputed=True,
        )
        ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=ShipmentTrackingStatus.PLANNED,
            actor_name="Agent",
            actor_structure="ASF",
            comments="planned",
            created_by=self.user,
        )

        response = self.client.get(reverse("scan:scan_shipments_tracking"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Litige")
        self.assertContains(response, "Traiter le litige")

    def test_shipments_tracking_filter_open_disputes_only(self):
        disputed = self._create_shipment(
            status=ShipmentStatus.PLANNED,
            is_disputed=True,
        )
        undisputed = self._create_shipment(status=ShipmentStatus.SHIPPED)
        ShipmentTrackingEvent.objects.create(
            shipment=disputed,
            status=ShipmentTrackingStatus.PLANNED,
            actor_name="Agent",
            actor_structure="ASF",
            comments="planned",
            created_by=self.user,
        )
        ShipmentTrackingEvent.objects.create(
            shipment=undisputed,
            status=ShipmentTrackingStatus.BOARDING_OK,
            actor_name="Agent",
            actor_structure="ASF",
            comments="boarded",
            created_by=self.user,
        )

        response = self.client.get(
            reverse("scan:scan_shipments_tracking"),
            {"dispute": "open"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, disputed.reference)
        self.assertNotContains(response, undisputed.reference)

    def test_shipments_tracking_filter_overdue_disputes_only(self):
        overdue = self._create_shipment(
            status=ShipmentStatus.PLANNED,
            is_disputed=True,
        )
        overdue.dispute_reason = "docs_missing"
        overdue.dispute_owner = "qualite"
        overdue.dispute_status = "open"
        overdue.dispute_due_at = timezone.now() - timedelta(hours=3)
        overdue.save(
            update_fields=[
                "dispute_reason",
                "dispute_owner",
                "dispute_status",
                "dispute_due_at",
            ]
        )
        not_overdue = self._create_shipment(
            status=ShipmentStatus.PLANNED,
            is_disputed=True,
        )
        not_overdue.dispute_reason = "delivery_issue"
        not_overdue.dispute_owner = "transport"
        not_overdue.dispute_status = "in_progress"
        not_overdue.dispute_due_at = timezone.now() + timedelta(hours=5)
        not_overdue.save(
            update_fields=[
                "dispute_reason",
                "dispute_owner",
                "dispute_status",
                "dispute_due_at",
            ]
        )

        response = self.client.get(
            reverse("scan:scan_shipments_tracking"),
            {"dispute": "overdue"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, overdue.reference)
        self.assertNotContains(response, not_overdue.reference)

    def test_shipments_tracking_filter_unassigned_disputes_only(self):
        unassigned = self._create_shipment(
            status=ShipmentStatus.PLANNED,
            is_disputed=True,
        )
        unassigned.dispute_reason = "docs_missing"
        unassigned.dispute_status = "open"
        unassigned.save(update_fields=["dispute_reason", "dispute_status"])
        assigned = self._create_shipment(
            status=ShipmentStatus.PLANNED,
            is_disputed=True,
        )
        assigned.dispute_reason = "delivery_issue"
        assigned.dispute_owner = "transport"
        assigned.dispute_status = "in_progress"
        assigned.save(
            update_fields=[
                "dispute_reason",
                "dispute_owner",
                "dispute_status",
            ]
        )

        response = self.client.get(
            reverse("scan:scan_shipments_tracking"),
            {"dispute": "unassigned"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, unassigned.reference)
        self.assertNotContains(response, assigned.reference)

    def test_tracking_detail_renders_structured_dispute_summary(self):
        shipment = self._create_shipment(
            status=ShipmentStatus.PLANNED,
            is_disputed=True,
        )
        shipment.dispute_reason = "docs_missing"
        shipment.dispute_owner = "qualite"
        shipment.dispute_status = "in_progress"
        shipment.dispute_due_at = timezone.now() + timedelta(days=1)
        shipment.dispute_opened_at = timezone.now() - timedelta(hours=6)
        shipment.save(
            update_fields=[
                "dispute_reason",
                "dispute_owner",
                "dispute_status",
                "dispute_due_at",
                "dispute_opened_at",
            ]
        )

        response = self.client.get(
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Motif du litige")
        self.assertContains(response, "Documents manquants")
        self.assertContains(response, "Qualité")
        self.assertContains(response, "Historique du litige")
