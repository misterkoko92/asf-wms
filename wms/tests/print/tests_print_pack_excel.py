from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase
from openpyxl import Workbook

from wms.print_pack_excel import PrintPackMappingError, fill_workbook_cells


class PrintPackExcelTests(SimpleTestCase):
    def _mapping(self, **overrides):
        payload = {
            "worksheet_name": "Main",
            "cell_ref": "D5",
            "source_key": "shipment.recipient.full_name",
            "transform": "",
            "required": False,
        }
        payload.update(overrides)
        return SimpleNamespace(**payload)

    def test_fill_workbook_cells_writes_transformed_values(self):
        workbook = Workbook()
        workbook.active.title = "Main"
        mappings = [self._mapping(transform="upper")]
        payload = {"shipment": {"recipient": {"full_name": "Doe John"}}}

        fill_workbook_cells(workbook, mappings, payload)

        self.assertEqual(workbook["Main"]["D5"].value, "DOE JOHN")

    def test_fill_workbook_cells_formats_dates(self):
        workbook = Workbook()
        workbook.active.title = "Main"
        mappings = [self._mapping(source_key="shipment.requested_delivery_date", transform="date_fr")]
        payload = {"shipment": {"requested_delivery_date": date(2026, 3, 1)}}

        fill_workbook_cells(workbook, mappings, payload)

        self.assertEqual(workbook["Main"]["D5"].value, "01/03/2026")

    def test_fill_workbook_cells_raises_when_required_value_is_missing(self):
        workbook = Workbook()
        workbook.active.title = "Main"
        mappings = [self._mapping(required=True)]
        payload = {"shipment": {}}

        with self.assertRaises(PrintPackMappingError):
            fill_workbook_cells(workbook, mappings, payload)

    def test_fill_workbook_cells_writes_repeating_rows(self):
        workbook = Workbook()
        workbook.active.title = "Main"
        mappings = [
            self._mapping(
                cell_ref="A14",
                source_key="carton.items[].product_name",
            ),
            self._mapping(
                cell_ref="C14",
                source_key="carton.items[].quantity",
            ),
        ]
        payload = {
            "carton": {
                "items": [
                    {"product_name": "Gants", "quantity": 4},
                    {"product_name": "Masques", "quantity": 10},
                ]
            }
        }

        fill_workbook_cells(workbook, mappings, payload)

        self.assertEqual(workbook["Main"]["A14"].value, "Gants")
        self.assertEqual(workbook["Main"]["A15"].value, "Masques")
        self.assertEqual(workbook["Main"]["C14"].value, 4)
        self.assertEqual(workbook["Main"]["C15"].value, 10)

    def test_fill_workbook_cells_raises_when_repeating_value_is_required_and_missing(self):
        workbook = Workbook()
        workbook.active.title = "Main"
        mappings = [
            self._mapping(
                cell_ref="A14",
                source_key="carton.items[].product_name",
                required=True,
            )
        ]
        payload = {"carton": {"items": []}}

        with self.assertRaises(PrintPackMappingError):
            fill_workbook_cells(workbook, mappings, payload)
