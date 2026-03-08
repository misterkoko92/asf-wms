import tempfile
from datetime import date
from pathlib import Path

from django.test import TestCase
from openpyxl import Workbook

from contacts.models import Contact, ContactType
from wms.models import Destination, PlanningRunFlightMode
from wms.planning.flight_sources import collect_flight_batches, import_excel_flights


class FlightSourceTests(TestCase):
    def setUp(self):
        correspondent = Contact.objects.create(
            name="Correspondent ABJ",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="CI",
            correspondent_contact=correspondent,
        )

    def _write_excel_workbook(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Flights"
        sheet.append(
            [
                "Flight Number",
                "Departure Date",
                "Origin IATA",
                "Destination IATA",
                "Capacity Units",
            ]
        )
        sheet.append(["af702 ", "2026-03-10", " cdg", "abj ", 12])

        tmp_dir = tempfile.TemporaryDirectory()
        path = Path(tmp_dir.name) / "flights.xlsx"
        workbook.save(path)
        return tmp_dir, path

    def test_import_excel_flights_creates_batch_and_rows(self):
        tmp_dir, path = self._write_excel_workbook()
        self.addCleanup(tmp_dir.cleanup)

        batch = import_excel_flights(path)
        flight = batch.flights.get()

        self.assertEqual(batch.source, "excel")
        self.assertEqual(batch.status, "imported")
        self.assertEqual(batch.flights.count(), 1)
        self.assertEqual(flight.flight_number, "AF702")
        self.assertEqual(flight.destination, self.destination)
        self.assertEqual(flight.capacity_units, 12)

    def test_collect_hybrid_flight_batches_adds_api_rows(self):
        tmp_dir, path = self._write_excel_workbook()
        self.addCleanup(tmp_dir.cleanup)
        excel_batch = import_excel_flights(path)

        class StubApiClient:
            def fetch_flights(self, *, start_date, end_date):
                self.called_with = (start_date, end_date)
                return [
                    {
                        "flight_number": "af704",
                        "departure_date": "2026-03-11",
                        "origin_iata": "cdg",
                        "destination_iata": "abj",
                        "capacity_units": "15",
                    }
                ]

        api_client = StubApiClient()

        batches = collect_flight_batches(
            flight_mode=PlanningRunFlightMode.HYBRID,
            start_date=date(2026, 3, 9),
            end_date=date(2026, 3, 15),
            excel_batch=excel_batch,
            api_client=api_client,
        )

        self.assertEqual(len(batches), 2)
        self.assertEqual(batches[0].source, "excel")
        self.assertEqual(batches[1].source, "api")
        self.assertEqual(batches[1].flights.get().flight_number, "AF704")
        self.assertEqual(batches[1].flights.get().destination, self.destination)
