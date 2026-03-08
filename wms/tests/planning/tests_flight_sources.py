import json
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock
from urllib import error

from django.test import TestCase, override_settings
from openpyxl import Workbook

from contacts.models import Contact, ContactType
from wms.models import Destination, PlanningRunFlightMode
from wms.planning.flight_sources import (
    DEFAULT_PLANNING_FLIGHT_API_BASE_URL,
    PlanningFlightApiClient,
    build_planning_flight_api_client,
    collect_flight_batches,
    import_excel_flights,
)


class FlightSourceTests(TestCase):
    class _UrlOpenResponse:
        def __init__(self, body):
            self._body = body

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

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
                "Departure Time",
                "Origin IATA",
                "Destination IATA",
                "Routing",
                "Route Pos",
                "Capacity Units",
            ]
        )
        sheet.append(["af702 ", "2026-03-10", "09:45", " cdg", "abj ", "CDG-ABJ", 1, 12])

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
        self.assertEqual(flight.departure_time.isoformat(timespec="minutes"), "09:45")
        self.assertEqual(flight.routing, "CDG-ABJ")
        self.assertEqual(flight.route_pos, 1)
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

    @override_settings(
        PLANNING_FLIGHT_API_BASE_URL="https://api.airfranceklm.com/opendata/flightstatus",
        PLANNING_FLIGHT_API_KEY="af-secret",  # pragma: allowlist secret
        PLANNING_FLIGHT_API_TIMEOUT_SECONDS=17,
        PLANNING_FLIGHT_API_ORIGIN_IATA="CDG",
        PLANNING_FLIGHT_API_AIRLINE_CODE="AF",
        PLANNING_FLIGHT_API_TIME_ORIGIN_TYPE="M",
    )
    def test_build_planning_flight_api_client_uses_settings(self):
        client = build_planning_flight_api_client()

        self.assertEqual(client.base_url, "https://api.airfranceklm.com/opendata/flightstatus")
        self.assertEqual(client.api_key, "af-secret")
        self.assertEqual(client.timeout_seconds, 17)
        self.assertEqual(client.origin_iata, "CDG")
        self.assertEqual(client.operating_airline_code, "AF")
        self.assertEqual(client.time_origin_type, "M")

    def test_api_client_fetch_flights_normalizes_airfrance_payload(self):
        payload = {
            "operationalFlights": [
                {
                    "route": ["CDG", "NKC", "CKY"],
                    "airline": {"code": "AF"},
                    "flightNumber": 1234,
                    "flightLegs": [
                        {
                            "departureInformation": {
                                "departureStation": "CDG",
                                "times": {
                                    "scheduled": "2026-03-10T09:45:00.000+01:00",
                                    "latestPublished": "2026-03-10T10:15:00.000+01:00",
                                },
                            }
                        }
                    ],
                }
            ]
        }
        client = PlanningFlightApiClient(
            base_url=DEFAULT_PLANNING_FLIGHT_API_BASE_URL,
            api_key="af-secret",  # pragma: allowlist secret
            timeout_seconds=17,
            origin_iata="CDG",
            operating_airline_code="AF",
            time_origin_type="M",
        )

        with mock.patch(
            "wms.planning.flight_sources.request.urlopen",
            return_value=self._UrlOpenResponse(json.dumps(payload).encode("utf-8")),
        ) as urlopen_mock:
            records = client.fetch_flights(
                start_date=date(2026, 3, 9),
                end_date=date(2026, 3, 15),
            )

        self.assertEqual(len(records), 2)
        self.assertEqual([record["destination_iata"] for record in records], ["NKC", "CKY"])
        self.assertEqual([record["route_pos"] for record in records], [1, 2])
        self.assertEqual(records[0]["flight_number"], "AF1234")
        self.assertEqual(records[0]["routing"], "CDG-NKC-CKY")
        self.assertEqual(records[0]["departure_date"], "2026-03-10")
        self.assertEqual(records[0]["departure_time"], "10:15")
        request_obj = urlopen_mock.call_args.args[0]
        self.assertIn("origin=CDG", request_obj.full_url)
        self.assertIn("operatingAirlineCode=AF", request_obj.full_url)
        self.assertIn("timeOriginType=M", request_obj.full_url)
        self.assertEqual(request_obj.headers["Api-key"], "af-secret")
        self.assertEqual(urlopen_mock.call_args.kwargs["timeout"], 17)

    def test_api_client_returns_empty_list_on_404(self):
        http_error = error.HTTPError(
            url=DEFAULT_PLANNING_FLIGHT_API_BASE_URL,
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )
        client = PlanningFlightApiClient(
            base_url=DEFAULT_PLANNING_FLIGHT_API_BASE_URL,
            api_key="af-secret",  # pragma: allowlist secret
            timeout_seconds=17,
            origin_iata="CDG",
            operating_airline_code="AF",
            time_origin_type="P",
        )

        with mock.patch(
            "wms.planning.flight_sources.request.urlopen",
            side_effect=http_error,
        ):
            records = client.fetch_flights(
                start_date=date(2026, 3, 9),
                end_date=date(2026, 3, 15),
            )

        self.assertEqual(records, [])

    def test_api_client_falls_back_to_earliest_leg_and_strips_final_origin(self):
        payload = {
            "operationalFlights": [
                {
                    "route": ["CDG", "RUN", "CDG"],
                    "airline": {"code": "AF"},
                    "flightNumber": 652,
                    "flightLegs": [
                        {
                            "departureInformation": {
                                "departureStation": "XXX",
                                "times": {"scheduled": "2026-03-10T13:00:00.000+01:00"},
                            }
                        },
                        {
                            "departureInformation": {
                                "departureStation": "YYY",
                                "times": {"latestPublished": "2026-03-10T11:00:00.000+01:00"},
                            }
                        },
                    ],
                }
            ]
        }
        client = PlanningFlightApiClient(
            base_url=DEFAULT_PLANNING_FLIGHT_API_BASE_URL,
            api_key="af-secret",  # pragma: allowlist secret
            timeout_seconds=17,
            origin_iata="CDG",
            operating_airline_code="AF",
            time_origin_type="P",
        )

        with mock.patch(
            "wms.planning.flight_sources.request.urlopen",
            return_value=self._UrlOpenResponse(json.dumps(payload).encode("utf-8")),
        ):
            records = client.fetch_flights(
                start_date=date(2026, 3, 9),
                end_date=date(2026, 3, 15),
            )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["routing"], "CDG-RUN")
        self.assertEqual(records[0]["destination_iata"], "RUN")
        self.assertEqual(records[0]["departure_time"], "11:00")
