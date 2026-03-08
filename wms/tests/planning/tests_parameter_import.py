import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from openpyxl import Workbook

from contacts.models import Contact, ContactType
from wms.models import Destination, PlanningDestinationRule, PlanningParameterSet


class PlanningParameterImportTests(TestCase):
    def test_import_command_creates_destination_rules(self):
        correspondent = Contact.objects.create(
            name="Correspondent ABJ",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="CI",
            correspondent_contact=correspondent,
        )
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "ParamDest"
        sheet.append(
            [
                "Destination IATA",
                "Libelle",
                "Frequence hebdo",
                "Max colis vol",
                "Priorite",
                "Actif",
                "Notes",
            ]
        )
        sheet.append(["ABJ", "Abidjan weekly", 2, 12, 5, "oui", "Imported from workbook"])

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "planning-parameters.xlsx"
            workbook.save(path)

            call_command(
                "import_planning_parameters",
                str(path),
                "--name",
                "Bootstrap mars 2026",
            )

        parameter_set = PlanningParameterSet.objects.get(name="Bootstrap mars 2026")
        rule = PlanningDestinationRule.objects.get(parameter_set=parameter_set)

        self.assertEqual(rule.destination, destination)
        self.assertEqual(rule.label, "Abidjan weekly")
        self.assertEqual(rule.weekly_frequency, 2)
        self.assertEqual(rule.max_cartons_per_flight, 12)
        self.assertEqual(rule.priority, 5)
        self.assertTrue(rule.is_active)
