from django.core.management.base import BaseCommand, CommandError

from wms.models import PlanningRunStatus
from wms.planning.recipe_dataset import normalize_recipe_scenario_slug, seed_recipe_dataset


class Command(BaseCommand):
    help = "Seed a disposable recipe planning dataset for operator end-to-end testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario",
            default="phase3-s11-recipe",
            help="Scenario slug used to namespace the recipe dataset.",
        )
        parser.add_argument(
            "--solve",
            action="store_true",
            help="Prepare and solve the planning run after seeding the dataset.",
        )

    def handle(self, *args, **options):
        scenario_slug = normalize_recipe_scenario_slug(options["scenario"])
        dataset = seed_recipe_dataset(
            scenario_slug=scenario_slug,
            solve=options["solve"],
        )
        run = dataset["run"]
        version = dataset["version"]
        if options["solve"] and run.status != PlanningRunStatus.SOLVED:
            raise CommandError(
                f"Scenario {scenario_slug} seeded but did not solve successfully: {run.status}"
            )

        assignments = version.assignments.count() if version is not None else 0
        self.stdout.write(
            self.style.SUCCESS(
                f"Scenario {scenario_slug} ready: "
                f"run={run.pk} "
                f"status={run.status} "
                f"shipments={len(dataset['shipments'])} "
                f"volunteers={len(dataset['volunteers'])} "
                f"flights={len(dataset['flights'])} "
                f"assignments={assignments}"
            )
        )
