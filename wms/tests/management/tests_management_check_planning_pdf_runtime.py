from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase


class CheckPlanningPdfRuntimeCommandTests(TestCase):
    @mock.patch(
        "wms.management.commands.check_planning_pdf_runtime.get_planning_pdf_runtime_status",
        return_value={
            "backend": "excel_desktop",
            "status": "ready",
            "available": True,
            "detail": "",
        },
    )
    def test_check_planning_pdf_runtime_returns_success_when_backend_is_ready(
        self,
        _runtime_status_mock,
    ):
        out = StringIO()

        call_command("check_planning_pdf_runtime", stdout=out)

        self.assertIn("Planning PDF runtime ready", out.getvalue())

    @mock.patch(
        "wms.management.commands.check_planning_pdf_runtime.get_planning_pdf_runtime_status",
        return_value={
            "backend": "excel_desktop",
            "status": "excel_not_installed",
            "available": False,
            "detail": "Microsoft Excel is not installed.",
        },
    )
    def test_check_planning_pdf_runtime_fails_when_backend_is_unavailable(
        self,
        _runtime_status_mock,
    ):
        with self.assertRaises(CommandError) as error:
            call_command("check_planning_pdf_runtime")

        self.assertIn("excel_not_installed", str(error.exception))
