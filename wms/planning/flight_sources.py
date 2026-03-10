import hashlib
from datetime import date, datetime
from pathlib import Path

from django.utils.dateparse import parse_date, parse_time

from wms.import_utils import extract_tabular_data, get_value, normalize_header, parse_int, parse_str
from wms.models import Flight, FlightSourceBatch, FlightSourceBatchStatus, PlanningRunFlightMode
from wms.planning.flight_providers import UnknownPlanningFlightProviderError
from wms.planning.flight_providers.airfrance_klm import AirFranceKlmFlightProvider
from wms.runtime_settings import get_planning_flight_api_config

FLIGHTS_SHEET_NAME = "Flights"


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
    if config.provider == "airfrance_klm":
        return AirFranceKlmFlightProvider(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout_seconds=config.timeout_seconds,
            origin_iata=config.origin_iata,
            operating_airline_code=config.operating_airline_code,
            time_origin_type=config.time_origin_type,
        )
    raise UnknownPlanningFlightProviderError(
        f"Unsupported planning flight API provider: {config.provider or '<empty>'}"
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
