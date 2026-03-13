from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.planning_comm_helper import autostart


class PlanningCommunicationHelperAutostartTests(unittest.TestCase):
    def test_build_macos_paths_target_stable_app_bundle(self):
        with mock.patch("pathlib.Path.home", return_value=Path("/Users/test")):
            paths = autostart.build_macos_autostart_paths(Path("/repo"))

        self.assertEqual(
            paths.launcher_app_path,
            Path("/Users/test/Applications/ASF Planning Communication Helper.app"),
        )
        self.assertEqual(
            paths.launcher_executable_path,
            Path(
                "/Users/test/Applications/ASF Planning Communication Helper.app/Contents/MacOS/ASF Planning Communication Helper"
            ),
        )
        self.assertEqual(
            paths.launcher_info_plist_path,
            Path(
                "/Users/test/Applications/ASF Planning Communication Helper.app/Contents/Info.plist"
            ),
        )
        self.assertEqual(paths.python_path, Path("/repo/.venv/bin/python"))

    def test_build_macos_launchagent_plist_uses_stable_app_executable(self):
        paths = autostart.MacAutostartPaths(
            plist_path=Path("/Users/test/Library/LaunchAgents/com.asf.planning_comm_helper.plist"),
            log_path=Path("/tmp/asf-planning-comm-helper.log"),
            launcher_app_path=Path("/Users/test/Applications/ASF Planning Communication Helper.app"),
            launcher_executable_path=Path(
                "/Users/test/Applications/ASF Planning Communication Helper.app/Contents/MacOS/ASF Planning Communication Helper"
            ),
            launcher_info_plist_path=Path(
                "/Users/test/Applications/ASF Planning Communication Helper.app/Contents/Info.plist"
            ),
            python_path=Path("/repo/.venv/bin/python"),
            repo_root=Path("/repo"),
        )

        rendered = autostart.build_macos_launchagent_plist(paths)

        self.assertIn("<string>com.asf.planning_comm_helper</string>", rendered)
        self.assertIn(
            "<string>/Users/test/Applications/ASF Planning Communication Helper.app/Contents/MacOS/ASF Planning Communication Helper</string>",
            rendered,
        )
        self.assertNotIn("<string>/repo/.venv/bin/python</string>", rendered)
        self.assertIn("<string>/tmp/asf-planning-comm-helper.log</string>", rendered)

    def test_install_macos_autostart_writes_app_bundle_and_launchagent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            repo_root.mkdir(parents=True, exist_ok=True)
            with (
                mock.patch("pathlib.Path.home", return_value=Path(tmpdir) / "home"),
                mock.patch("subprocess.run") as subprocess_run,
            ):
                paths = autostart.install_macos_autostart(repo_root=repo_root, uid=501)

            self.assertTrue(paths.plist_path.exists())
            self.assertTrue(paths.launcher_info_plist_path.exists())
            self.assertTrue(paths.launcher_executable_path.exists())
            self.assertIn("CFBundleIdentifier", paths.launcher_info_plist_path.read_text())
            self.assertIn(
                str(repo_root / ".venv" / "bin" / "python"),
                paths.launcher_executable_path.read_text(),
            )
            self.assertTrue(paths.launcher_executable_path.stat().st_mode & 0o111)
            subprocess_run.assert_any_call(
                ["launchctl", "bootstrap", "gui/501", str(paths.plist_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            subprocess_run.assert_any_call(
                ["launchctl", "kickstart", "-k", "gui/501/com.asf.planning_comm_helper"],
                check=True,
            )

    def test_install_macos_autostart_reloads_existing_launch_agent_before_kickstart(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir) / "repo"
            repo_root.mkdir(parents=True, exist_ok=True)
            with (
                mock.patch("pathlib.Path.home", return_value=Path(tmpdir) / "home"),
                mock.patch("subprocess.run") as subprocess_run,
            ):
                paths = autostart.install_macos_autostart(repo_root=repo_root, uid=501)

        self.assertEqual(
            subprocess_run.call_args_list[:3],
            [
                mock.call(
                    ["launchctl", "bootout", "gui/501", str(paths.plist_path)],
                    check=False,
                    capture_output=True,
                    text=True,
                ),
                mock.call(
                    ["launchctl", "bootstrap", "gui/501", str(paths.plist_path)],
                    check=False,
                    capture_output=True,
                    text=True,
                ),
                mock.call(
                    ["launchctl", "kickstart", "-k", "gui/501/com.asf.planning_comm_helper"],
                    check=True,
                ),
            ],
        )

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
