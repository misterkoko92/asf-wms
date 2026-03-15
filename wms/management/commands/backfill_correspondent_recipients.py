from django.core.management.base import BaseCommand

from contacts.correspondent_recipient_promotion import backfill_correspondent_recipients


class Command(BaseCommand):
    help = "Backfill additif des correspondants pour les rendre utilisables comme destinataires."

    def add_arguments(self, parser):
        mode_group = parser.add_mutually_exclusive_group()
        mode_group.add_argument(
            "--dry-run",
            action="store_true",
            help="Execute le backfill sans persister les changements.",
        )
        mode_group.add_argument(
            "--apply",
            action="store_true",
            help="Execute le backfill et persiste les changements.",
        )

    def handle(self, *args, **options):
        apply = bool(options.get("apply"))
        dry_run = not apply
        summary = backfill_correspondent_recipients(dry_run=dry_run)
        mode = "APPLY" if apply else "DRY RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(f"Backfill correspondent recipients [{mode}]"))
        self.stdout.write(
            "\n".join(
                [
                    f"- Correspondents scanned: {summary['processed_contacts']}",
                    f"- Contacts changed: {summary['changed_contacts']}",
                    f"- Recipient tags added: {summary['recipient_tags_added']}",
                    f"- Support organizations created: {summary['support_organizations_created']}",
                    (
                        "- Contacts attached to support organization: "
                        f"{summary['contacts_attached_to_support_org']}"
                    ),
                    f"- Recipient roles created: {summary['recipient_roles_created']}",
                    f"- Recipient roles reactivated: {summary['recipient_roles_reactivated']}",
                ]
            )
        )
