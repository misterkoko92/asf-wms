from django.test import SimpleTestCase

from wms.notification_policy import resolve_reference_notification_emails


class NotificationPolicyTests(SimpleTestCase):
    def test_resolve_reference_notification_emails_collects_and_deduplicates_values(self):
        recipients = resolve_reference_notification_emails(
            {"notification_emails": ["ops@example.org", "OPS@example.org", ""]},
            None,
            {"notification_emails": ["coord@example.org", "ops@example.org"]},
        )

        self.assertEqual(recipients, ["ops@example.org", "coord@example.org"])

    def test_resolve_reference_notification_emails_ignores_invalid_references(self):
        recipients = resolve_reference_notification_emails(
            {"notification_emails": ["shipper@example.org"]},
            {},
            {"notification_emails": None},
            "not-a-dict",
        )

        self.assertEqual(recipients, ["shipper@example.org"])
