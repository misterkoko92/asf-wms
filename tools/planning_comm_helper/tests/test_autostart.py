from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.planning_comm_helper import autostart


class PlanningCommunicationHelperAutostartTests(unittest.TestCase):
    def test_build_macos_launchagent_plist_uses_current_repo_and_python(self):
        paths = autostart.MacAutostartPaths(
            plist_path=Path("/Users/test/Library/LaunchAgents/com.asf.planning_comm_helper.plist"),
            log_path=Path("/tmp/asf-planning-comm-helper.log"),
            python_path=Path("/repo/.venv/bin/python"),
            repo_root=Path("/repo"),
        )

        rendered = autostart.build_macos_launchagent_plist(paths)

        self.assertIn("<string>com.asf.planning_comm_helper</string>", rendered)
        self.assertIn("<string>/repo/.venv/bin/python</string>", rendered)
        self.assertIn("<string>/repo</string>", rendered)
        self.assertIn("<string>/tmp/asf-planning-comm-helper.log</string>", rendered)

    def test_build_windows_paths_target_startup_folder_and_local_support_dir(self):
        repo_root = Path("C:/repo")
        with (
            mock.patch.dict(
                "os.environ",
                {
                    "APPDATA": r"C:\Users\Test\AppData\Roaming",
                    "LOCALAPPDATA": r"C:\Users\Test\AppData\Local",
                },
                clear=False,
            ),
            mock.patch("platform.system", return_value="Windows"),
        ):
            paths = autostart.build_windows_autostart_paths(repo_root)

        self.assertEqual(
            str(paths.startup_vbs_path).replace("\\", "/"),
            "C:/Users/Test/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/ASF Planning Communication Helper.vbs",
        )
        self.assertEqual(
            str(paths.runner_cmd_path).replace("\\", "/"),
            "C:/Users/Test/AppData/Local/ASF/planning_comm_helper/start-helper.cmd",
        )
        self.assertEqual(
            str(paths.log_path).replace("\\", "/"),
            "C:/Users/Test/AppData/Local/ASF/planning_comm_helper/planning-comm-helper.log",
        )
        self.assertEqual(str(paths.python_path).replace("\\", "/"), "C:/repo/.venv/Scripts/python.exe")

    def test_build_windows_runner_files_reference_hidden_startup_script(self):
        paths = autostart.WindowsAutostartPaths(
            startup_vbs_path=Path(
                r"C:\Users\Test\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\ASF Planning Communication Helper.vbs"
            ),
            runner_cmd_path=Path(r"C:\Users\Test\AppData\Local\ASF\planning_comm_helper\start-helper.cmd"),
            log_path=Path(r"C:\Users\Test\AppData\Local\ASF\planning_comm_helper\planning-comm-helper.log"),
            python_path=Path(r"C:\repo\.venv\Scripts\python.exe"),
            repo_root=Path(r"C:\repo"),
        )

        runner = autostart.build_windows_runner_cmd(paths)
        startup_vbs = autostart.build_windows_startup_vbs(paths)

        self.assertIn('cd /d "C:\\repo"', runner)
        self.assertIn(
            '"C:\\repo\\.venv\\Scripts\\python.exe" -m tools.planning_comm_helper.server',
            runner,
        )
        self.assertIn("planning-comm-helper.log", runner)
        self.assertIn('shell.Run Chr(34) & "C:\\Users\\Test\\AppData\\Local\\ASF\\planning_comm_helper\\start-helper.cmd" & Chr(34), 0, False', startup_vbs)

    def test_install_windows_autostart_writes_runner_and_vbs_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            repo_root.mkdir(parents=True, exist_ok=True)
            appdata = Path(tmpdir) / "AppData" / "Roaming"
            local_appdata = Path(tmpdir) / "AppData" / "Local"
            with mock.patch.dict(
                "os.environ",
                {
                    "APPDATA": str(appdata),
                    "LOCALAPPDATA": str(local_appdata),
                },
                clear=False,
            ):
                paths = autostart.install_windows_autostart(repo_root=repo_root)
                self.assertTrue(paths.startup_vbs_path.exists())
                self.assertTrue(paths.runner_cmd_path.exists())
                self.assertIn("tools.planning_comm_helper.server", paths.runner_cmd_path.read_text())
                self.assertIn("shell.Run", paths.startup_vbs_path.read_text())
