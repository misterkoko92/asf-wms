import json
import time
from datetime import datetime
from urllib import error, parse, request

from django.utils.dateparse import parse_datetime

from .base import (
    PlanningFlightProvider,
    PlanningFlightProviderConfigurationError,
    PlanningFlightProviderError,
)

DEFAULT_AIRFRANCE_KLM_FLIGHT_API_BASE_URL = "https://api.airfranceklm.com/opendata/flightstatus"
DEFAULT_AIRFRANCE_KLM_ORIGIN_IATA = "CDG"
DEFAULT_AIRFRANCE_KLM_AIRLINE_CODE = "AF"
DEFAULT_AIRFRANCE_KLM_TIME_ORIGIN_TYPE = "P"
ALLOWED_TIME_ORIGIN_TYPES = {"S", "M", "I", "P"}


class AirFranceKlmFlightProvider(PlanningFlightProvider):
    def __init__(
        self,
        *,
        base_url,
        api_key,
        timeout_seconds,
        max_calls_per_day=100,
        min_delay_seconds=1.1,
        origin_iata=DEFAULT_AIRFRANCE_KLM_ORIGIN_IATA,
        operating_airline_code=DEFAULT_AIRFRANCE_KLM_AIRLINE_CODE,
        time_origin_type=DEFAULT_AIRFRANCE_KLM_TIME_ORIGIN_TYPE,
    ):
        self.base_url = (base_url or DEFAULT_AIRFRANCE_KLM_FLIGHT_API_BASE_URL).strip()
        self.api_key = (api_key or "").strip()
        self.timeout_seconds = timeout_seconds
        self.max_calls_per_day = max(1, int(max_calls_per_day or 100))
        self.min_delay_seconds = max(0.1, float(min_delay_seconds or 1.1))
        self.origin_iata = (origin_iata or DEFAULT_AIRFRANCE_KLM_ORIGIN_IATA).strip().upper()
        self.operating_airline_code = (
            (operating_airline_code or DEFAULT_AIRFRANCE_KLM_AIRLINE_CODE).strip().upper()
        )
        normalized_time_origin_type = (
            (time_origin_type or DEFAULT_AIRFRANCE_KLM_TIME_ORIGIN_TYPE).strip().upper()
        )
        if normalized_time_origin_type not in ALLOWED_TIME_ORIGIN_TYPES:
            raise PlanningFlightProviderConfigurationError(
                f"Unsupported planning flight API timeOriginType: {normalized_time_origin_type}"
            )
        self.time_origin_type = normalized_time_origin_type

    def _build_url(self, *, start_date, end_date, destination_code=None):
        query_params = {
            "startRange": f"{start_date.isoformat()}T00:00:01Z",
            "endRange": f"{end_date.isoformat()}T23:59:59Z",
            "origin": self.origin_iata,
            "operatingAirlineCode": self.operating_airline_code,
            "timeOriginType": self.time_origin_type,
        }
        if destination_code:
            query_params["destination"] = destination_code
        query = parse.urlencode(query_params)
        separator = "&" if "?" in self.base_url else "?"
        return f"{self.base_url}{separator}{query}"

    def _read_payload(self, *, start_date, end_date, destination_code=None):
        if not self.api_key:
            raise PlanningFlightProviderConfigurationError(
                "PLANNING_FLIGHT_API_KEY is required for planning API imports."
            )

        req = request.Request(
            self._build_url(
                start_date=start_date,
                end_date=end_date,
                destination_code=destination_code,
            ),
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
            raise PlanningFlightProviderError(
                f"Planning flight API failed with HTTP {exc.code}: {message or exc}"
            ) from exc
        except error.URLError as exc:
            raise PlanningFlightProviderError(f"Planning flight API request failed: {exc}") from exc

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise PlanningFlightProviderError("Planning flight API returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise PlanningFlightProviderError("Planning flight API returned an unexpected payload.")
        return payload

    def fetch_flights(self, *, start_date, end_date, destination_codes=None):
        normalized_destination_codes = _normalize_destination_codes(destination_codes)
        if not normalized_destination_codes:
            payload = self._read_payload(start_date=start_date, end_date=end_date)
            return _extract_records(
                payload,
                origin_iata=self.origin_iata,
                operating_airline_code=self.operating_airline_code,
            )

        if len(normalized_destination_codes) > self.max_calls_per_day:
            raise PlanningFlightProviderError(
                "Planning flight API destination count "
                f"({len(normalized_destination_codes)}) exceeds max_calls_per_day="
                f"{self.max_calls_per_day}."
            )

        records = []
        for destination_code in normalized_destination_codes:
            payload = self._read_payload(
                start_date=start_date,
                end_date=end_date,
                destination_code=destination_code,
            )
            records.extend(
                _extract_records(
                    payload,
                    origin_iata=self.origin_iata,
                    operating_airline_code=self.operating_airline_code,
                )
            )
            if destination_code != normalized_destination_codes[-1]:
                time.sleep(self.min_delay_seconds)
        return records


def _normalize_destination_codes(destination_codes):
    if not destination_codes:
        return []
    normalized_codes = []
    seen = set()
    for raw_code in destination_codes:
        code = str(raw_code or "").strip().upper()
        if len(code) != 3 or code in seen:
            continue
        seen.add(code)
        normalized_codes.append(code)
    return normalized_codes


def _pick_departure_iso_from_leg(leg):
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


def _extract_departure_iso(flight, *, origin_iata):
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
        departure_iso = _pick_departure_iso_from_leg(leg_from_origin)
        if departure_iso:
            return departure_iso

    candidates = []
    for leg in flight_legs:
        departure_iso = _pick_departure_iso_from_leg(leg)
        if departure_iso:
            candidates.append(departure_iso)
    if not candidates:
        return ""
    return min(candidates)


def _extract_records(payload, *, origin_iata, operating_airline_code):
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

        departure_iso = _extract_departure_iso(flight, origin_iata=origin_iata)
        departure_dt = (
            parse_datetime(departure_iso.replace("Z", "+00:00")) if departure_iso else None
        )
        if departure_dt is None or not isinstance(departure_dt, datetime):
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
