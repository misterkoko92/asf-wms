from django.test import SimpleTestCase

from wms.admin_badges import render_admin_status_badge
from wms.status_badges import build_status_class, resolve_status_tone


class StatusBadgesTests(SimpleTestCase):
    def test_resolve_status_tone_by_domain(self):
        self.assertEqual(resolve_status_tone("approved", domain="order_review"), "ready")
        self.assertEqual(
            resolve_status_tone("changes_requested", domain="order_review"),
            "warning",
        )
        self.assertEqual(resolve_status_tone("failed", domain="integration"), "error")
        self.assertEqual(resolve_status_tone("unknown", domain="integration"), "progress")

    def test_resolve_status_tone_disputed_has_priority(self):
        self.assertEqual(
            resolve_status_tone("packed", domain="shipment", is_disputed=True),
            "error",
        )

    def test_resolve_status_tone_distinguishes_planned_and_shipped_shipments(self):
        self.assertEqual(resolve_status_tone("planned", domain="shipment"), "warning")
        self.assertEqual(resolve_status_tone("shipped", domain="shipment"), "info")

    def test_build_status_class_uses_base_class_and_tone(self):
        self.assertEqual(
            build_status_class("ready", domain="order", base_class="portal-badge"),
            "portal-badge is-ready",
        )

    def test_render_admin_status_badge_formats_inline_pill(self):
        html = render_admin_status_badge(
            status_value="pending",
            label="Pending",
            domain="document_review",
        )
        self.assertIn("Pending", html)
        self.assertIn("border-radius:999px", html)
