import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from wms.planning.recipe_export import build_planning_recipe_export


class Command(BaseCommand):
    help = "Export a limited planning recipe dataset for a target week."

    def add_arguments(self, parser):
        parser.add_argument("--week-start", required=True)
        parser.add_argument("--week-end", required=True)
        parser.add_argument("--output", required=True)
        parser.add_argument("--parameter-set-id", type=int)
        parser.add_argument("--parameter-set-name")
        parser.add_argument(
            "--include-flight-batches",
            action="store_true",
            default=False,
        )
        parser.add_argument(
            "--no-anonymize",
            action="store_true",
            default=False,
        )

    def handle(self, *args, **options):
        week_start = parse_date(options["week_start"])
        week_end = parse_date(options["week_end"])
        if week_start is None:
            raise CommandError("Invalid --week-start date.")
        if week_end is None:
            raise CommandError("Invalid --week-end date.")
        if week_end < week_start:
            raise CommandError("--week-end must be after or equal to --week-start.")

        export = build_planning_recipe_export(
            week_start=week_start,
            week_end=week_end,
            parameter_set_id=options.get("parameter_set_id"),
            parameter_set_name=options.get("parameter_set_name"),
            include_flight_batches=options["include_flight_batches"],
            anonymize=not options["no_anonymize"],
        )
        output_path = Path(options["output"]).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(export.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Wrote planning recipe export to "
                f"{output_path} "
                f"(shipments={export.summary['shipments']}, "
                f"flights={export.summary['flights']}, "
                f"volunteers={export.summary['volunteers']})"
            )
        )
