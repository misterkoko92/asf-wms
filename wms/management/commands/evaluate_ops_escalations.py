from django.core.management.base import BaseCommand
from django.utils import timezone

from wms.ops_escalations import sync_ops_escalations


class Command(BaseCommand):
    help = "Évalue et persiste les escalades locales de pilotage."

    def handle(self, *args, **options):
        summary = sync_ops_escalations(now=timezone.now())
        self.stdout.write(
            self.style.SUCCESS(
                "Evaluated ops escalations: "
                f"open={summary['open_count']}, resolved={summary['resolved_count']}."
            )
        )
