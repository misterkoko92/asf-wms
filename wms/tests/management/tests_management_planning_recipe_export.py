import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase


class PlanningRecipeExportCommandTests(TestCase):
    def test_planning_recipe_export_rejects_invalid_week_start(self):
        with self.assertRaises(CommandError) as error:
            call_command(
                "planning_recipe_export",
                week_start="bad-date",
                week_end="2026-04-06",
                output="/tmp/planning-recipe.json",
            )

        self.assertIn("Invalid --week-start date.", str(error.exception))

    def test_planning_recipe_export_rejects_invalid_week_end(self):
        with self.assertRaises(CommandError) as error:
            call_command(
                "planning_recipe_export",
                week_start="2026-04-01",
                week_end="bad-date",
                output="/tmp/planning-recipe.json",
            )

        self.assertIn("Invalid --week-end date.", str(error.exception))

    def test_planning_recipe_export_rejects_inverted_date_range(self):
        with self.assertRaises(CommandError) as error:
            call_command(
                "planning_recipe_export",
                week_start="2026-04-07",
                week_end="2026-04-06",
                output="/tmp/planning-recipe.json",
            )

        self.assertIn("--week-end must be after or equal to --week-start.", str(error.exception))

    @mock.patch("wms.management.commands.planning_recipe_export.build_planning_recipe_export")
    def test_planning_recipe_export_writes_file_and_reports_success(self, export_builder_mock):
        out = StringIO()
        export_builder_mock.return_value = mock.Mock(
            to_dict=mock.Mock(return_value={"summary": {"shipments": 2}}),
            summary={"shipments": 2, "flights": 3, "volunteers": 4},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "planning-recipe.json"
            call_command(
                "planning_recipe_export",
                week_start="2026-04-01",
                week_end="2026-04-07",
                output=str(output_path),
                stdout=out,
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(
                json.loads(output_path.read_text(encoding="utf-8")), {"summary": {"shipments": 2}}
            )
        self.assertIn("Wrote planning recipe export to", out.getvalue())
