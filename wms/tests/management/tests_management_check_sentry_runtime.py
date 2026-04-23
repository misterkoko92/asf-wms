from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from asf_wms.settings import _SENTRY_FILTERED, _sentry_before_send


class CheckSentryRuntimeCommandTests(SimpleTestCase):
    @override_settings(SENTRY_DSN="")
    def test_allow_missing_reports_skip_ok(self):
        output = StringIO()

        call_command("check_sentry_runtime", "--allow-missing", stdout=output)

        self.assertIn("SENTRY_DSN absent", output.getvalue())

    @override_settings(SENTRY_DSN="")
    def test_missing_dsn_fails_without_allow_missing(self):
        with self.assertRaisesMessage(CommandError, "SENTRY_DSN n'est pas configure"):
            call_command("check_sentry_runtime")

    @override_settings(SENTRY_DSN="https://public@example.invalid/1")
    @mock.patch("wms.management.commands.check_sentry_runtime.importlib.util.find_spec")
    def test_configured_dsn_requires_sentry_sdk_package(self, find_spec_mock):
        find_spec_mock.return_value = None

        with self.assertRaisesMessage(CommandError, "sentry-sdk"):
            call_command("check_sentry_runtime")

    @override_settings(
        SENTRY_DSN="https://public@example.invalid/1",
        SENTRY_ENVIRONMENT="test",
        SENTRY_RELEASE="test-release",
        SENTRY_SAMPLE_RATE=1.0,
        SENTRY_TRACES_SAMPLE_RATE=0.0,
        SENTRY_SEND_DEFAULT_PII=False,
    )
    @mock.patch("wms.management.commands.check_sentry_runtime.importlib.util.find_spec")
    def test_configured_dsn_reports_runtime_snapshot(self, find_spec_mock):
        find_spec_mock.return_value = object()
        output = StringIO()

        call_command("check_sentry_runtime", stdout=output)

        self.assertIn("environment=test", output.getvalue())
        self.assertIn("send_default_pii=False", output.getvalue())

    @override_settings(
        SENTRY_DSN="https://public@example.invalid/1",
        SENTRY_ENVIRONMENT="test",
        SENTRY_RELEASE="",
        SENTRY_SAMPLE_RATE=1.0,
        SENTRY_TRACES_SAMPLE_RATE=0.0,
        SENTRY_SEND_DEFAULT_PII=False,
    )
    @mock.patch("wms.management.commands.check_sentry_runtime.importlib.import_module")
    @mock.patch("wms.management.commands.check_sentry_runtime.importlib.util.find_spec")
    def test_send_test_captures_message_and_flushes(self, find_spec_mock, import_module_mock):
        find_spec_mock.return_value = object()
        sentry_mock = mock.Mock()
        import_module_mock.return_value = sentry_mock
        output = StringIO()

        call_command("check_sentry_runtime", "--send-test", "--flush-timeout=0.1", stdout=output)

        sentry_mock.capture_message.assert_called_once_with("ASF WMS Sentry runtime check")
        sentry_mock.flush.assert_called_once_with(timeout=0.1)
        self.assertIn("test event sent", output.getvalue())

    def test_before_send_strips_query_and_sensitive_request_values(self):
        event = {
            "request": {
                "url": "https://example.test/scan/?token=secret&shipment=ABC",
                "query_string": "token=secret&shipment=ABC",
                "headers": {
                    "Authorization": "Bearer secret",
                    "X-Request-ID": "req-1",
                },  # pragma: allowlist secret
                "cookies": {"sessionid": "secret"},
                "data": {"password": "secret", "reference": "ABC"},  # pragma: allowlist secret
            },
            "extra": {"api_key": "secret", "safe_value": "visible"},  # pragma: allowlist secret
        }

        filtered_event = _sentry_before_send(event, {})

        self.assertEqual(filtered_event["request"]["url"], "https://example.test/scan/")
        self.assertEqual(filtered_event["request"]["query_string"], _SENTRY_FILTERED)
        self.assertEqual(filtered_event["request"]["headers"]["Authorization"], _SENTRY_FILTERED)
        self.assertEqual(filtered_event["request"]["headers"]["X-Request-ID"], "req-1")
        self.assertEqual(filtered_event["request"]["cookies"]["sessionid"], _SENTRY_FILTERED)
        self.assertEqual(filtered_event["request"]["data"]["password"], _SENTRY_FILTERED)
        self.assertEqual(filtered_event["request"]["data"]["reference"], "ABC")
        self.assertEqual(filtered_event["extra"]["api_key"], _SENTRY_FILTERED)
        self.assertEqual(filtered_event["extra"]["safe_value"], "visible")
