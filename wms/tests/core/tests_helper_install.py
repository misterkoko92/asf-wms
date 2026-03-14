from __future__ import annotations

from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from django.test import RequestFactory, SimpleTestCase

from wms.helper_install import (
    build_helper_install_context,
    build_helper_installer_payload,
    build_helper_installer_response,
    resolve_helper_installer_access,
)


class HelperInstallTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_build_helper_installer_payload_for_macos_mentions_stable_helper_app(self):
        with (
            mock.patch("pathlib.Path.home", return_value=Path("/Users/test")),
            mock.patch("wms.helper_install._helper_bundle_base64", return_value="QUJD"),
        ):
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
        with (
            mock.patch("pathlib.Path.home", return_value=Path("/Users/test")),
            mock.patch("wms.helper_install._helper_bundle_base64", return_value="QUJD"),
        ):
            context = build_helper_install_context(
                install_url="/scan/helper/install/",
                app_label="asf-wms",
                system="Darwin",
                repo_root=Path("/repo"),
            )

        parsed = urlsplit(context["install_url"])
        self.assertEqual(parsed.path, "/scan/helper/install/")
        self.assertIn("installer_token", parse_qs(parsed.query))
        self.assertEqual(
            context["installed_app_path"],
            "/Users/test/Applications/ASF Planning Communication Helper.app",
        )
        self.assertTrue(context["post_install_guidance"].startswith("Au premier lancement"))
        self.assertEqual(context["minimum_helper_version"], "0.1.0")
        self.assertEqual(context["latest_helper_version"], "0.1.0")

    def test_build_helper_install_context_uses_absolute_macos_install_command(self):
        request = self.factory.get("/scan/shipments-ready/")
        with (
            mock.patch("pathlib.Path.home", return_value=Path("/Users/test")),
            mock.patch("wms.helper_install._helper_bundle_base64", return_value="QUJD"),
        ):
            context = build_helper_install_context(
                install_url="/scan/helper/install/",
                app_label="asf-wms",
                system="Darwin",
                repo_root=Path("/home/messmed/asf-wms"),
                request=request,
            )

        self.assertTrue(
            context["command"].startswith('curl -fsSL "http://testserver/scan/helper/install/?')
        )
        self.assertIn("installer_token=", context["command"])
        self.assertNotIn("/home/messmed/asf-wms", context["command"])
        self.assertIn("Copier la commande", context["post_install_guidance"])

        signed_install_url = context["install_url"]
        parsed = urlsplit(signed_install_url)
        self.assertEqual(parsed.path, "/scan/helper/install/")
        self.assertIn("installer_token", parse_qs(parsed.query))

    def test_build_helper_install_context_uses_client_macos_user_agent_before_linux_server(self):
        request = self.factory.get(
            "/scan/shipments-ready/",
            HTTP_USER_AGENT=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
            ),
        )
        with (
            mock.patch("pathlib.Path.home", return_value=Path("/Users/test")),
            mock.patch("wms.helper_install._helper_bundle_base64", return_value="QUJD"),
        ):
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

    def test_build_helper_installer_response_for_macos_is_self_contained(self):
        request = self.factory.get("/scan/helper/install/")
        with mock.patch("wms.helper_install._helper_bundle_base64", return_value="QUJD"):
            response = build_helper_installer_response(
                request=request,
                app_label="asf-wms",
                system="Darwin",
                repo_root=Path("/home/messmed/asf-wms"),
            )

        content = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("ASF/planning_comm_helper", content)
        self.assertIn("requirements-helper.txt", content)
        self.assertIn("tools.planning_comm_helper.autostart install", content)
        self.assertNotIn("/home/messmed/asf-wms/.venv/bin/python", content)
        self.assertNotIn('cd "/home/messmed/asf-wms"', content)

    def test_build_helper_installer_response_uses_signed_platform_hint_without_browser_headers(
        self,
    ):
        request = self.factory.get("/scan/shipments-ready/")
        with (
            mock.patch("pathlib.Path.home", return_value=Path("/Users/test")),
            mock.patch("wms.helper_install._helper_bundle_base64", return_value="QUJD"),
        ):
            context = build_helper_install_context(
                install_url="/scan/helper/install/",
                app_label="asf-wms",
                system="Darwin",
                repo_root=Path("/repo"),
                request=request,
            )

        signed_request = self.factory.get(context["install_url"])
        with mock.patch("wms.helper_install._helper_bundle_base64", return_value="QUJD"):
            response = build_helper_installer_response(
                request=signed_request,
                app_label="asf-wms",
                system="Linux",
                repo_root=Path("/repo"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="install-asf-wms-helper.command"',
        )
        self.assertIn("#!/bin/zsh", response.content.decode())

    def test_build_helper_installer_response_uses_client_windows_platform_hint(self):
        request = self.factory.get(
            "/scan/helper/install/",
            HTTP_SEC_CH_UA_PLATFORM='"Windows"',
        )

        with mock.patch("wms.helper_install._helper_bundle_base64", return_value="QUJD"):
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

    def test_build_helper_install_context_uses_absolute_windows_install_command(self):
        request = self.factory.get("/scan/shipments-ready/")
        with mock.patch("wms.helper_install._helper_bundle_base64", return_value="QUJD"):
            context = build_helper_install_context(
                install_url="/scan/helper/install/",
                app_label="asf-wms",
                system="Windows",
                repo_root=Path("/home/messmed/asf-wms"),
                request=request,
            )

        self.assertIn("powershell", context["command"].lower())
        self.assertIn("http://testserver/scan/helper/install/", context["command"])
        self.assertIn("-OutFile", context["command"])
        self.assertIn("installer_token=", context["command"])
        self.assertNotIn("/home/messmed/asf-wms", context["command"])

    def test_resolve_helper_installer_access_returns_signed_platform(self):
        request = self.factory.get("/scan/shipments-ready/")
        with (
            mock.patch("pathlib.Path.home", return_value=Path("/Users/test")),
            mock.patch("wms.helper_install._helper_bundle_base64", return_value="QUJD"),
        ):
            context = build_helper_install_context(
                install_url="/scan/helper/install/",
                app_label="asf-wms",
                system="Windows",
                repo_root=Path("/repo"),
                request=request,
            )

        signed_request = self.factory.get(context["install_url"])
        access = resolve_helper_installer_access(
            signed_request,
            app_label="asf-wms",
        )

        self.assertEqual(
            access,
            {
                "app_label": "asf-wms",
                "install_path": "/scan/helper/install/",
                "system": "Windows",
            },
        )
