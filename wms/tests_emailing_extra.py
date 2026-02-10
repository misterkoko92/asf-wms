import json
import os
from unittest import mock
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from wms.emailing import (
    _brevo_settings,
    _normalize_recipients,
    _parse_next_attempt,
    _queue_meta,
    _safe_int,
    _send_with_brevo,
    EMAIL_QUEUE_EVENT_TYPE,
    EMAIL_QUEUE_SOURCE,
    EMAIL_QUEUE_TARGET,
    enqueue_email_safe,
    get_admin_emails,
    process_email_queue,
    send_email_safe,
)


class EmailingHelpersTests(TestCase):
    def test_get_admin_emails_returns_only_active_superusers_with_email(self):
        user_model = get_user_model()
        user_model.objects.create_superuser(
            username="admin-ok",
            email="admin-ok@example.com",
            password="pass1234",
        )
        user_model.objects.create_superuser(
            username="admin-empty",
            email="",
            password="pass1234",
        )
        inactive_admin = user_model.objects.create_superuser(
            username="admin-inactive",
            email="admin-inactive@example.com",
            password="pass1234",
        )
        inactive_admin.is_active = False
        inactive_admin.save(update_fields=["is_active"])
        user_model.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="pass1234",
        )

        emails = get_admin_emails()

        self.assertEqual(emails, ["admin-ok@example.com"])

    def test_recipient_and_int_helpers_cover_edge_cases(self):
        self.assertEqual(_normalize_recipients("one@example.com"), ["one@example.com"])
        self.assertEqual(_normalize_recipients(None), [])
        self.assertEqual(
            _normalize_recipients(["one@example.com", "", None, "two@example.com"]),
            ["one@example.com", "two@example.com"],
        )

        self.assertEqual(_safe_int("x", default=7, minimum=1), 7)
        self.assertEqual(_safe_int(-5, default=7, minimum=1), 1)

    def test_parse_next_attempt_and_queue_meta_handle_invalid_and_naive_values(self):
        self.assertIsNone(_parse_next_attempt(None))
        self.assertIsNone(_parse_next_attempt("not-a-date"))

        parsed = _parse_next_attempt("2026-01-10T12:30:00")
        self.assertIsNotNone(parsed)
        self.assertTrue(timezone.is_aware(parsed))

        default_meta = _queue_meta({"_queue": "invalid"})
        self.assertEqual(default_meta, {"attempts": 0, "next_attempt_at": None})

        parsed_meta = _queue_meta(
            {
                "_queue": {
                    "attempts": "bad",
                    "next_attempt_at": "2026-01-10T12:30:00",
                }
            }
        )
        self.assertEqual(parsed_meta["attempts"], 0)
        self.assertTrue(timezone.is_aware(parsed_meta["next_attempt_at"]))

    @override_settings(
        DEFAULT_FROM_EMAIL="default@example.com",
        BREVO_API_KEY="",
        BREVO_SENDER_EMAIL="",
        BREVO_SENDER_NAME="",
        BREVO_REPLY_TO_EMAIL="",
    )
    def test_brevo_settings_read_from_environment_and_default_sender(self):
        with mock.patch.dict(
            os.environ,
            {
                "BREVO_API_KEY": "env-key",
                "BREVO_SENDER_EMAIL": "sender@example.com",
                "BREVO_SENDER_NAME": "Env Sender",
                "BREVO_REPLY_TO_EMAIL": "reply@example.com",
            },
            clear=False,
        ):
            self.assertEqual(
                _brevo_settings(),
                (
                    "env-key",
                    "sender@example.com",
                    "Env Sender",
                    "reply@example.com",
                ),
            )

        with mock.patch.dict(
            os.environ,
            {"BREVO_API_KEY": "env-key", "BREVO_SENDER_EMAIL": "", "BREVO_SENDER_NAME": ""},
            clear=False,
        ):
            api_key, sender_email, sender_name, reply_to = _brevo_settings()
        self.assertEqual(api_key, "env-key")
        self.assertEqual(sender_email, "default@example.com")
        self.assertEqual(sender_name, "")
        self.assertEqual(reply_to, "")


class BrevoAndFallbackSendTests(TestCase):
    @override_settings(
        DEFAULT_FROM_EMAIL="default@example.com",
        BREVO_API_KEY="",
        BREVO_SENDER_EMAIL="",
    )
    def test_send_with_brevo_returns_false_when_missing_credentials(self):
        with mock.patch.dict(os.environ, {"BREVO_API_KEY": "", "BREVO_SENDER_EMAIL": ""}, clear=False):
            sent = _send_with_brevo(
                subject="Subject",
                message="Message",
                recipients=["dest@example.com"],
            )
        self.assertFalse(sent)

    @override_settings(
        BREVO_API_KEY="key-123",
        BREVO_SENDER_EMAIL="sender@example.com",
        BREVO_SENDER_NAME="Sender Name",
        BREVO_REPLY_TO_EMAIL="reply@example.com",
    )
    def test_send_with_brevo_success_includes_optional_fields(self):
        captured = {}

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"{}"

        def _fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _FakeResponse()

        with mock.patch("wms.emailing.urlopen", side_effect=_fake_urlopen):
            sent = _send_with_brevo(
                subject="Subject",
                message="Message",
                recipients=["dest@example.com"],
                html_message="<p>Hello</p>",
                tags=("tag-1", "tag-2"),
            )

        self.assertTrue(sent)
        self.assertEqual(captured["timeout"], 10)
        request = captured["request"]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["sender"]["email"], "sender@example.com")
        self.assertEqual(payload["subject"], "Subject")
        self.assertEqual(payload["textContent"], "Message")
        self.assertEqual(payload["htmlContent"], "<p>Hello</p>")
        self.assertEqual(payload["replyTo"]["email"], "reply@example.com")
        self.assertEqual(payload["tags"], ["tag-1", "tag-2"])
        header_items = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(header_items["api-key"], "key-123")

    @override_settings(BREVO_API_KEY="key-123", BREVO_SENDER_EMAIL="sender@example.com")
    def test_send_with_brevo_logs_warning_on_transport_error(self):
        with mock.patch("wms.emailing.urlopen", side_effect=URLError("down")):
            with mock.patch("wms.emailing.LOGGER.warning") as warning_mock:
                sent = _send_with_brevo(
                    subject="Subject",
                    message="Message",
                    recipients=["dest@example.com"],
                )

        self.assertFalse(sent)
        warning_mock.assert_called_once()

    @override_settings(BREVO_API_KEY="key-123", BREVO_SENDER_EMAIL="sender@example.com")
    def test_send_with_brevo_rejects_unexpected_endpoint(self):
        with mock.patch("wms.emailing.BREVO_API_URL", "http://evil.example/api"):
            with mock.patch("wms.emailing.urlopen") as urlopen_mock:
                with mock.patch("wms.emailing.LOGGER.warning") as warning_mock:
                    sent = _send_with_brevo(
                        subject="Subject",
                        message="Message",
                        recipients=["dest@example.com"],
                    )

        self.assertFalse(sent)
        urlopen_mock.assert_not_called()
        warning_mock.assert_called_once()

    @override_settings(DEFAULT_FROM_EMAIL="default@example.com")
    def test_send_email_safe_branches(self):
        self.assertFalse(send_email_safe(subject="S", message="M", recipient=None))

        with mock.patch("wms.emailing._send_with_brevo", return_value=True):
            with mock.patch("wms.emailing.send_mail") as send_mail_mock:
                sent = send_email_safe(
                    subject="Subject",
                    message="Message",
                    recipient=["dest@example.com"],
                )
        self.assertTrue(sent)
        send_mail_mock.assert_not_called()

        with mock.patch("wms.emailing._send_with_brevo", return_value=False):
            with mock.patch("wms.emailing.send_mail", return_value=1) as send_mail_mock:
                sent = send_email_safe(
                    subject="Subject",
                    message="Message",
                    recipient="dest@example.com",
                    html_message="<p>hello</p>",
                )
        self.assertTrue(sent)
        send_mail_mock.assert_called_once()

        with mock.patch("wms.emailing._send_with_brevo", return_value=False):
            with mock.patch("wms.emailing.send_mail", side_effect=RuntimeError("smtp down")):
                with mock.patch("wms.emailing.LOGGER.warning") as warning_mock:
                    sent = send_email_safe(
                        subject="Subject",
                        message="Message",
                        recipient=["dest@example.com"],
                    )
        self.assertFalse(sent)
        warning_mock.assert_called_once()


class EmailQueueExtraTests(TestCase):
    def test_enqueue_email_safe_handles_empty_recipient_and_optional_payload(self):
        self.assertFalse(
            enqueue_email_safe(
                subject="Sujet",
                message="Message",
                recipient=[],
            )
        )

        queued = enqueue_email_safe(
            subject="Sujet",
            message="Message",
            recipient="dest@example.com",
            html_message="<p>hello</p>",
            tags=("a", "b"),
        )
        self.assertTrue(queued)

        event = (
            process_email_queue.__globals__["IntegrationEvent"]
            .objects.filter(
                source=EMAIL_QUEUE_SOURCE,
                target=EMAIL_QUEUE_TARGET,
                event_type=EMAIL_QUEUE_EVENT_TYPE,
            )
            .get()
        )
        self.assertEqual(event.payload["recipient"], ["dest@example.com"])
        self.assertEqual(event.payload["html_message"], "<p>hello</p>")
        self.assertEqual(event.payload["tags"], ["a", "b"])

    @mock.patch("wms.emailing.send_email_safe", return_value=True)
    def test_process_email_queue_handles_invalid_limit_value(self, _send_mock):
        enqueue_email_safe(
            subject="Sujet",
            message="Message",
            recipient="dest@example.com",
        )

        result = process_email_queue(limit="invalid")

        self.assertEqual(result["selected"], 1)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["retried"], 0)
        self.assertEqual(result["deferred"], 0)

    def test_process_email_queue_skips_event_when_claim_update_fails(self):
        class _FakeEvent:
            def __init__(self):
                self.id = 1
                self.pk = 1
                self.created_at = timezone.now()
                self.payload = {
                    "subject": "Sujet",
                    "message": "Message",
                    "recipient": ["dest@example.com"],
                    "_queue": {"attempts": 0, "next_attempt_at": None},
                }
                self.status = "pending"
                self.processed_at = None
                self.error_message = ""

            def save(self, **kwargs):
                return None

        class _FakeQuerySet:
            def __init__(self, events, *, claim=False, state=None):
                self._events = events
                self._claim = claim
                self._state = state or {"slice_calls": 0}

            def filter(self, *args, **kwargs):
                if "pk" in kwargs:
                    return _FakeQuerySet(
                        self._events,
                        claim=True,
                        state=self._state,
                    )
                return _FakeQuerySet(
                    self._events,
                    claim=self._claim,
                    state=self._state,
                )

            def order_by(self, *args, **kwargs):
                return self

            def update(self, **kwargs):
                if self._claim:
                    return 0
                return 1

            def __getitem__(self, item):
                if isinstance(item, slice):
                    if self._claim:
                        return self._events[item]
                    self._state["slice_calls"] += 1
                    if self._state["slice_calls"] > 1:
                        return []
                    return self._events[item]
                raise TypeError("Expected slice")

        fake_queryset = _FakeQuerySet([_FakeEvent()])
        with mock.patch("wms.emailing._base_email_queue_queryset", return_value=fake_queryset):
            with mock.patch("wms.emailing.send_email_safe") as send_mock:
                result = process_email_queue(limit=1)

        self.assertEqual(result["selected"], 0)
        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["retried"], 0)
        self.assertEqual(result["deferred"], 0)
        send_mock.assert_not_called()
