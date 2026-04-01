import importlib
import subprocess
from unittest import TestCase, mock

from tools.planning_comm_helper import excel_runtime


class PlanningCommunicationHelperExcelRuntimeTests(TestCase):
    @mock.patch("tools.planning_comm_helper.excel_runtime.subprocess.run")
    @mock.patch("tools.planning_comm_helper.excel_runtime.shutil.which", return_value="/usr/bin/osascript")
    @mock.patch("tools.planning_comm_helper.excel_runtime.platform.system", return_value="Darwin")
    def test_excel_runtime_ready_on_macos_when_excel_app_is_visible(
        self,
        _platform_mock,
        _which_mock,
        subprocess_run_mock,
    ):
        subprocess_run_mock.return_value = subprocess.CompletedProcess(
            args=["osascript", "-e", 'id of app "Microsoft Excel"'],
            returncode=0,
            stdout="com.microsoft.Excel\n",
            stderr="",
        )

        status = excel_runtime.get_excel_runtime_status()

        self.assertEqual(status["backend"], "excel_desktop")
        self.assertEqual(status["status"], "ready")
        self.assertTrue(status["available"])
        self.assertEqual(status["detail"], "")

    @mock.patch("tools.planning_comm_helper.excel_runtime.subprocess.run")
    @mock.patch("tools.planning_comm_helper.excel_runtime.shutil.which", return_value="/usr/bin/osascript")
    @mock.patch("tools.planning_comm_helper.excel_runtime.platform.system", return_value="Darwin")
    def test_excel_runtime_returns_excel_not_installed_code(
        self,
        _platform_mock,
        _which_mock,
        subprocess_run_mock,
    ):
        subprocess_run_mock.return_value = subprocess.CompletedProcess(
            args=["osascript", "-e", 'id of app "Microsoft Excel"'],
            returncode=1,
            stdout="",
            stderr="Application isn’t running.",
        )

        status = excel_runtime.get_excel_runtime_status()

        self.assertEqual(status["backend"], "excel_desktop")
        self.assertEqual(status["status"], "excel_not_installed")
        self.assertFalse(status["available"])
        self.assertIn("Microsoft Excel", status["detail"])

    @mock.patch("tools.planning_comm_helper.excel_runtime.platform.system", return_value="Linux")
    def test_excel_runtime_returns_platform_unsupported_on_linux(self, _platform_mock):
        status = excel_runtime.get_excel_runtime_status()

        self.assertEqual(status["backend"], "excel_desktop")
        self.assertEqual(status["status"], "platform_unsupported")
        self.assertFalse(status["available"])

    @mock.patch(
        "tools.planning_comm_helper.excel_runtime.importlib.import_module",
        side_effect=ImportError("missing win32com"),
    )
    @mock.patch("tools.planning_comm_helper.excel_runtime.platform.system", return_value="Windows")
    def test_excel_runtime_returns_automation_unavailable_on_windows_when_com_modules_missing(
        self,
        _platform_mock,
        _import_module_mock,
    ):
        status = excel_runtime.get_excel_runtime_status()

        self.assertEqual(status["backend"], "excel_desktop")
        self.assertEqual(status["status"], "excel_automation_unavailable")
        self.assertFalse(status["available"])
        self.assertIn("Windows", status["detail"])
