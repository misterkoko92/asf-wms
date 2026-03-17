from django.core.management.base import BaseCommand, CommandError

from wms.reset_operational_data import render_reset_summary, reset_operational_data


class Command(BaseCommand):
    help = "Reset operational WMS data while preserving stable reference and configuration rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the reset scope without deleting any rows.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the reset for real.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        apply = bool(options.get("apply"))
        if dry_run and apply:
            raise CommandError("Choose either --dry-run or --apply, not both.")

        summary = reset_operational_data(apply=apply)
        for line in render_reset_summary(summary):
            self.stdout.write(line)
