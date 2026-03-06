from __future__ import annotations

import shutil
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from wms.document_scan_queue import (
    DOCUMENT_SCAN_BACKEND_CLAMAV,
    DOCUMENT_SCAN_BACKEND_NOOP,
    DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
    DOCUMENT_SCAN_QUEUE_SOURCE,
    _clamav_command,
    _processing_timeout_seconds,
    _scan_backend,
)
from wms.models import IntegrationDirection, IntegrationEvent, IntegrationStatus


def _non_negative(value: int | None, *, option_name: str) -> int | None:
    if value is None:
        return None
    if value < 0:
        raise CommandError(f"{option_name} doit etre >= 0.")
    return value


def _scan_queue_queryset():
    return IntegrationEvent.objects.filter(
        direction=IntegrationDirection.OUTBOUND,
        source=DOCUMENT_SCAN_QUEUE_SOURCE,
        event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
    )


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
        allow_noop = bool(options["allow_noop"])
        max_pending = _non_negative(options["max_pending"], option_name="--max-pending")
        max_failed = _non_negative(options["max_failed"], option_name="--max-failed")
        max_stale_processing = _non_negative(
            options["max_stale_processing"],
            option_name="--max-stale-processing",
        )

        backend = _scan_backend()
        clamav_command = _clamav_command()
        clamav_available = bool(shutil.which(clamav_command))
        timeout_seconds = _processing_timeout_seconds(options["processing_timeout_seconds"])

        queue_queryset = _scan_queue_queryset()
        counts = {
            IntegrationStatus.PENDING: queue_queryset.filter(
                status=IntegrationStatus.PENDING
            ).count(),
            IntegrationStatus.PROCESSING: queue_queryset.filter(
                status=IntegrationStatus.PROCESSING
            ).count(),
            IntegrationStatus.FAILED: queue_queryset.filter(
                status=IntegrationStatus.FAILED
            ).count(),
            IntegrationStatus.PROCESSED: queue_queryset.filter(
                status=IntegrationStatus.PROCESSED
            ).count(),
        }
        stale_cutoff = timezone.now() - timedelta(seconds=timeout_seconds)
        stale_processing = queue_queryset.filter(
            status=IntegrationStatus.PROCESSING,
            processed_at__lte=stale_cutoff,
        ).count()

        self.stdout.write(
            "Document scan runtime snapshot: "
            f"backend={backend}, clamav_command={clamav_command}, "
            f"clamav_available={'yes' if clamav_available else 'no'}, "
            f"pending={counts[IntegrationStatus.PENDING]}, "
            f"processing={counts[IntegrationStatus.PROCESSING]}, "
            f"failed={counts[IntegrationStatus.FAILED]}, "
            f"processed={counts[IntegrationStatus.PROCESSED]}, "
            f"stale_processing={stale_processing}, "
            f"stale_timeout_seconds={timeout_seconds}."
        )

        issues = []
        if backend == DOCUMENT_SCAN_BACKEND_NOOP and not allow_noop:
            issues.append(
                "DOCUMENT_SCAN_BACKEND=noop detecte sans --allow-noop (interdit en production)."
            )
        if backend == DOCUMENT_SCAN_BACKEND_CLAMAV and not clamav_available:
            issues.append(f"Commande ClamAV introuvable: '{clamav_command}'.")

        if max_pending is not None and counts[IntegrationStatus.PENDING] > max_pending:
            issues.append(
                f"pending={counts[IntegrationStatus.PENDING]} depasse --max-pending={max_pending}."
            )
        if max_failed is not None and counts[IntegrationStatus.FAILED] > max_failed:
            issues.append(
                f"failed={counts[IntegrationStatus.FAILED]} depasse --max-failed={max_failed}."
            )
        if max_stale_processing is not None and stale_processing > max_stale_processing:
            issues.append(
                "stale_processing="
                f"{stale_processing} depasse --max-stale-processing={max_stale_processing}."
            )

        if issues:
            raise CommandError("Runtime check scan documentaire en echec: " + " ".join(issues))

        self.stdout.write(self.style.SUCCESS("Runtime check scan documentaire: OK."))
