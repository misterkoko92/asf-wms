from django.core.management.base import BaseCommand

from wms.organization_roles_backfill import backfill_contacts_to_org_roles


class Command(BaseCommand):
    help = (
        "Backfill non bloquant des contacts legacy vers le modele organization roles."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Execute le backfill sans persister les changements.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        summary = backfill_contacts_to_org_roles(dry_run=dry_run)
        mode = "DRY RUN" if dry_run else "APPLY"
        self.stdout.write(self.style.MIGRATE_HEADING(f"Backfill org roles [{mode}]"))
        self.stdout.write(
            "\n".join(
                [
                    f"- Contacts traites: {summary['processed_contacts']}",
                    f"- Role assignments crees: {summary['created_role_assignments']}",
                    f"- Shipper scopes crees: {summary['created_shipper_scopes']}",
                    f"- Recipient bindings crees: {summary['created_recipient_bindings']}",
                    f"- Items de revue ajoutes: {summary['queued_review_items']}",
                ]
            )
        )
