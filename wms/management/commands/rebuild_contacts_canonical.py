from __future__ import annotations

from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from wms.reset_operational_data import render_reset_summary, reset_operational_data

DEFAULT_REPORT_PATH = "docs/import/be_contact_rebuild_review.md"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (_project_root() / path).resolve()


class Command(BaseCommand):
    help = (
        "Reset operational contact runtime data, then rebuild canonical contacts, "
        "capabilities, and shipment parties from the BE workbook."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            required=True,
            help="Path to the canonical BE workbook source.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the reset and rebuild workflow without touching the database.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the reset and rebuild workflow.",
        )
        parser.add_argument(
            "--report-path",
            default=DEFAULT_REPORT_PATH,
            help=f"Path to the markdown review report (default: {DEFAULT_REPORT_PATH}).",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        apply = bool(options.get("apply"))
        if dry_run and apply:
            raise CommandError("Choose either --dry-run or --apply, not both.")

        source_path = _resolve_path(options["source"])
        report_path = _resolve_path(options["report_path"])
        if not source_path.exists():
            raise CommandError(f"Workbook source not found: {source_path}")

        mode = "APPLY" if apply else "DRY RUN"
        self.stdout.write(f"Canonical contact rebuild [{mode}]")
        self.stdout.write(f"Source: {source_path}")
        self.stdout.write(f"Review report: {report_path}")

        summary = reset_operational_data(apply=apply)
        for line in render_reset_summary(summary, heading="Reset summary"):
            self.stdout.write(line)

        rebuild_flag = "--apply" if apply else "--dry-run"
        call_command(
            "rebuild_contacts_from_be_xlsx",
            "--source",
            str(source_path),
            rebuild_flag,
            "--report-path",
            str(report_path),
            stdout=self.stdout,
        )
