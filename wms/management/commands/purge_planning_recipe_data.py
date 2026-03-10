from django.core.management.base import BaseCommand

from wms.planning.recipe_dataset import normalize_recipe_scenario_slug, purge_recipe_dataset


class Command(BaseCommand):
    help = "Purge a disposable recipe planning dataset."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario",
            default="phase3-s11-recipe",
            help="Scenario slug used to namespace the recipe dataset.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Delete the recipe dataset instead of running in dry-run mode.",
        )

    def handle(self, *args, **options):
        scenario_slug = normalize_recipe_scenario_slug(options["scenario"])
        result = purge_recipe_dataset(
            scenario_slug=scenario_slug,
            dry_run=not options["yes"],
        )
        counts = (
            ", ".join(f"{key}={value}" for key, value in sorted(result["counts"].items()) if value)
            or "nothing"
        )
        if result["dry_run"]:
            self.stdout.write(
                self.style.WARNING(f"Dry-run for {scenario_slug}: would delete {counts}")
            )
            return
        self.stdout.write(self.style.SUCCESS(f"Purged {scenario_slug}: deleted {counts}"))
