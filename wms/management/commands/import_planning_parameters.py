from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from wms.planning.parameter_import import import_destination_rules


class Command(BaseCommand):
    help = "Import planning parameters from an Excel workbook."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to the planning workbook")
        parser.add_argument("--name", required=True, help="Planning parameter set name")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            parameter_set = import_destination_rules(
                workbook_path=options["path"],
                parameter_set_name=options["name"],
                created_by=None,
            )
        except FileNotFoundError as exc:
            raise CommandError(f"File not found: {options['path']}") from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported planning destination rules into parameter set {parameter_set.name}."
            )
        )
