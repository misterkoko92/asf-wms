from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from wms.models import Flight, PlanningParameterSet, PlanningRun, PlanningRunStatus, Shipment


class PlanningRecipeDataCommandTests(TestCase):
    def test_recipe_scenarios_are_isolated_by_namespace(self):
        call_command("seed_planning_recipe_data", "--scenario=phase3-s11-recipe")
        call_command("seed_planning_recipe_data", "--scenario=phase3-s12-recipe")

        self.assertTrue(
            PlanningParameterSet.objects.filter(name="RECIPE phase3-s11-recipe").exists()
        )
        self.assertTrue(
            PlanningParameterSet.objects.filter(name="RECIPE phase3-s12-recipe").exists()
        )
        self.assertEqual(
            Shipment.objects.filter(reference__startswith="RECIPE-PHASE3-S11").count(),
            8,
        )
        self.assertEqual(
            Shipment.objects.filter(reference__startswith="RECIPE-PHASE3-S12").count(),
            8,
        )

        call_command(
            "purge_planning_recipe_data",
            "--scenario=phase3-s11-recipe",
            "--yes",
        )

        self.assertFalse(
            PlanningParameterSet.objects.filter(name="RECIPE phase3-s11-recipe").exists()
        )
        self.assertTrue(
            PlanningParameterSet.objects.filter(name="RECIPE phase3-s12-recipe").exists()
        )
        self.assertEqual(
            Shipment.objects.filter(reference__startswith="RECIPE-PHASE3-S12").count(),
            8,
        )

    def test_seed_planning_recipe_data_creates_expected_volumes(self):
        output = StringIO()

        call_command(
            "seed_planning_recipe_data",
            "--scenario=phase3-s11-recipe",
            stdout=output,
        )

        self.assertTrue(
            PlanningParameterSet.objects.filter(name="RECIPE phase3-s11-recipe").exists()
        )
        self.assertEqual(
            Flight.objects.filter(
                batch__source="recipe", batch__file_name="phase3-s11-recipe"
            ).count(),
            6,
        )
        self.assertEqual(
            Shipment.objects.filter(reference__startswith="RECIPE-PHASE3-S11").count(),
            8,
        )
        self.assertIn("phase3-s11-recipe", output.getvalue())

    def test_seed_planning_recipe_data_can_solve_and_cover_required_business_cases(self):
        output = StringIO()

        call_command(
            "seed_planning_recipe_data",
            "--scenario=phase3-s11-recipe",
            "--solve",
            stdout=output,
        )

        run = PlanningRun.objects.get(parameter_set__name="RECIPE phase3-s11-recipe")
        version = run.versions.get(number=1)

        self.assertEqual(run.status, PlanningRunStatus.SOLVED)
        self.assertTrue(version.assignments.exists())
        self.assertFalse(
            version.assignments.filter(flight_snapshot__flight_number="AF945").exists()
        )
        self.assertEqual(
            set(
                version.assignments.filter(flight_snapshot__flight_number="AF982").values_list(
                    "shipment_snapshot__destination_iata",
                    flat=True,
                )
            ),
            {"NSI"},
        )
        self.assertGreaterEqual(len(run.solver_result["unassigned_shipment_snapshot_ids"]), 1)
        self.assertGreaterEqual(
            run.shipment_snapshots.exclude(assignments__version=version).count(),
            1,
        )
        self.assertGreaterEqual(
            run.volunteer_snapshots.filter(assignments__flight_snapshot__flight_number="AF704")
            .values("pk")
            .distinct()
            .count(),
            1,
        )
        self.assertGreaterEqual(
            next(
                item["benevole_compat_count"]
                for item in run.solver_result["vols_diagnostics"]
                if item["flight_number"] == "AF704"
            ),
            2,
        )
        self.assertEqual(
            set(
                version.assignments.filter(flight_snapshot__flight_number="AF704").values_list(
                    "volunteer_snapshot__volunteer_label",
                    flat=True,
                )
            ),
            {"Abel Long"},
        )
        self.assertTrue(
            any(
                item["flight_number"] in {"AF968", "AF969"}
                and item["shipment_compat_count"] > 0
                and item["benevole_compat_count"] > 0
                and not item["used"]
                for item in run.solver_result["vols_diagnostics"]
            )
        )
        self.assertIn("solved", output.getvalue().lower())

    def test_purge_planning_recipe_data_dry_run_only_reports_counts(self):
        output = StringIO()
        call_command("seed_planning_recipe_data", "--scenario=phase3-s11-recipe")

        call_command(
            "purge_planning_recipe_data",
            "--scenario=phase3-s11-recipe",
            stdout=output,
        )

        self.assertIn("dry-run", output.getvalue().lower())
        self.assertTrue(
            PlanningParameterSet.objects.filter(name="RECIPE phase3-s11-recipe").exists()
        )

    def test_purge_planning_recipe_data_deletes_only_recipe_namespace(self):
        call_command("seed_planning_recipe_data", "--scenario=phase3-s11-recipe")
        keep = PlanningParameterSet.objects.create(name="Keep me")

        call_command(
            "purge_planning_recipe_data",
            "--scenario=phase3-s11-recipe",
            "--yes",
        )

        self.assertFalse(
            PlanningParameterSet.objects.filter(name="RECIPE phase3-s11-recipe").exists()
        )
        self.assertTrue(PlanningParameterSet.objects.filter(pk=keep.pk).exists())
        self.assertEqual(
            Shipment.objects.filter(reference__startswith="RECIPE-PHASE3-S11").count(),
            0,
        )
        self.assertEqual(
            Flight.objects.filter(
                batch__source="recipe", batch__file_name="phase3-s11-recipe"
            ).count(),
            0,
        )
