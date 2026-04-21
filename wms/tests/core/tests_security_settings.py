import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

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
    ):
        env.pop(name, None)
    env.update(overrides)
    return env


class SecuritySettingsTests(SimpleTestCase):
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
