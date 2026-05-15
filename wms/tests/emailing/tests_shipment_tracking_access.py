from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings

from wms.config import get_installation_config


class ShipmentTrackingAccessEmailTemplateTests(SimpleTestCase):
    def test_recovery_email_mentions_asf_id_role_and_return_links(self):
        message = render_to_string(
            "emails/shipment_tracking_access_recovery.txt",
            {
                "shipment": SimpleNamespace(reference="SHP-EMAIL-001"),
                "role_label": "Correspondant",
                "identifier": "ASF-C-00000042",
                "contact_identifier_label": "ASF ID",
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
                "contact_identifier_label": "ASF ID",
                "login_url": "https://example.test/login",
                "set_password_url": "https://example.test/password",  # pragma: allowlist secret
                "tracking_url": "https://example.test/track",
            },
        )

        self.assertIn("pending", message)
        self.assertIn("ASF ID", message)
        self.assertIn("ASF-C-00000043", message)
        self.assertIn("https://example.test/password", message)

    @override_settings(
        CONTACT_IDENTIFIER_LABEL="Contact ref.",
        TRACKING_CONTACT_IDENTIFIER_LABEL="Tracking ref.",
    )
    def test_recovery_email_uses_contact_identifier_label_override(self):
        message = render_to_string(
            "emails/shipment_tracking_access_recovery.txt",
            {
                "shipment": SimpleNamespace(reference="SHP-EMAIL-003"),
                "role_label": "Correspondant",
                "identifier": "ASF-C-00000044",
                "contact_identifier_label": (
                    get_installation_config().references.contact_identifier_label
                ),
                "escale_code": "CDG",
                "login_url": "https://example.test/login",
                "set_password_url": "https://example.test/password",  # pragma: allowlist secret
                "tracking_url": "https://example.test/track",
            },
        )

        self.assertIn("Contact ref. : ASF-C-00000044", message)
        self.assertIn("ASF-C-00000044", message)
        self.assertNotIn("Tracking ref.", message)

    @override_settings(
        CONTACT_IDENTIFIER_LABEL="Contact ref.",
        TRACKING_CONTACT_IDENTIFIER_LABEL="Tracking ref.",
    )
    def test_pending_email_uses_contact_identifier_label_override(self):
        message = render_to_string(
            "emails/shipment_tracking_pending_created.txt",
            {
                "shipment": SimpleNamespace(reference="SHP-EMAIL-004"),
                "role_label": "Expéditeur",
                "identifier": "ASF-C-00000045",
                "contact_identifier_label": (
                    get_installation_config().references.contact_identifier_label
                ),
                "login_url": "https://example.test/login",
                "set_password_url": "https://example.test/password",  # pragma: allowlist secret
                "tracking_url": "https://example.test/track",
            },
        )

        self.assertIn("Contact ref. : ASF-C-00000045", message)
        self.assertIn("ASF-C-00000045", message)
        self.assertNotIn("Tracking ref.", message)
