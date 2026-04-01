from datetime import date

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Rafraîchit les snapshots et escalades de pilotage ops."

    def add_arguments(self, parser):
        parser.add_argument(
            "--snapshot-date",
            dest="snapshot_date",
            default=None,
            help="Date de capture au format YYYY-MM-DD. Defaut: aujourd'hui.",
        )

    def handle(self, *args, **options):
        snapshot_date_raw = options.get("snapshot_date")
        if snapshot_date_raw:
            try:
                snapshot_date = date.fromisoformat(str(snapshot_date_raw))
            except ValueError as exc:
                raise CommandError("snapshot-date doit etre au format YYYY-MM-DD.") from exc
        else:
            snapshot_date = timezone.localdate()

        call_command(
            "capture_ops_pilotage_snapshot",
            snapshot_date=snapshot_date.isoformat(),
            stdout=self.stdout,
        )
        call_command("evaluate_ops_escalations", stdout=self.stdout)
        self.stdout.write(
            self.style.SUCCESS(f"Refreshed ops pilotage for {snapshot_date.isoformat()}.")
        )
