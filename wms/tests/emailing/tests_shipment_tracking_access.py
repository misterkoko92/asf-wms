from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


class ShipmentTrackingAccessEmailTemplateTests(SimpleTestCase):
    def test_recovery_email_mentions_asf_id_role_and_return_links(self):
        message = render_to_string(
            "emails/shipment_tracking_access_recovery.txt",
            {
                "shipment": SimpleNamespace(reference="SHP-EMAIL-001"),
                "role_label": "Correspondant",
                "identifier": "ASF-C-00000042",
                "escale_code": "CDG",
                "login_url": "https://example.test/login",
                "set_password_url": "https://example.test/password",  # pragma: allowlist secret
                "tracking_url": "https://example.test/track",
            },
        )

        self.assertIn("ASF ID", message)
        self.assertIn("Correspondant", message)
        self.assertIn("ASF-C-00000042", message)
        self.assertIn("https://example.test/login", message)
        self.assertIn("https://example.test/track", message)

    def test_pending_email_mentions_pending_status_and_assigned_asf_id(self):
        message = render_to_string(
            "emails/shipment_tracking_pending_created.txt",
            {
                "shipment": SimpleNamespace(reference="SHP-EMAIL-002"),
                "role_label": "Expéditeur",
                "identifier": "ASF-C-00000043",
                "login_url": "https://example.test/login",
                "set_password_url": "https://example.test/password",  # pragma: allowlist secret
                "tracking_url": "https://example.test/track",
            },
        )

        self.assertIn("pending", message)
        self.assertIn("ASF ID", message)
        self.assertIn("ASF-C-00000043", message)
        self.assertIn("https://example.test/password", message)
