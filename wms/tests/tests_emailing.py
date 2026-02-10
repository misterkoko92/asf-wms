from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from wms.emailing import enqueue_email_safe, process_email_queue
from wms.models import (
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
)


class EmailQueueTests(TestCase):
    def test_enqueue_email_safe_creates_pending_event(self):
        queued = enqueue_email_safe(
            subject="Sujet test",
            message="Message test",
            recipient="dest@example.com",
        )

        self.assertTrue(queued)
        event = IntegrationEvent.objects.get()
        self.assertEqual(event.direction, IntegrationDirection.OUTBOUND)
        self.assertEqual(event.source, "wms.email")
        self.assertEqual(event.event_type, "send_email")
        self.assertEqual(event.status, IntegrationStatus.PENDING)
        self.assertEqual(event.payload["recipient"], ["dest@example.com"])
        self.assertEqual(event.payload["_queue"]["attempts"], 0)
        self.assertIsNone(event.payload["_queue"]["next_attempt_at"])

    @mock.patch("wms.emailing.send_email_safe")
    def test_process_email_queue_marks_event_processed(self, send_email_mock):
        send_email_mock.return_value = True
        enqueue_email_safe(
            subject="Sujet test",
            message="Message test",
            recipient="dest@example.com",
        )

        result = process_email_queue(limit=10)

        self.assertEqual(
            result,
            {
                "selected": 1,
                "processed": 1,
                "failed": 0,
                "retried": 0,
                "deferred": 0,
            },
        )
        event = IntegrationEvent.objects.get()
        self.assertEqual(event.status, IntegrationStatus.PROCESSED)
        self.assertEqual(event.error_message, "")
        self.assertIsNotNone(event.processed_at)
        send_email_mock.assert_called_once()

    @mock.patch("wms.emailing.send_email_safe")
    def test_process_email_queue_schedules_retry_on_failure(self, send_email_mock):
        send_email_mock.return_value = False
        enqueue_email_safe(
            subject="Sujet test",
            message="Message test",
            recipient="dest@example.com",
        )
        started_at = timezone.now()

        result = process_email_queue(
            limit=10,
            max_attempts=3,
            retry_base_seconds=120,
            retry_max_seconds=120,
        )

        self.assertEqual(
            result,
            {
                "selected": 1,
                "processed": 0,
                "failed": 0,
                "retried": 1,
                "deferred": 0,
            },
        )
        event = IntegrationEvent.objects.get()
        self.assertEqual(event.status, IntegrationStatus.PENDING)
        self.assertIn("retry 1/3 in 120s", event.error_message)
        self.assertIsNotNone(event.processed_at)
        self.assertEqual(event.payload["_queue"]["attempts"], 1)
        next_attempt_at = parse_datetime(event.payload["_queue"]["next_attempt_at"])
        self.assertIsNotNone(next_attempt_at)
        if timezone.is_naive(next_attempt_at):
            next_attempt_at = timezone.make_aware(next_attempt_at, timezone.get_current_timezone())
        self.assertGreater(next_attempt_at, started_at)
        send_email_mock.assert_called_once()

    @mock.patch("wms.emailing.send_email_safe")
    def test_process_email_queue_defers_event_until_next_attempt(self, send_email_mock):
        send_email_mock.return_value = True
        future = timezone.now() + timedelta(minutes=5)
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            target="smtp",
            event_type="send_email",
            payload={
                "subject": "Sujet test",
                "message": "Message test",
                "recipient": ["dest@example.com"],
                "_queue": {
                    "attempts": 1,
                    "next_attempt_at": future.isoformat(),
                },
            },
            status=IntegrationStatus.PENDING,
        )

        result = process_email_queue(limit=10)

        self.assertEqual(
            result,
            {
                "selected": 0,
                "processed": 0,
                "failed": 0,
                "retried": 0,
                "deferred": 1,
            },
        )
        send_email_mock.assert_not_called()

    @mock.patch("wms.emailing.send_email_safe")
    def test_process_email_queue_reclaims_stale_processing_event(self, send_email_mock):
        send_email_mock.return_value = True
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            target="smtp",
            event_type="send_email",
            payload={
                "subject": "Sujet stale processing",
                "message": "Message stale processing",
                "recipient": ["dest@example.com"],
                "_queue": {"attempts": 1, "next_attempt_at": None},
            },
            status=IntegrationStatus.PROCESSING,
            processed_at=timezone.now() - timedelta(minutes=30),
        )

        result = process_email_queue(limit=10, processing_timeout_seconds=60)

        self.assertEqual(
            result,
            {
                "selected": 1,
                "processed": 1,
                "failed": 0,
                "retried": 0,
                "deferred": 0,
            },
        )
        send_email_mock.assert_called_once()

    @mock.patch("wms.emailing.send_email_safe")
    def test_process_email_queue_skips_fresh_processing_event(self, send_email_mock):
        send_email_mock.return_value = True
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            target="smtp",
            event_type="send_email",
            payload={
                "subject": "Sujet fresh processing",
                "message": "Message fresh processing",
                "recipient": ["dest@example.com"],
                "_queue": {"attempts": 1, "next_attempt_at": None},
            },
            status=IntegrationStatus.PROCESSING,
            processed_at=timezone.now(),
        )

        result = process_email_queue(limit=10, processing_timeout_seconds=600)

        self.assertEqual(
            result,
            {
                "selected": 0,
                "processed": 0,
                "failed": 0,
                "retried": 0,
                "deferred": 0,
            },
        )
        send_email_mock.assert_not_called()

    @mock.patch("wms.emailing.send_email_safe")
    def test_process_email_queue_marks_event_failed_after_max_attempts(self, send_email_mock):
        send_email_mock.return_value = False
        event = IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            target="smtp",
            event_type="send_email",
            payload={
                "subject": "Sujet test",
                "message": "Message test",
                "recipient": ["dest@example.com"],
                "_queue": {
                    "attempts": 2,
                    "next_attempt_at": None,
                },
            },
            status=IntegrationStatus.PENDING,
        )

        result = process_email_queue(limit=10, max_attempts=3)

        self.assertEqual(
            result,
            {
                "selected": 1,
                "processed": 0,
                "failed": 1,
                "retried": 0,
                "deferred": 0,
            },
        )
        event.refresh_from_db()
        self.assertEqual(event.status, IntegrationStatus.FAILED)
        self.assertIn("after 3 attempt(s)", event.error_message)
        self.assertEqual(event.payload["_queue"]["attempts"], 3)
        self.assertIsNone(event.payload["_queue"]["next_attempt_at"])
        send_email_mock.assert_called_once()

    @mock.patch("wms.emailing.send_email_safe")
    def test_process_email_queue_retries_failed_when_enabled(self, send_email_mock):
        send_email_mock.return_value = True
        event = IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            target="smtp",
            event_type="send_email",
            payload={
                "subject": "Sujet test",
                "message": "Message test",
                "recipient": ["dest@example.com"],
                "_queue": {"attempts": 5, "next_attempt_at": None},
            },
            status=IntegrationStatus.FAILED,
            error_message="previous failure",
        )

        skipped = process_email_queue(limit=10, include_failed=False)
        processed = process_email_queue(limit=10, include_failed=True)

        self.assertEqual(
            skipped,
            {
                "selected": 0,
                "processed": 0,
                "failed": 0,
                "retried": 0,
                "deferred": 0,
            },
        )
        self.assertEqual(
            processed,
            {
                "selected": 1,
                "processed": 1,
                "failed": 0,
                "retried": 0,
                "deferred": 0,
            },
        )
        event.refresh_from_db()
        self.assertEqual(event.status, IntegrationStatus.PROCESSED)
        self.assertEqual(event.error_message, "")
        self.assertIsNotNone(event.processed_at)
        send_email_mock.assert_called_once()


class ProcessEmailQueueCommandTests(TestCase):
    @mock.patch("wms.emailing.send_email_safe")
    def test_process_email_queue_command_processes_events(self, send_email_mock):
        send_email_mock.return_value = True
        enqueue_email_safe(
            subject="Sujet commande",
            message="Message commande",
            recipient="dest@example.com",
        )
        out = StringIO()

        call_command("process_email_queue", "--limit=1", stdout=out)

        event = IntegrationEvent.objects.get()
        self.assertEqual(event.status, IntegrationStatus.PROCESSED)
        self.assertIn(
            "selected=1, processed=1, failed=0, retried=0, deferred=0",
            out.getvalue(),
        )
