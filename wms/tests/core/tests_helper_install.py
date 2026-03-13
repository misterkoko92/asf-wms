from __future__ import annotations

from pathlib import Path
from unittest import mock

from django.test import RequestFactory, SimpleTestCase

from wms.helper_install import (
    build_helper_install_context,
    build_helper_installer_payload,
    build_helper_installer_response,
)


class HelperInstallTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_build_helper_installer_payload_for_macos_mentions_stable_helper_app(self):
        with mock.patch("pathlib.Path.home", return_value=Path("/Users/test")):
            payload = build_helper_installer_payload(
                app_label="asf-wms",
                system="Darwin",
                repo_root=Path("/repo"),
            )

        self.assertEqual(
            payload["installed_app_path"],
            "/Users/test/Applications/ASF Planning Communication Helper.app",
        )
        self.assertIn("ASF Planning Communication Helper", payload["post_install_guidance"])
        self.assertIn("Microsoft Excel", payload["post_install_guidance"])

    def test_build_helper_install_context_keeps_stable_helper_guidance(self):
        with mock.patch("pathlib.Path.home", return_value=Path("/Users/test")):
            context = build_helper_install_context(
                install_url="/scan/helper/install/",
                app_label="asf-wms",
                system="Darwin",
                repo_root=Path("/repo"),
            )

        self.assertEqual(context["install_url"], "/scan/helper/install/")
        self.assertEqual(
            context["installed_app_path"],
            "/Users/test/Applications/ASF Planning Communication Helper.app",
        )
        self.assertTrue(context["post_install_guidance"].startswith("Au premier lancement"))
        self.assertEqual(context["minimum_helper_version"], "0.1.0")
        self.assertEqual(context["latest_helper_version"], "0.1.0")

    def test_build_helper_install_context_uses_client_macos_user_agent_before_linux_server(self):
        request = self.factory.get(
            "/scan/shipments-ready/",
            HTTP_USER_AGENT=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
            ),
        )
        with mock.patch("pathlib.Path.home", return_value=Path("/Users/test")):
            context = build_helper_install_context(
                install_url="/scan/helper/install/",
                app_label="asf-wms",
                system="Linux",
                repo_root=Path("/repo"),
                request=request,
            )

        self.assertTrue(context["available"])
        self.assertEqual(context["platform_label"], "macOS")
        self.assertEqual(context["download_label"], "Installer le helper (macOS)")
        self.assertEqual(
            context["installed_app_path"],
            "/Users/test/Applications/ASF Planning Communication Helper.app",
        )

    def test_build_helper_installer_response_uses_client_windows_platform_hint(self):
        request = self.factory.get(
            "/scan/helper/install/",
            HTTP_SEC_CH_UA_PLATFORM='"Windows"',
        )

        response = build_helper_installer_response(
            request=request,
            app_label="asf-wms",
            system="Linux",
            repo_root=Path("/repo"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="install-asf-wms-helper.cmd"',
        )
        self.assertIn("@echo off", response.content.decode())
