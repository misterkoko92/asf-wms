import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

import asf_wms.settings as django_settings
from wms.security_headers import (
    CSP_REPORT_ONLY_HEADER,
    ContentSecurityPolicyReportOnlyMiddleware,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
VALID_DJANGO_SETTING_VALUE = "test-" + ("x" * 60)


def _settings_env(**overrides: str) -> dict[str, str]:
    env = os.environ.copy()
    for name in (
        "CSRF_COOKIE_SAMESITE",
        "DJANGO_DEBUG",
        "DJANGO_SECRET_KEY",
        "DOCUMENT_SCAN_BACKEND",
        "SESSION_COOKIE_SAMESITE",
        "SENTRY_DSN",
        "SENTRY_ENVIRONMENT",
        "SENTRY_RELEASE",
        "SENTRY_SAMPLE_RATE",
        "SENTRY_SEND_DEFAULT_PII",
        "SENTRY_TRACES_SAMPLE_RATE",
    ):
        env.pop(name, None)
    env.update(overrides)
    return env


class SecuritySettingsTests(TestCase):
    def test_env_parsing_helpers_handle_defaults_invalid_and_valid_values(self):
        with mock.patch.dict(
            os.environ,
            {
                "TEST_INT": "7",
                "TEST_BAD_INT": "seven",
                "TEST_FLOAT": "0.25",
                "TEST_BAD_FLOAT": "quarter",
                "TEST_OPTIONAL_FLOAT": "0.5",
                "TEST_BAD_OPTIONAL_FLOAT": "half",
            },
            clear=False,
        ):
            self.assertEqual(django_settings._env_int("TEST_MISSING_INT", 3), 3)
            self.assertEqual(django_settings._env_int("TEST_INT", 3), 7)
            self.assertEqual(django_settings._env_int("TEST_BAD_INT", 3), 3)
            self.assertEqual(django_settings._env_float("TEST_MISSING_FLOAT", 1.0), 1.0)
            self.assertEqual(django_settings._env_float("TEST_FLOAT", 1.0), 0.25)
            self.assertEqual(django_settings._env_float("TEST_BAD_FLOAT", 1.0), 1.0)
            self.assertIsNone(django_settings._env_optional_float("TEST_MISSING_OPTIONAL_FLOAT"))
            self.assertEqual(
                django_settings._env_optional_float("TEST_OPTIONAL_FLOAT"),
                0.5,
            )
            self.assertIsNone(django_settings._env_optional_float("TEST_BAD_OPTIONAL_FLOAT"))

    def test_secret_key_and_sentry_rate_helpers_cover_edges(self):
        self.assertFalse(django_settings._is_secure_secret_key(""))
        self.assertFalse(django_settings._is_secure_secret_key("django-insecure-" + ("x" * 60)))
        self.assertFalse(django_settings._is_secure_secret_key("short"))
        self.assertFalse(django_settings._is_secure_secret_key("x" * 64))
        self.assertTrue(django_settings._is_secure_secret_key("test-" + ("abc123XYZ" * 7)))

        django_settings._validate_sentry_rate("SENTRY_SAMPLE_RATE", None)
        django_settings._validate_sentry_rate("SENTRY_SAMPLE_RATE", 0.0)
        django_settings._validate_sentry_rate("SENTRY_SAMPLE_RATE", 1.0)
        with self.assertRaisesMessage(ImproperlyConfigured, "SENTRY_SAMPLE_RATE"):
            django_settings._validate_sentry_rate("SENTRY_SAMPLE_RATE", -0.1)

    def test_sentry_before_send_redacts_nested_and_non_dict_request_values(self):
        event = {
            "request": {
                "url": "https://example.test/scan/",
                "headers": "raw-auth-token",
                "cookies": {"sessionid": "cookie-value"},
                "env": {
                    "SAFE_VALUE": "visible",
                    "AUTHORIZATION": "Bearer token",
                },
            },
            "contexts": {
                "runtime": {
                    "token": "secret-token",  # pragma: allowlist secret
                    "safe_list": ["visible", {"password": "hidden"}],  # pragma: allowlist secret
                }
            },
        }

        filtered = django_settings._sentry_before_send(event, {})

        self.assertEqual(filtered["request"]["url"], "https://example.test/scan/")
        self.assertEqual(filtered["request"]["headers"], django_settings._SENTRY_FILTERED)
        self.assertEqual(
            filtered["request"]["cookies"]["sessionid"],
            django_settings._SENTRY_FILTERED,
        )
        self.assertEqual(filtered["request"]["env"]["SAFE_VALUE"], "visible")
        self.assertEqual(
            filtered["request"]["env"]["AUTHORIZATION"],
            django_settings._SENTRY_FILTERED,
        )
        self.assertEqual(
            filtered["contexts"]["runtime"]["token"],
            django_settings._SENTRY_FILTERED,
        )
        self.assertEqual(filtered["contexts"]["runtime"]["safe_list"][0], "visible")
        self.assertEqual(
            filtered["contexts"]["runtime"]["safe_list"][1]["password"],
            django_settings._SENTRY_FILTERED,
        )

    def test_security_defaults_keep_strict_cookie_policy(self):
        command = (
            "import json; "
            "import asf_wms.settings as s; "
            "print(json.dumps({"
            "'csrf_cookie_httponly': s.CSRF_COOKIE_HTTPONLY, "
            "'csrf_cookie_samesite': s.CSRF_COOKIE_SAMESITE, "
            "'session_cookie_httponly': s.SESSION_COOKIE_HTTPONLY, "
            "'session_cookie_samesite': s.SESSION_COOKIE_SAMESITE"
            "}, sort_keys=True))"
        )
        result = subprocess.run(
            [sys.executable, "-c", command],
            cwd=REPO_ROOT,
            env=_settings_env(DJANGO_SECRET_KEY=VALID_DJANGO_SETTING_VALUE),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "csrf_cookie_httponly": True,
                "csrf_cookie_samesite": "Strict",
                "session_cookie_httponly": True,
                "session_cookie_samesite": "Strict",
            },
        )

    def test_csp_report_only_header_is_enabled(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Content-Security-Policy-Report-Only", response)
        policy = response["Content-Security-Policy-Report-Only"]
        self.assertIn("default-src 'self'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertIn("base-uri 'self'", policy)
        self.assertIn("frame-ancestors 'none'", policy)

    def test_csp_report_only_does_not_allow_dormant_ocr_cdn_capabilities(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        policy = response["Content-Security-Policy-Report-Only"]
        self.assertIn("script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net", policy)
        self.assertIn(
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
            policy,
        )
        self.assertIn("font-src 'self' https://fonts.gstatic.com data:", policy)
        self.assertIn("connect-src 'self' https://nominatim.openstreetmap.org", policy)
        self.assertIn("worker-src 'self' blob:", policy)
        self.assertNotIn("'wasm-unsafe-eval'", policy)
        self.assertNotIn(
            "connect-src 'self' https://nominatim.openstreetmap.org https://cdn.jsdelivr.net",
            policy,
        )
        self.assertNotIn("worker-src 'self' blob: https://cdn.jsdelivr.net", policy)

    @override_settings(CSP_REPORT_ONLY_ENABLED=False)
    def test_csp_report_only_middleware_can_be_disabled(self):
        middleware = ContentSecurityPolicyReportOnlyMiddleware(lambda request: HttpResponse("ok"))

        response = middleware(RequestFactory().get("/"))

        self.assertNotIn(CSP_REPORT_ONLY_HEADER, response)

    def test_noop_document_scan_backend_is_rejected_outside_tests_even_in_debug(self):
        result = subprocess.run(
            [sys.executable, "-c", "import asf_wms.settings"],
            cwd=REPO_ROOT,
            env=_settings_env(
                DJANGO_DEBUG="true",
                DJANGO_SECRET_KEY=VALID_DJANGO_SETTING_VALUE,
                DOCUMENT_SCAN_BACKEND="noop",
            ),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DOCUMENT_SCAN_BACKEND=noop is only allowed in tests", result.stderr)

    def test_invalid_sentry_sample_rate_is_rejected_when_dsn_is_configured(self):
        result = subprocess.run(
            [sys.executable, "-c", "import asf_wms.settings"],
            cwd=REPO_ROOT,
            env=_settings_env(
                DJANGO_SECRET_KEY=VALID_DJANGO_SETTING_VALUE,
                SENTRY_DSN="https://public@example.invalid/1",
                SENTRY_SAMPLE_RATE="1.5",
            ),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SENTRY_SAMPLE_RATE must be between 0.0 and 1.0", result.stderr)

    def test_rest_framework_has_default_throttles(self):
        command = (
            "import json; "
            "import asf_wms.settings as s; "
            "print(json.dumps({"
            "'classes': s.REST_FRAMEWORK.get('DEFAULT_THROTTLE_CLASSES'), "
            "'rates': s.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES')"
            "}, sort_keys=True))"
        )
        result = subprocess.run(
            [sys.executable, "-c", command],
            cwd=REPO_ROOT,
            env=_settings_env(DJANGO_SECRET_KEY=VALID_DJANGO_SETTING_VALUE),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("rest_framework.throttling.UserRateThrottle", payload["classes"])
        self.assertIn("rest_framework.throttling.AnonRateThrottle", payload["classes"])
        self.assertEqual(payload["rates"]["user"], "120/minute")
        self.assertEqual(payload["rates"]["anon"], "30/minute")

    def test_password_minimum_length_is_explicitly_twelve(self):
        command = (
            "import json; "
            "import asf_wms.settings as s; "
            "minimum = next("
            "item for item in s.AUTH_PASSWORD_VALIDATORS "
            "if item['NAME'].endswith('MinimumLengthValidator')"
            "); "
            "print(json.dumps(minimum.get('OPTIONS'), sort_keys=True))"
        )
        result = subprocess.run(
            [sys.executable, "-c", command],
            cwd=REPO_ROOT,
            env=_settings_env(DJANGO_SECRET_KEY=VALID_DJANGO_SETTING_VALUE),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"min_length": 12})

    def test_templates_do_not_open_blank_targets_without_noopener(self):
        offenders = []
        target_pattern = re.compile(r"<[^>]+target=[\"']_blank[\"'][^>]*>", re.IGNORECASE)
        for path in (REPO_ROOT / "templates").rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            for match in target_pattern.finditer(text):
                tag = match.group(0)
                if not re.search(r"rel=[\"'][^\"']*\bnoopener\b", tag, re.IGNORECASE):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {tag[:160]}")

        self.assertEqual(offenders, [])

    def test_bootstrap_cdn_assets_use_sri(self):
        offenders = []
        bootstrap_pattern = re.compile(
            r"<(?:link|script)[^>]+cdn\.jsdelivr\.net/npm/bootstrap@5\.3\.3/dist/[^>]+>",
            re.IGNORECASE,
        )
        for path in (REPO_ROOT / "templates").rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            for match in bootstrap_pattern.finditer(text):
                tag = match.group(0)
                if "integrity=" not in tag or "crossorigin=" not in tag:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {tag[:160]}")

        self.assertEqual(offenders, [])

    def test_static_javascript_does_not_ship_tesseract_cdn_loader(self):
        forbidden_sources = [
            "cdn.jsdelivr.net/npm/" + "tesseract",
            "tesseract.js" + "-core",
            "tesseract.js" + "-data",
        ]
        offenders = []
        for path in (REPO_ROOT / "wms/static").rglob("*.js"):
            text = path.read_text(encoding="utf-8")
            for forbidden_source in forbidden_sources:
                if forbidden_source in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {forbidden_source}")

        self.assertEqual(offenders, [])

    def test_frontend_dynamic_html_sinks_are_removed_from_touched_flows(self):
        portal_account = (REPO_ROOT / "templates/portal/account.html").read_text(encoding="utf-8")
        mapping_editor = (REPO_ROOT / "wms/static/scan/print_pack_mapping_editor.js").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("insertAdjacentHTML", portal_account)
        self.assertNotIn("row.innerHTML", mapping_editor)
        self.assertNotIn(".outerHTML", mapping_editor)
