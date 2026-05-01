from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings

from wms.emailing import (
    enqueue_email_safe,
    format_email_subject,
    process_email_queue,
    send_email_safe,
)
from wms.models import IntegrationDirection, IntegrationEvent, IntegrationStatus


class EmailSubjectFormattingTests(TestCase):
    def test_format_email_subject_default_preserves_current_prefix(self):
        self.assertEqual(format_email_subject("ASF WMS - X"), "ASF WMS - X")

    def test_format_email_subject_unprefixed_gets_default_prefix(self):
        self.assertEqual(format_email_subject("X"), "ASF WMS - X")

    def test_format_email_subject_idempotence_double_call(self):
        formatted = format_email_subject("X")

        self.assertEqual(format_email_subject(formatted), formatted)

    def test_format_email_subject_idempotence_no_space_after_dash(self):
        self.assertEqual(
            format_email_subject("ASF WMS -Nouvelle commande"),
            "ASF WMS -Nouvelle commande",
        )

    def test_format_email_subject_reads_installation_config(self):
        installation = SimpleNamespace(
            notifications=SimpleNamespace(email_subject_prefix="CLIENT - "),
        )

        with mock.patch("wms.emailing.get_installation_config", return_value=installation):
            self.assertEqual(format_email_subject("X"), "CLIENT - X")

    @override_settings(DEFAULT_FROM_EMAIL="default@example.com")
    def test_send_email_safe_applies_subject_formatting_brevo(self):
        with mock.patch("wms.emailing._send_with_brevo", return_value=True) as brevo_mock:
            with mock.patch("wms.emailing.send_mail") as send_mail_mock:
                sent = send_email_safe(
                    subject="X",
                    message="Message",
                    recipient=["dest@example.com"],
                )

        self.assertTrue(sent)
        brevo_mock.assert_called_once()
        self.assertEqual(brevo_mock.call_args.kwargs["subject"], "ASF WMS - X")
        send_mail_mock.assert_not_called()

    @override_settings(DEFAULT_FROM_EMAIL="default@example.com")
    def test_send_email_safe_applies_subject_formatting_smtp_fallback(self):
        with mock.patch("wms.emailing._send_with_brevo", return_value=False):
            with mock.patch("wms.emailing.send_mail", return_value=1) as send_mail_mock:
                sent = send_email_safe(
                    subject="X",
                    message="Message",
                    recipient="dest@example.com",
                )

        self.assertTrue(sent)
        send_mail_mock.assert_called_once_with(
            "ASF WMS - X",
            "Message",
            "default@example.com",
            ["dest@example.com"],
            fail_silently=False,
            html_message=None,
        )

    @override_settings(EMAIL_DELIVERY_MODE="direct_only", DEFAULT_FROM_EMAIL="default@example.com")
    def test_enqueue_email_safe_direct_only_applies_formatting(self):
        with mock.patch("wms.emailing._send_with_brevo", return_value=False):
            with mock.patch("wms.emailing.send_mail", return_value=1) as send_mail_mock:
                queued = enqueue_email_safe(
                    subject="X",
                    message="Message",
                    recipient="dest@example.com",
                )

        self.assertTrue(queued)
        self.assertEqual(IntegrationEvent.objects.count(), 0)
        self.assertEqual(send_mail_mock.call_args.args[0], "ASF WMS - X")

    @override_settings(DEFAULT_FROM_EMAIL="default@example.com")
    def test_process_email_queue_applies_formatting_to_queued_payload(self):
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            target="smtp",
            event_type="send_email",
            payload={
                "subject": "ASF WMS - Y",
                "message": "Message",
                "recipient": ["dest@example.com"],
                "_queue": {"attempts": 0, "next_attempt_at": None},
            },
            status=IntegrationStatus.PENDING,
        )

        with mock.patch("wms.emailing._send_with_brevo", return_value=True) as brevo_mock:
            result = process_email_queue(limit=10)

        self.assertEqual(result["processed"], 1)
        brevo_mock.assert_called_once()
        self.assertEqual(brevo_mock.call_args.kwargs["subject"], "ASF WMS - Y")

    def test_pack_review_subject_receives_prefix_after_pr2(self):
        self.assertEqual(
            format_email_subject("Revue produit requise : ABC"),
            "ASF WMS - Revue produit requise : ABC",
        )
