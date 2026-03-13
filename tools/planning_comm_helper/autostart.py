from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

LAUNCH_AGENT_LABEL = "com.asf.planning_comm_helper"
MACOS_APP_BUNDLE_NAME = "ASF Planning Communication Helper.app"
MACOS_APP_EXECUTABLE_NAME = "ASF Planning Communication Helper"
WINDOWS_STARTUP_VBS = "ASF Planning Communication Helper.vbs"
WINDOWS_RUNNER_CMD = "start-helper.cmd"
WINDOWS_SUPPORT_DIRNAME = "planning_comm_helper"


@dataclass(frozen=True)
class MacAutostartPaths:
    plist_path: Path
    log_path: Path
    launcher_app_path: Path
    launcher_executable_path: Path
    launcher_info_plist_path: Path
    python_path: Path
    repo_root: Path


@dataclass(frozen=True)
class WindowsAutostartPaths:
    startup_vbs_path: Path
    runner_cmd_path: Path
    log_path: Path
    python_path: Path
    repo_root: Path


def repo_root_from_file(file_path: str | Path = __file__) -> Path:
    return Path(file_path).resolve().parents[2]


def _windows_appdata() -> Path:
    value = os.environ.get("APPDATA")
    if value:
        return Path(value)
    return Path.home() / "AppData" / "Roaming"


def _windows_local_appdata() -> Path:
    value = os.environ.get("LOCALAPPDATA")
    if value:
        return Path(value)
    return Path.home() / "AppData" / "Local"


def build_macos_autostart_paths(repo_root: Path | None = None) -> MacAutostartPaths:
    repo_root = repo_root or repo_root_from_file()
    launcher_app_path = Path.home() / "Applications" / MACOS_APP_BUNDLE_NAME
    launcher_contents_path = launcher_app_path / "Contents"
    return MacAutostartPaths(
        plist_path=Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist",
        log_path=Path("/tmp/asf-planning-comm-helper.log"),
        launcher_app_path=launcher_app_path,
        launcher_executable_path=launcher_contents_path / "MacOS" / MACOS_APP_EXECUTABLE_NAME,
        launcher_info_plist_path=launcher_contents_path / "Info.plist",
        python_path=repo_root / ".venv" / "bin" / "python",
        repo_root=repo_root,
    )


def build_windows_autostart_paths(repo_root: Path | None = None) -> WindowsAutostartPaths:
    repo_root = repo_root or repo_root_from_file()
    startup_dir = (
        _windows_appdata()
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )
    support_dir = _windows_local_appdata() / "ASF" / WINDOWS_SUPPORT_DIRNAME
    return WindowsAutostartPaths(
        startup_vbs_path=startup_dir / WINDOWS_STARTUP_VBS,
        runner_cmd_path=support_dir / WINDOWS_RUNNER_CMD,
        log_path=support_dir / "planning-comm-helper.log",
        python_path=repo_root / ".venv" / "Scripts" / "python.exe",
        repo_root=repo_root,
    )


def build_macos_launchagent_plist(paths: MacAutostartPaths) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{LAUNCH_AGENT_LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>{paths.launcher_executable_path}</string>
  </array>

  <key>WorkingDirectory</key>
  <string>{paths.repo_root}</string>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>{paths.log_path}</string>

  <key>StandardErrorPath</key>
  <string>{paths.log_path}</string>
</dict>
</plist>
"""


def build_macos_app_info_plist(paths: MacAutostartPaths) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDisplayName</key>
  <string>ASF Planning Communication Helper</string>
  <key>CFBundleExecutable</key>
  <string>{MACOS_APP_EXECUTABLE_NAME}</string>
  <key>CFBundleIdentifier</key>
  <string>{LAUNCH_AGENT_LABEL}</string>
  <key>CFBundleName</key>
  <string>ASF Planning Communication Helper</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSUIElement</key>
  <true/>
</dict>
</plist>
"""


def build_macos_app_launcher(paths: MacAutostartPaths) -> str:
    return f"""#!/bin/zsh
set -e
cd "{paths.repo_root}"
exec "{paths.python_path}" -m tools.planning_comm_helper.server >> "{paths.log_path}" 2>&1
"""


def build_windows_runner_cmd(paths: WindowsAutostartPaths) -> str:
    return f"""@echo off
cd /d "{paths.repo_root}"
"{paths.python_path}" -m tools.planning_comm_helper.server >> "{paths.log_path}" 2>&1
"""


def _vbs_escape(value: str | Path) -> str:
    return str(value).replace('"', '""')


def build_windows_startup_vbs(paths: WindowsAutostartPaths) -> str:
    return f"""Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "{_vbs_escape(paths.repo_root)}"
shell.Run Chr(34) & "{_vbs_escape(paths.runner_cmd_path)}" & Chr(34), 0, False
"""


def install_macos_autostart(
    *,
    repo_root: Path | None = None,
    uid: int | None = None,
) -> MacAutostartPaths:
    paths = build_macos_autostart_paths(repo_root)
    paths.plist_path.parent.mkdir(parents=True, exist_ok=True)
    paths.launcher_info_plist_path.parent.mkdir(parents=True, exist_ok=True)
    paths.launcher_executable_path.parent.mkdir(parents=True, exist_ok=True)
    paths.launcher_info_plist_path.write_text(build_macos_app_info_plist(paths), encoding="utf-8")
    paths.launcher_executable_path.write_text(build_macos_app_launcher(paths), encoding="utf-8")
    paths.launcher_executable_path.chmod(0o755)
    paths.plist_path.write_text(build_macos_launchagent_plist(paths), encoding="utf-8")
    subprocess.run(
        ["launchctl", "bootout", f"gui/{uid or os.getuid()}", str(paths.plist_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid or os.getuid()}", str(paths.plist_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["launchctl", "kickstart", "-k", f"gui/{uid or os.getuid()}/{LAUNCH_AGENT_LABEL}"],
        check=True,
    )
    return paths


def uninstall_macos_autostart(*, uid: int | None = None) -> MacAutostartPaths:
    paths = build_macos_autostart_paths()
    subprocess.run(
        ["launchctl", "bootout", f"gui/{uid or os.getuid()}", str(paths.plist_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if paths.plist_path.exists():
        paths.plist_path.unlink()
    if paths.launcher_app_path.exists():
        shutil.rmtree(paths.launcher_app_path, ignore_errors=True)
    return paths


def install_windows_autostart(*, repo_root: Path | None = None) -> WindowsAutostartPaths:
    paths = build_windows_autostart_paths(repo_root)
    paths.startup_vbs_path.parent.mkdir(parents=True, exist_ok=True)
    paths.runner_cmd_path.parent.mkdir(parents=True, exist_ok=True)
    paths.runner_cmd_path.write_text(build_windows_runner_cmd(paths), encoding="utf-8")
    paths.startup_vbs_path.write_text(build_windows_startup_vbs(paths), encoding="utf-8")
    return paths


def uninstall_windows_autostart() -> WindowsAutostartPaths:
    paths = build_windows_autostart_paths()
    if paths.startup_vbs_path.exists():
        paths.startup_vbs_path.unlink()
    if paths.runner_cmd_path.exists():
        paths.runner_cmd_path.unlink()
    return paths


def install_autostart() -> Path:
    system = platform.system()
    if system == "Darwin":
        return install_macos_autostart().plist_path
    if system == "Windows":
        return install_windows_autostart().startup_vbs_path
    raise RuntimeError("Autostart is only supported on macOS and Windows.")


def uninstall_autostart() -> Path:
    system = platform.system()
    if system == "Darwin":
        return uninstall_macos_autostart().plist_path
    if system == "Windows":
        return uninstall_windows_autostart().startup_vbs_path
    raise RuntimeError("Autostart is only supported on macOS and Windows.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install planning helper autostart.")
    parser.add_argument("action", choices=["install", "uninstall"])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.action == "install":
        installed_path = install_autostart()
        print(installed_path)
        return 0
    removed_path = uninstall_autostart()
    print(removed_path)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
