from django.core.management.base import BaseCommand, CommandError

from wms.jobs.runtime_checks import run_document_scan_runtime_check
from wms.models import IntegrationStatus


class Command(BaseCommand):
    help = (
        "Valide la readiness runtime de la queue de scan documentaire "
        "(backend, ClamAV, backlog, stale processing)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-noop",
            action="store_true",
            help=(
                "Autorise DOCUMENT_SCAN_BACKEND=noop (utile uniquement en dev/tests). "
                "En production, ce flag ne doit pas etre utilise."
            ),
        )
        parser.add_argument(
            "--max-pending",
            type=int,
            default=None,
            help="Seuil max d'evenements pending autorises (optionnel).",
        )
        parser.add_argument(
            "--max-failed",
            type=int,
            default=0,
            help="Seuil max d'evenements failed autorises (defaut: 0).",
        )
        parser.add_argument(
            "--max-stale-processing",
            type=int,
            default=0,
            help="Seuil max d'evenements processing stale autorises (defaut: 0).",
        )
        parser.add_argument(
            "--processing-timeout-seconds",
            type=int,
            default=None,
            help=(
                "Timeout (s) pour definir un processing stale. "
                "Si absent, utilise DOCUMENT_SCAN_QUEUE_PROCESSING_TIMEOUT_SECONDS."
            ),
        )

    def handle(self, *args, **options):
        try:
            snapshot = run_document_scan_runtime_check(
                allow_noop=bool(options["allow_noop"]),
                max_pending=options["max_pending"],
                max_failed=options["max_failed"],
                max_stale_processing=options["max_stale_processing"],
                processing_timeout_seconds=options["processing_timeout_seconds"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            "Document scan runtime snapshot: "
            f"backend={snapshot['backend']}, clamav_command={snapshot['clamav_command']}, "
            f"clamav_available={'yes' if snapshot['clamav_available'] else 'no'}, "
            f"pending={snapshot['counts'][IntegrationStatus.PENDING]}, "
            f"processing={snapshot['counts'][IntegrationStatus.PROCESSING]}, "
            f"failed={snapshot['counts'][IntegrationStatus.FAILED]}, "
            f"processed={snapshot['counts'][IntegrationStatus.PROCESSED]}, "
            f"stale_processing={snapshot['stale_processing']}, "
            f"stale_timeout_seconds={snapshot['timeout_seconds']}."
        )

        issues = snapshot.get("issues", [])
        if issues:
            raise CommandError("Runtime check scan documentaire en echec: " + " ".join(issues))

        self.stdout.write(self.style.SUCCESS("Runtime check scan documentaire: OK."))
