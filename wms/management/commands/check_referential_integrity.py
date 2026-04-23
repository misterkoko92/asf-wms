from django.core.management.base import BaseCommand, CommandError

from wms.referential_integrity import find_referential_integrity_issues, issue_count_by_code


class Command(BaseCommand):
    help = "Verifie les invariants referentiels critiques apres migrations ou avant release."

    def add_arguments(self, parser):
        parser.add_argument(
            "--report-only",
            action="store_true",
            help="Affiche les anomalies sans retourner d'erreur.",
        )
        parser.add_argument(
            "--max-details",
            type=int,
            default=50,
            help="Nombre maximum de lignes detaillees affichees.",
        )

    def handle(self, *args, **options):
        max_details = options["max_details"]
        if max_details < 0:
            raise CommandError("--max-details doit etre >= 0")

        issues = find_referential_integrity_issues()
        if not issues:
            self.stdout.write(self.style.SUCCESS("Referential integrity: OK (0 issue)."))
            return

        self.stdout.write(
            self.style.WARNING(f"Referential integrity: {len(issues)} issue(s) detected.")
        )
        for code, count in issue_count_by_code(issues).items():
            self.stdout.write(f"- {code}: {count}")

        if max_details:
            self.stdout.write("Details:")
            for issue in issues[:max_details]:
                self.stdout.write(f"- {issue.format()}")
            if len(issues) > max_details:
                self.stdout.write(f"- ... {len(issues) - max_details} additional issue(s)")

        if not options["report_only"]:
            raise CommandError("Referential integrity check failed: issues detected.")
