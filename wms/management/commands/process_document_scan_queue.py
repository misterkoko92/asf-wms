from django.core.management.base import BaseCommand

from wms.jobs.document_scan import run_document_scan_queue_job


class Command(BaseCommand):
    help = "Process pending document scan events from the antivirus queue."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of queued document scans to process.",
        )
        parser.add_argument(
            "--processing-timeout-seconds",
            type=int,
            default=None,
            help="Override timeout (seconds) to reclaim stale processing events.",
        )
        parser.add_argument(
            "--include-failed",
            action="store_true",
            help="Retry events currently in failed status.",
        )

    def handle(self, *args, **options):
        result = run_document_scan_queue_job(
            limit=options["limit"],
            include_failed=options["include_failed"],
            processing_timeout_seconds=options["processing_timeout_seconds"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Document scan queue processed: "
                f"selected={result['selected']}, "
                f"processed={result['processed']}, "
                f"infected={result['infected']}, "
                f"failed={result['failed']}."
            )
        )
