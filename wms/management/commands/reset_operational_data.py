from django.core.management.base import BaseCommand, CommandError

from wms.reset_operational_data import reset_operational_data


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
        self.stdout.write(f"Operational reset [{summary.mode}]")
        self.stdout.write("Planned deletions:")
        for label, count in summary.delete_counts_before.items():
            self.stdout.write(f"- {label}: {count}")
        self.stdout.write("Preserved models:")
        for label, count in summary.keep_counts_after.items():
            self.stdout.write(f"- {label}: {count}")
        if summary.missing_table_labels:
            self.stdout.write("Skipped missing tables:")
            for label in summary.missing_table_labels:
                self.stdout.write(f"- {label}")
