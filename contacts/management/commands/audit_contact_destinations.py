from django.core.management.base import BaseCommand, CommandError

from contacts.destination_scope import sync_contact_destination_scope
from contacts.models import Contact


class Command(BaseCommand):
    help = (
        "Audit de cohérence des destinations contacts. "
        "La source de vérité est Contact.destinations (M2M); "
        "Contact.destination est conservé temporairement pour compatibilité."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Applique la correction automatique des incohérences détectées.",
        )
        parser.add_argument(
            "--fail-on-issues",
            action="store_true",
            help="Retourne un code d'erreur s'il existe au moins une incohérence.",
        )

    def handle(self, *args, **options):
        apply_fixes = options["apply"]
        fail_on_issues = options["fail_on_issues"]
        stats = {
            "legacy_only": 0,
            "single_mismatch": 0,
            "legacy_with_multi": 0,
            "ok": 0,
        }
        fixed = 0

        contacts = Contact.objects.prefetch_related("destinations").order_by("id")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Audit destinations contacts: {contacts.count()} contact(s)."
            )
        )

        for contact in contacts:
            destination_ids = sorted(contact.destinations.values_list("id", flat=True))
            legacy_destination_id = contact.destination_id
            issue = None

            if not destination_ids and legacy_destination_id:
                issue = "legacy_only"
            elif len(destination_ids) == 1 and legacy_destination_id != destination_ids[0]:
                issue = "single_mismatch"
            elif len(destination_ids) > 1 and legacy_destination_id is not None:
                issue = "legacy_with_multi"

            if issue is None:
                stats["ok"] += 1
                continue

            stats[issue] += 1
            self.stdout.write(
                self.style.WARNING(
                    f"- Contact #{contact.id} {contact.name}: "
                    f"legacy={legacy_destination_id or '-'} "
                    f"m2m={destination_ids or '[]'} issue={issue}"
                )
            )
            if apply_fixes:
                sync_contact_destination_scope(contact)
                fixed += 1

        issue_count = stats["legacy_only"] + stats["single_mismatch"] + stats["legacy_with_multi"]

        summary = (
            f"OK={stats['ok']} "
            f"legacy_only={stats['legacy_only']} "
            f"single_mismatch={stats['single_mismatch']} "
            f"legacy_with_multi={stats['legacy_with_multi']}"
        )
        if issue_count == 0:
            self.stdout.write(self.style.SUCCESS(f"Aucune incohérence détectée. {summary}"))
            return

        if apply_fixes:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{issue_count} incohérence(s) détectée(s), {fixed} corrigée(s). {summary}"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"{issue_count} incohérence(s) détectée(s). {summary}")
            )

        if fail_on_issues:
            raise CommandError("Audit destinations contacts en échec: incohérences détectées.")
