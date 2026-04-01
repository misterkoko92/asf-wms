from io import StringIO
from types import SimpleNamespace
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase


class ImportPlanningParametersCommandTests(TestCase):
    @mock.patch(
        "wms.management.commands.import_planning_parameters.import_destination_rules",
        side_effect=FileNotFoundError,
    )
    def test_import_planning_parameters_reports_missing_file(self, _import_mock):
        with self.assertRaises(CommandError) as error:
            call_command(
                "import_planning_parameters",
                "/tmp/missing.xlsx",
                name="Planning mars",
            )

        self.assertIn("File not found", str(error.exception))

    @mock.patch(
        "wms.management.commands.import_planning_parameters.import_destination_rules",
        side_effect=ValueError("Workbook invalide"),
    )
    def test_import_planning_parameters_reports_validation_error(self, _import_mock):
        with self.assertRaises(CommandError) as error:
            call_command(
                "import_planning_parameters",
                "/tmp/invalid.xlsx",
                name="Planning mars",
            )

        self.assertIn("Workbook invalide", str(error.exception))

    @mock.patch("wms.management.commands.import_planning_parameters.import_destination_rules")
    def test_import_planning_parameters_reports_success(self, import_mock):
        out = StringIO()
        import_mock.return_value = SimpleNamespace(name="Planning avril")

        call_command(
            "import_planning_parameters",
            "/tmp/planning.xlsx",
            name="Planning avril",
            stdout=out,
        )

        self.assertIn(
            "Imported planning destination rules into parameter set Planning avril.", out.getvalue()
        )
