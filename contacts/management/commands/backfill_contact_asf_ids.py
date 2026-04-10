from django.core.management.base import BaseCommand

from contacts.asf_ids import backfill_missing_contact_asf_ids


class Command(BaseCommand):
    help = "Backfill additif des asf_id manquants sur les contacts."

    def add_arguments(self, parser):
        mode_group = parser.add_mutually_exclusive_group()
        mode_group.add_argument(
            "--dry-run",
            action="store_true",
            help="Calcule le backfill sans persister les changements.",
        )
        mode_group.add_argument(
            "--apply",
            action="store_true",
            help="Execute le backfill et persiste les changements.",
        )

    def handle(self, *args, **options):
        apply = bool(options.get("apply"))
        dry_run = not apply
        summary = backfill_missing_contact_asf_ids(dry_run=dry_run)
        mode = "APPLY" if apply else "DRY RUN"

        self.stdout.write(self.style.MIGRATE_HEADING(f"Backfill contact asf ids [{mode}]"))
        self.stdout.write(
            "\n".join(
                [
                    f"- Contacts scanned: {summary['scanned_contacts']}",
                    f"- Contacts missing asf_id: {summary['missing_contacts']}",
                    f"- Contacts backfilled: {summary['backfilled_contacts']}",
                ]
            )
        )
