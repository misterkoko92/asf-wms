from __future__ import annotations

from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from wms.helper_install import build_helper_install_context, build_helper_installer_payload


class HelperInstallTests(SimpleTestCase):
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
