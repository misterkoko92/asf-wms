from django.core.management.base import BaseCommand

from wms.print_pack_sync import process_print_artifact_queue


class Command(BaseCommand):
    help = "Process generated print artifact queue and sync PDFs to OneDrive."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Maximum number of artifacts to process.",
        )
        parser.add_argument(
            "--include-failed",
            action="store_true",
            help="Retry artifacts already marked as sync_failed.",
        )
        parser.add_argument(
            "--max-attempts",
            type=int,
            default=None,
            help="Maximum sync attempts before artifact is marked sync_failed.",
        )

    def handle(self, *args, **options):
        result = process_print_artifact_queue(
            limit=options["limit"],
            include_failed=options["include_failed"],
            max_attempts=options["max_attempts"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Print artifact queue processed: "
                f"selected={result['selected']}, "
                f"processed={result['processed']}, "
                f"failed={result['failed']}, "
                f"retried={result['retried']}."
            )
        )
