from django.core.management.base import BaseCommand

from wms.emailing import process_email_queue


class Command(BaseCommand):
    help = "Process pending outbound email events from IntegrationEvent queue."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of queued emails to process.",
        )
        parser.add_argument(
            "--max-attempts",
            type=int,
            default=None,
            help="Override max attempts before moving an email event to failed.",
        )
        parser.add_argument(
            "--retry-base-seconds",
            type=int,
            default=None,
            help="Override retry base delay (seconds) for exponential backoff.",
        )
        parser.add_argument(
            "--retry-max-seconds",
            type=int,
            default=None,
            help="Override retry max delay (seconds) for exponential backoff.",
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
        result = process_email_queue(
            limit=options["limit"],
            include_failed=options["include_failed"],
            max_attempts=options["max_attempts"],
            retry_base_seconds=options["retry_base_seconds"],
            retry_max_seconds=options["retry_max_seconds"],
            processing_timeout_seconds=options["processing_timeout_seconds"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Email queue processed: "
                f"selected={result['selected']}, "
                f"processed={result['processed']}, "
                f"failed={result['failed']}, "
                f"retried={result['retried']}, "
                f"deferred={result['deferred']}."
            )
        )
