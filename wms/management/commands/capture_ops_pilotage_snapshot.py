from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from wms.ops_pilotage_snapshots import capture_ops_pilotage_snapshots


class Command(BaseCommand):
    help = "Capture les snapshots quotidiens de pilotage ops."

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
        captured_count = capture_ops_pilotage_snapshots(snapshot_date=snapshot_date)
        self.stdout.write(
            self.style.SUCCESS(
                f"Captured {captured_count} ops pilotage snapshots for {snapshot_date.isoformat()}."
            )
        )
