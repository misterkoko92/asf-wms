import json
import os
import re
import subprocess
import sys
from pathlib import Path

from django.test import TestCase

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

    def test_frontend_dynamic_html_sinks_are_removed_from_touched_flows(self):
        portal_account = (REPO_ROOT / "templates/portal/account.html").read_text(encoding="utf-8")
        mapping_editor = (REPO_ROOT / "wms/static/scan/print_pack_mapping_editor.js").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("insertAdjacentHTML", portal_account)
        self.assertNotIn("row.innerHTML", mapping_editor)
        self.assertNotIn(".outerHTML", mapping_editor)
