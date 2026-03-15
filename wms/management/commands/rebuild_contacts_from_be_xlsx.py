from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from wms.contact_rebuild import (
    apply_be_contact_dataset,
    build_be_contact_dataset,
    render_review_report,
)

DEFAULT_REPORT_PATH = "docs/import/be_contact_rebuild_review.md"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (_project_root() / path).resolve()


class Command(BaseCommand):
    help = "Normalize the BE workbook and rebuild contacts, destinations, and org-role links."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            required=True,
            help="Path to the BE workbook source.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Normalize and report planned writes without touching the database.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the rebuild to the database.",
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

        dataset = build_be_contact_dataset(source_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_review_report(dataset.review_items), encoding="utf-8")

        if apply:
            apply_be_contact_dataset(dataset)

        self.stdout.write(f"Rebuild contacts from BE workbook [{'APPLY' if apply else 'DRY RUN'}]")
        self.stdout.write(f"Source: {source_path}")
        self.stdout.write(f"Review report: {report_path}")
        self.stdout.write(f"Donors: {len(dataset.donors)}")
        self.stdout.write(f"Shippers: {len(dataset.shippers)}")
        self.stdout.write(f"Recipients: {len(dataset.recipients)}")
        self.stdout.write(f"Correspondents: {len(dataset.correspondents)}")
        self.stdout.write(f"Destinations: {len(dataset.destinations)}")
        self.stdout.write(f"Shipper scopes: {len(dataset.shipper_scopes)}")
        self.stdout.write(f"Recipient bindings: {len(dataset.recipient_bindings)}")
        self.stdout.write(f"Review items: {len(dataset.review_items)}")
