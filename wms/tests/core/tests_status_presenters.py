from types import SimpleNamespace

from django.test import SimpleTestCase

from wms.status_presenters import (
    present_order_review_status,
    present_order_shipment_status,
    present_order_status,
    present_shipment_status,
)


class StatusPresentersTests(SimpleTestCase):
    def test_present_shipment_status_uses_disponible_for_packed(self):
        shipment = SimpleNamespace(status="packed", is_disputed=False)

        payload = present_shipment_status(shipment)

        self.assertEqual(payload["value"], "packed")
        self.assertEqual(payload["label"], "Disponible")
        self.assertEqual(payload["domain"], "shipment")
        self.assertFalse(payload["is_disputed"])

    def test_present_shipment_status_keeps_litige_prefix(self):
        shipment = SimpleNamespace(status="planned", is_disputed=True)

        payload = present_shipment_status(shipment)

        self.assertEqual(payload["label"], "Litige - Planifié")
        self.assertTrue(payload["is_disputed"])

    def test_present_order_status_uses_canonical_portal_wording(self):
        order = SimpleNamespace(status="reserved")

        payload = present_order_status(order)

        self.assertEqual(payload["label"], "Réservée")
        self.assertEqual(payload["domain"], "order")

    def test_present_order_review_status_uses_state_wording(self):
        order = SimpleNamespace(review_status="changes_requested")

        payload = present_order_review_status(order)

        self.assertEqual(payload["label"], "Modifications demandées")
        self.assertEqual(payload["domain"], "order_review")

    def test_present_order_shipment_status_returns_dash_without_linked_shipment(self):
        order = SimpleNamespace(shipment=None)

        payload = present_order_shipment_status(order)

        self.assertEqual(payload["value"], "")
        self.assertEqual(payload["label"], "-")
        self.assertEqual(payload["domain"], "shipment")

    def test_present_order_shipment_status_uses_linked_shipment_status(self):
        order = SimpleNamespace(
            shipment=SimpleNamespace(status="packed", is_disputed=False),
        )

        payload = present_order_shipment_status(order)

        self.assertEqual(payload["value"], "packed")
        self.assertEqual(payload["label"], "Disponible")
