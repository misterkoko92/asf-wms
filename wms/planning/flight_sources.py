import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from urllib import error, parse, request

from django.utils.dateparse import parse_date, parse_datetime, parse_time

from wms.import_utils import extract_tabular_data, get_value, normalize_header, parse_int, parse_str
from wms.models import Flight, FlightSourceBatch, FlightSourceBatchStatus, PlanningRunFlightMode
from wms.runtime_settings import get_planning_flight_api_config

DEFAULT_PLANNING_FLIGHT_API_BASE_URL = "https://api.airfranceklm.com/opendata/flightstatus"
DEFAULT_PLANNING_FLIGHT_API_ORIGIN_IATA = "CDG"
DEFAULT_PLANNING_FLIGHT_API_AIRLINE_CODE = "AF"
DEFAULT_PLANNING_FLIGHT_API_TIME_ORIGIN_TYPE = "P"
ALLOWED_TIME_ORIGIN_TYPES = {"S", "M", "I", "P"}
FLIGHTS_SHEET_NAME = "Flights"


class PlanningFlightApiError(RuntimeError):
    """Raised when the planning flight API cannot be queried or parsed safely."""


class PlanningFlightApiClient:
    def __init__(
        self,
        *,
        base_url,
        api_key,
        timeout_seconds,
        origin_iata=DEFAULT_PLANNING_FLIGHT_API_ORIGIN_IATA,
        operating_airline_code=DEFAULT_PLANNING_FLIGHT_API_AIRLINE_CODE,
        time_origin_type=DEFAULT_PLANNING_FLIGHT_API_TIME_ORIGIN_TYPE,
    ):
        self.base_url = (base_url or DEFAULT_PLANNING_FLIGHT_API_BASE_URL).strip()
        self.api_key = (api_key or "").strip()
        self.timeout_seconds = timeout_seconds
        self.origin_iata = (origin_iata or DEFAULT_PLANNING_FLIGHT_API_ORIGIN_IATA).strip().upper()
        self.operating_airline_code = (
            (operating_airline_code or DEFAULT_PLANNING_FLIGHT_API_AIRLINE_CODE).strip().upper()
        )
        normalized_time_origin_type = (
            (time_origin_type or DEFAULT_PLANNING_FLIGHT_API_TIME_ORIGIN_TYPE).strip().upper()
        )
        if normalized_time_origin_type not in ALLOWED_TIME_ORIGIN_TYPES:
            raise PlanningFlightApiError(
                f"Unsupported planning flight API timeOriginType: {normalized_time_origin_type}"
            )
        self.time_origin_type = normalized_time_origin_type

    def _build_url(self, *, start_date, end_date):
        query = parse.urlencode(
            {
                "startRange": f"{start_date.isoformat()}T00:00:01Z",
                "endRange": f"{end_date.isoformat()}T23:59:59Z",
                "origin": self.origin_iata,
                "operatingAirlineCode": self.operating_airline_code,
                "timeOriginType": self.time_origin_type,
            }
        )
        separator = "&" if "?" in self.base_url else "?"
        return f"{self.base_url}{separator}{query}"

    def _read_payload(self, *, start_date, end_date):
        if not self.api_key:
            raise PlanningFlightApiError(
                "PLANNING_FLIGHT_API_KEY is required for planning API imports."
            )

        req = request.Request(
            self._build_url(start_date=start_date, end_date=end_date),
            method="GET",
            headers={
                "API-Key": self.api_key,
                "Accept": "application/hal+json",
                "User-Agent": "ASF-WMS/planning-flight-client",
            },
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:  # nosec B310
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            if exc.code == 404:
                return {"operationalFlights": []}
            message = ""
            try:
                message = exc.read().decode("utf-8", errors="ignore")
            except OSError:
                message = ""
            raise PlanningFlightApiError(
                f"Planning flight API failed with HTTP {exc.code}: {message or exc}"
            ) from exc
        except error.URLError as exc:
            raise PlanningFlightApiError(f"Planning flight API request failed: {exc}") from exc

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise PlanningFlightApiError("Planning flight API returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise PlanningFlightApiError("Planning flight API returned an unexpected payload.")
        return payload

    def fetch_flights(self, *, start_date, end_date):
        payload = self._read_payload(start_date=start_date, end_date=end_date)
        return _extract_api_records(
            payload,
            origin_iata=self.origin_iata,
            operating_airline_code=self.operating_airline_code,
        )


def _rows_from_headers_and_values(headers, rows):
    normalized_headers = [normalize_header(header) for header in headers]
    entries = []
    for row in rows:
        entry = {}
        for index, header in enumerate(normalized_headers):
            if not header:
                continue
            entry[header] = row[index] if index < len(row) else ""
        entries.append(entry)
    return entries


def _parse_departure_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = parse_date(str(value or "").strip())
    if parsed is None:
        raise ValueError(f"Invalid departure date: {value}")
    return parsed


def _parse_departure_time(value):
    text = parse_str(value)
    if text is None:
        return None
    parsed = parse_time(text)
    if parsed is None:
        raise ValueError(f"Invalid departure time: {value}")
    return parsed


def _infer_route_pos(*, routing, destination_iata):
    if not routing or not destination_iata:
        return None
    parts = [part.strip().upper() for part in str(routing).replace(",", "-").split("-") if part]
    destination = str(destination_iata).strip().upper()
    for index, code in enumerate(parts[1:], start=1):
        if code == destination:
            return index
    return None


def _extract_api_departure_iso(flight, *, origin_iata):
    def _pick_departure_time(leg):
        departure_info = leg.get("departureInformation", {}) if isinstance(leg, dict) else {}
        times = departure_info.get("times", {}) if isinstance(departure_info, dict) else {}
        if not isinstance(times, dict):
            return ""
        estimated = times.get("estimated", {})
        estimated_value = estimated.get("value") if isinstance(estimated, dict) else ""
        return (
            str(times.get("latestPublished") or "")
            or str(times.get("actual") or "")
            or str(estimated_value or "")
            or str(times.get("scheduled") or "")
        )

    flight_legs = flight.get("flightLegs") or []
    leg_from_origin = next(
        (
            leg
            for leg in flight_legs
            if str(leg.get("departureInformation", {}).get("departureStation", "")).upper()
            == origin_iata
        ),
        None,
    )
    if leg_from_origin:
        departure_iso = _pick_departure_time(leg_from_origin)
        if departure_iso:
            return departure_iso

    candidates = []
    for leg in flight_legs:
        departure_iso = _pick_departure_time(leg)
        if departure_iso:
            candidates.append(departure_iso)
    if not candidates:
        return ""
    return min(candidates)


def _extract_api_records(payload, *, origin_iata, operating_airline_code):
    records = []
    for flight in payload.get("operationalFlights", []):
        route = [str(code or "").strip().upper() for code in (flight.get("route") or []) if code]
        if len(route) < 2:
            continue
        if route[-1] == origin_iata and len(route) > 1:
            route = route[:-1]
        if len(route) < 2 or route[0] != origin_iata:
            continue

        airline_code = str(flight.get("airline", {}).get("code", "")).strip().upper()
        if operating_airline_code and airline_code and airline_code != operating_airline_code:
            continue

        departure_iso = _extract_api_departure_iso(flight, origin_iata=origin_iata)
        departure_dt = (
            parse_datetime(departure_iso.replace("Z", "+00:00")) if departure_iso else None
        )
        if departure_dt is None:
            continue

        flight_number = f"{airline_code}{str(flight.get('flightNumber') or '').strip()}".strip()
        if not flight_number:
            continue

        cleaned_route = "-".join(route)
        for route_pos, destination_iata in enumerate(route[1:], start=1):
            records.append(
                {
                    "flight_number": flight_number,
                    "departure_date": departure_dt.date().isoformat(),
                    "departure_time": departure_dt.strftime("%H:%M"),
                    "origin_iata": origin_iata,
                    "destination_iata": destination_iata,
                    "routing": cleaned_route,
                    "route_pos": route_pos,
                }
            )
    return records


def normalize_flight_record(row):
    flight_number = parse_str(get_value(row, "flight_number", "numero_vol", "numero_de_vol"))
    if not flight_number:
        raise ValueError("Each flight row must contain a flight number.")
    destination_iata = parse_str(
        get_value(row, "destination_iata", "destination", "code_iata_destination")
    )
    if not destination_iata:
        raise ValueError("Each flight row must contain a destination IATA code.")
    origin_iata = parse_str(get_value(row, "origin_iata", "origin", "code_iata_origin")) or ""
    departure_date = _parse_departure_date(get_value(row, "departure_date", "date_depart", "date"))
    departure_time = _parse_departure_time(
        get_value(row, "departure_time", "heure_depart", "departure")
    )
    capacity_units = parse_int(
        get_value(row, "capacity_units", "capacite", "capacity", "max_colis_vol")
    )
    routing = parse_str(get_value(row, "routing", "route", "routing_str")) or ""
    route_pos = parse_int(get_value(row, "route_pos", "route_position", "stop_order"))
    destination_iata = destination_iata.upper()
    origin_iata = origin_iata.upper()
    if route_pos is None:
        route_pos = _infer_route_pos(routing=routing, destination_iata=destination_iata)
    destination = (
        Flight._meta.get_field("destination")
        .remote_field.model.objects.filter(iata_code__iexact=destination_iata)
        .first()
    )
    return {
        "flight_number": flight_number.strip().upper(),
        "departure_date": departure_date,
        "departure_time": departure_time,
        "origin_iata": origin_iata,
        "destination_iata": destination_iata,
        "routing": routing,
        "route_pos": route_pos,
        "destination": destination,
        "capacity_units": capacity_units,
    }


def _persist_batch(*, source, records, file_name="", checksum="", notes=""):
    records = list(records)
    dates = [record["departure_date"] for record in records]
    batch = FlightSourceBatch.objects.create(
        source=source,
        period_start=min(dates) if dates else None,
        period_end=max(dates) if dates else None,
        file_name=file_name,
        checksum=checksum,
        status=FlightSourceBatchStatus.IMPORTED if records else FlightSourceBatchStatus.DRAFT,
        notes=notes,
    )
    flights = [Flight(batch=batch, **record) for record in records]
    Flight.objects.bulk_create(flights)
    return batch


def import_excel_flights(workbook_path):
    path = Path(workbook_path)
    data = path.read_bytes()
    headers, rows = extract_tabular_data(data, path.suffix.lower(), sheet_name=FLIGHTS_SHEET_NAME)
    entries = _rows_from_headers_and_values(headers, rows)
    records = []
    for row in entries:
        if not any(
            (value or "").strip() if isinstance(value, str) else value for value in row.values()
        ):
            continue
        records.append(normalize_flight_record(row))
    return _persist_batch(
        source="excel",
        records=records,
        file_name=path.name,
        checksum=hashlib.sha256(data).hexdigest(),
    )


def build_planning_flight_api_client():
    config = get_planning_flight_api_config()
    return PlanningFlightApiClient(
        base_url=config.base_url or DEFAULT_PLANNING_FLIGHT_API_BASE_URL,
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
        origin_iata=config.origin_iata,
        operating_airline_code=config.operating_airline_code,
        time_origin_type=config.time_origin_type,
    )


def import_api_flights(*, start_date, end_date, client=None):
    api_client = client or build_planning_flight_api_client()
    records = [
        normalize_flight_record(row)
        for row in api_client.fetch_flights(start_date=start_date, end_date=end_date)
    ]
    return _persist_batch(
        source="api",
        records=records,
        notes=f"Imported for {start_date.isoformat()} -> {end_date.isoformat()}",
    )


def collect_flight_batches(*, flight_mode, start_date, end_date, excel_batch=None, api_client=None):
    batches = []
    if flight_mode in {PlanningRunFlightMode.EXCEL, PlanningRunFlightMode.HYBRID} and excel_batch:
        batches.append(excel_batch)
    if flight_mode in {PlanningRunFlightMode.API, PlanningRunFlightMode.HYBRID}:
        batches.append(
            import_api_flights(
                start_date=start_date,
                end_date=end_date,
                client=api_client,
            )
        )
    return batches
