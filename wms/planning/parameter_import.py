from pathlib import Path

from wms.import_utils import (
    extract_tabular_data,
    get_value,
    normalize_header,
    parse_bool,
    parse_int,
    parse_str,
)
from wms.models import Destination, PlanningDestinationRule, PlanningParameterSet

PARAM_DEST_SHEET_NAME = "ParamDest"


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


def _resolve_destination(row):
    iata_code = parse_str(
        get_value(
            row,
            "destination_iata",
            "iata",
            "iata_code",
            "code_iata",
        )
    )
    if not iata_code:
        raise ValueError("Chaque ligne ParamDest doit contenir un code IATA.")
    destination = Destination.objects.filter(iata_code__iexact=iata_code).first()
    if destination is None:
        raise ValueError(f"Destination inconnue pour le code IATA {iata_code}.")
    return destination


def _apply_destination_row(*, parameter_set, row):
    destination = _resolve_destination(row)
    label = parse_str(get_value(row, "libelle", "label", "nom")) or destination.city
    weekly_frequency = parse_int(get_value(row, "frequence_hebdo", "frequence", "weekly_frequency"))
    max_cartons_per_flight = parse_int(
        get_value(row, "max_colis_vol", "max_colis_flight", "max_cartons_per_flight")
    )
    priority = parse_int(get_value(row, "priorite", "priority")) or 0
    is_active = parse_bool(get_value(row, "actif", "is_active"))
    notes = parse_str(get_value(row, "notes", "commentaire", "commentaires")) or ""

    PlanningDestinationRule.objects.update_or_create(
        parameter_set=parameter_set,
        destination=destination,
        defaults={
            "label": label,
            "weekly_frequency": weekly_frequency,
            "max_cartons_per_flight": max_cartons_per_flight,
            "priority": priority,
            "is_active": True if is_active is None else is_active,
            "notes": notes,
        },
    )


def import_destination_rules(*, workbook_path, parameter_set_name, created_by=None):
    path = Path(workbook_path)
    data = path.read_bytes()
    headers, rows = extract_tabular_data(
        data,
        path.suffix.lower(),
        sheet_name=PARAM_DEST_SHEET_NAME,
    )
    entries = _rows_from_headers_and_values(headers, rows)
    parameter_set, _created = PlanningParameterSet.objects.update_or_create(
        name=parameter_set_name,
        defaults={"created_by": created_by},
    )
    parameter_set.destination_rules.all().delete()
    for row in entries:
        if not any(
            (value or "").strip() if isinstance(value, str) else value for value in row.values()
        ):
            continue
        _apply_destination_row(parameter_set=parameter_set, row=row)
    return parameter_set
