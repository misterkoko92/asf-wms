from __future__ import annotations

from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from wms.document_scan_queue import (
    DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
    DOCUMENT_SCAN_QUEUE_SOURCE,
)
from wms.models import IntegrationDirection, IntegrationEvent, IntegrationStatus


class CheckDocumentScanRuntimeCommandTests(TestCase):
    def _create_scan_event(self, *, status: str, processed_at=None):
        return IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source=DOCUMENT_SCAN_QUEUE_SOURCE,
            target="antivirus",
            event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
            payload={"model": "wms.AccountDocument", "pk": 1},
            status=status,
            processed_at=processed_at,
        )

    @override_settings(
        DOCUMENT_SCAN_BACKEND="clamav",
        DOCUMENT_SCAN_CLAMAV_COMMAND="clamscan",
    )
    @mock.patch(
        "wms.jobs.runtime_checks.shutil.which",
        return_value="/usr/bin/clamscan",
    )
    def test_command_passes_with_clamav_and_healthy_queue(self, _which_mock):
        out = StringIO()

        call_command(
            "check_document_scan_runtime",
            "--max-failed=0",
            "--max-stale-processing=0",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("backend=clamav", output)
        self.assertIn("Runtime check scan documentaire: OK.", output)

    @override_settings(
        DOCUMENT_SCAN_BACKEND="clamav",
        DOCUMENT_SCAN_CLAMAV_COMMAND="clamscan",
    )
    @mock.patch(
        "wms.jobs.runtime_checks.shutil.which",
        return_value=None,
    )
    def test_command_fails_when_clamav_command_is_unavailable(self, _which_mock):
        with self.assertRaisesMessage(CommandError, "Commande ClamAV introuvable"):
            call_command("check_document_scan_runtime")

    @override_settings(DOCUMENT_SCAN_BACKEND="noop")
    @mock.patch(
        "wms.jobs.runtime_checks.shutil.which",
        return_value=None,
    )
    def test_command_rejects_noop_backend_without_allow_noop(self, _which_mock):
        with self.assertRaisesMessage(CommandError, "DOCUMENT_SCAN_BACKEND=noop"):
            call_command("check_document_scan_runtime")

    @override_settings(DOCUMENT_SCAN_BACKEND="noop")
    @mock.patch(
        "wms.jobs.runtime_checks.shutil.which",
        return_value=None,
    )
    def test_command_accepts_noop_backend_with_allow_noop(self, _which_mock):
        out = StringIO()
        call_command("check_document_scan_runtime", "--allow-noop", stdout=out)
        self.assertIn("Runtime check scan documentaire: OK.", out.getvalue())

    @override_settings(
        DOCUMENT_SCAN_BACKEND="clamav",
        DOCUMENT_SCAN_CLAMAV_COMMAND="clamscan",
    )
    @mock.patch(
        "wms.jobs.runtime_checks.shutil.which",
        return_value="/usr/bin/clamscan",
    )
    def test_command_enforces_pending_failed_and_stale_thresholds(self, _which_mock):
        now = timezone.now()
        self._create_scan_event(status=IntegrationStatus.PENDING, processed_at=now)
        self._create_scan_event(status=IntegrationStatus.FAILED, processed_at=now)
        self._create_scan_event(
            status=IntegrationStatus.PROCESSING,
            processed_at=now - timedelta(seconds=120),
        )

        with self.assertRaisesMessage(CommandError, "depasse --max-pending=0"):
            call_command(
                "check_document_scan_runtime",
                "--max-pending=0",
                "--max-failed=0",
                "--max-stale-processing=0",
                "--processing-timeout-seconds=60",
            )

    @override_settings(
        DOCUMENT_SCAN_BACKEND="clamav",
        DOCUMENT_SCAN_CLAMAV_COMMAND="clamscan",
    )
    @mock.patch(
        "wms.jobs.runtime_checks.shutil.which",
        return_value="/usr/bin/clamscan",
    )
    def test_command_rejects_negative_thresholds(self, _which_mock):
        with self.assertRaisesMessage(CommandError, "--max-failed doit etre >= 0"):
            call_command("check_document_scan_runtime", "--max-failed=-1")

    @mock.patch(
        "wms.management.commands.check_document_scan_runtime.run_document_scan_runtime_check",
        return_value={
            "backend": "clamav",
            "clamav_command": "clamscan",
            "clamav_available": True,
            "counts": {
                IntegrationStatus.PENDING: 0,
                IntegrationStatus.PROCESSING: 0,
                IntegrationStatus.FAILED: 0,
                IntegrationStatus.PROCESSED: 0,
            },
            "stale_processing": 0,
            "timeout_seconds": 900,
            "issues": [],
        },
    )
    def test_command_delegates_runtime_check_to_job_layer(self, runtime_check_mock):
        out = StringIO()

        call_command("check_document_scan_runtime", stdout=out)

        runtime_check_mock.assert_called_once_with(
            allow_noop=False,
            max_pending=None,
            max_failed=0,
            max_stale_processing=0,
            processing_timeout_seconds=None,
        )
        self.assertIn("Runtime check scan documentaire: OK.", out.getvalue())
