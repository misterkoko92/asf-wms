from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    Flight,
    PlanningParameterSet,
    PlanningRun,
    PlanningRunStatus,
    Shipment,
    ShipmentStatus,
    VolunteerProfile,
)


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

    def test_seed_planning_recipe_data_solve_ignores_non_recipe_weekly_data(self):
        external_contact = Contact.objects.create(
            name="External shipper",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        external_correspondent = Contact.objects.create(
            name="External correspondent",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        external_destination = Destination.objects.create(
            city="Dakar",
            iata_code="DSS",
            country="Senegal",
            correspondent_contact=external_correspondent,
        )
        Shipment.objects.create(
            reference="REAL-WEEK-001",
            status=ShipmentStatus.PACKED,
            shipper_name="External shipper",
            shipper_contact_ref=external_contact,
            recipient_name="External recipient",
            destination=external_destination,
            destination_address="Airport road",
            destination_country="Senegal",
            ready_at="2026-03-12T09:00:00+00:00",
        )
        external_user = get_user_model().objects.create_user(
            username="real-volunteer@example.com",
            email="real-volunteer@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        VolunteerProfile.objects.create(user=external_user, city="Paris")

        call_command(
            "seed_planning_recipe_data",
            "--scenario=phase3-s11-recipe",
            "--solve",
        )

        run = PlanningRun.objects.get(parameter_set__name="RECIPE phase3-s11-recipe")

        self.assertEqual(run.status, PlanningRunStatus.SOLVED)
        self.assertEqual(run.shipment_snapshots.count(), 8)
        self.assertEqual(run.volunteer_snapshots.count(), 5)
        self.assertFalse(run.shipment_snapshots.filter(shipment_reference="REAL-WEEK-001").exists())

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
