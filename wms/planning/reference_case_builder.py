from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

import pandas as pd


def _normalize_flight_number(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    compact = "".join(ch for ch in text if ch.isalnum())
    if compact.isdigit():
        return f"AF{compact}"
    return compact


def _normalize_routing(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.strip("[]")
    parts = [part.strip().upper() for part in text.replace(",", "-").split("-") if part.strip()]
    return "-".join(parts)


def _iso_date(value: Any) -> str:
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return str(value or "")
    return parsed.date().isoformat()


def _format_time_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%H:%M")
    if isinstance(value, time):
        return value.strftime("%H:%M")
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("h", ":")
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text
    return parsed.strftime("%H:%M")


def _clean_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_week_bounds(
    df_benev: pd.DataFrame,
    df_vols: pd.DataFrame,
    planning_df: pd.DataFrame,
) -> tuple[str, str]:
    dates: list[str] = []
    if "Date_dt" in df_benev.columns:
        dates.extend(_iso_date(value) for value in df_benev["Date_dt"].dropna().tolist())

    if "Date_Vol_dt" in df_vols.columns:
        dates.extend(_iso_date(value) for value in df_vols["Date_Vol_dt"].dropna().tolist())
    elif "Date_Vol" in df_vols.columns:
        dates.extend(_iso_date(value) for value in df_vols["Date_Vol"].dropna().tolist())

    if not dates and "Date_Vol" in planning_df.columns:
        dates.extend(_iso_date(value) for value in planning_df["Date_Vol"].dropna().tolist())

    normalized = sorted({value for value in dates if value})
    if not normalized:
        raise ValueError("Unable to infer week bounds from legacy data.")
    return normalized[0], normalized[-1]


def build_reference_case_payload(
    *,
    case_name: str,
    df_be: pd.DataFrame,
    df_param_be: pd.DataFrame | None = None,
    df_param_dest: pd.DataFrame | None = None,
    df_vols: pd.DataFrame,
    df_benev: pd.DataFrame,
    df_param_benev: pd.DataFrame,
    planning_df: pd.DataFrame,
    stats: dict[str, Any],
    week_start: str | None = None,
    week_end: str | None = None,
) -> dict[str, Any]:
    if week_start is None or week_end is None:
        week_start, week_end = _build_week_bounds(df_benev, df_vols, planning_df)
    week_start_ts = pd.Timestamp(week_start)
    week_end_ts = pd.Timestamp(week_end)

    filtered_df_benev = df_benev.copy()
    if "Date_dt" in filtered_df_benev.columns:
        filtered_df_benev = filtered_df_benev[
            filtered_df_benev["Date_dt"].between(week_start_ts, week_end_ts)
        ]

    filtered_df_vols = df_vols.copy()
    if "Date_Vol_dt" in filtered_df_vols.columns:
        filtered_df_vols = filtered_df_vols[
            filtered_df_vols["Date_Vol_dt"].between(week_start_ts, week_end_ts)
        ]

    filtered_planning_df = planning_df.copy()
    if "Date_Vol" in filtered_planning_df.columns:
        planning_dates = pd.to_datetime(
            filtered_planning_df["Date_Vol"],
            errors="coerce",
            dayfirst=True,
        )
        filtered_planning_df = filtered_planning_df[
            planning_dates.between(week_start_ts, week_end_ts)
        ]

    type_priority_map: dict[str, int] = {}
    if df_param_be is not None and not df_param_be.empty:
        for row in df_param_be.to_dict(orient="records"):
            type_label = str(row.get("Type") or "").strip().upper()
            priority_type = _clean_int(row.get("Priorite_Type"))
            if type_label and priority_type is not None:
                type_priority_map[type_label] = priority_type

    shipments = []
    for row in df_be.sort_values(["Priorite", "BE_Numero"], ascending=[False, True]).to_dict(
        orient="records"
    ):
        legacy_type = str(row.get("BE_Type") or "").strip()
        shipments.append(
            {
                "reference": str(row.get("BE_Numero") or "").strip(),
                "shipper_name": str(row.get("BE_Expediteur") or "").strip(),
                "destination_iata": str(row.get("Destination") or "").strip().upper(),
                "priority": _clean_int(row.get("Priorite")) or 0,
                "carton_count": _clean_int(row.get("BE_Nb_Colis")) or 0,
                "equivalent_units": _clean_int(row.get("Equiv_Colis")) or 0,
                "payload": {
                    "legacy_case_name": case_name,
                    "legacy_type": legacy_type,
                    "legacy_destinataire": str(row.get("BE_Destinataire") or "").strip(),
                    "legacy_type_priority": type_priority_map.get(legacy_type.upper()),
                },
            }
        )

    param_benev_records = {}
    for row in df_param_benev.to_dict(orient="records"):
        benev_id = _clean_int(row.get("ID"))
        label = str(row.get("Benevole") or "").strip()
        if benev_id is not None:
            param_benev_records[benev_id] = row
        if label:
            param_benev_records[label] = row

    volunteers = []
    grouped_benev = filtered_df_benev.sort_values(["Date_dt", "Benevole", "ID"]).groupby(
        ["ID", "Benevole"],
        dropna=False,
    )
    for (benev_id_raw, label_raw), group in grouped_benev:
        benev_id = _clean_int(benev_id_raw)
        label = str(label_raw or "").strip()
        param_row = param_benev_records.get(benev_id) or param_benev_records.get(label) or {}
        slots = []
        seen_slots = set()
        for row in group.to_dict(orient="records"):
            slot = {
                "date": _iso_date(row.get("Date_dt") or row.get("Date")),
                "start_time": _format_time_value(
                    row.get("Heure_Arrivee_time") or row.get("Heure_Arrivee")
                ),
                "end_time": _format_time_value(
                    row.get("Heure_Depart_time") or row.get("Heure_Depart")
                ),
            }
            key = (slot["date"], slot["start_time"], slot["end_time"])
            if not slot["date"] or key in seen_slots:
                continue
            seen_slots.add(key)
            slots.append(slot)
        volunteers.append(
            {
                "label": label,
                "max_colis_vol": _clean_int(param_row.get("Max_Colis_Vol")),
                "availability_summary": {
                    "slot_count": len(slots),
                    "slots": slots,
                },
                "payload": {
                    "legacy_id": benev_id,
                    "legacy_phone": str(param_row.get("Telephone") or "").strip(),
                },
            }
        )

    flights = []
    seen_flights = set()
    for row in filtered_df_vols.sort_values(
        ["Date_Vol_dt", "Numero_Vol", "Route_Pos", "IATA"]
    ).to_dict(orient="records"):
        flight_number = _normalize_flight_number(row.get("Numero_Vol"))
        departure_date = _iso_date(row.get("Date_Vol_dt") or row.get("Date_Vol"))
        destination_iata = str(row.get("IATA") or row.get("Destination") or "").strip().upper()
        key = (flight_number, departure_date, destination_iata)
        if not flight_number or not departure_date or not destination_iata or key in seen_flights:
            continue
        seen_flights.add(key)
        routing = _normalize_routing(row.get("Routing"))
        flights.append(
            {
                "flight_number": flight_number,
                "departure_date": departure_date,
                "destination_iata": destination_iata,
                "capacity_units": _clean_int(row.get("Max_Colis")),
                "payload": {
                    "departure_time": _format_time_value(
                        row.get("Heure_Vol_dt") or row.get("Heure_Vol")
                    ),
                    "origin_iata": routing.split("-")[0] if routing else "",
                    "routing": routing,
                    "route_pos": _clean_int(row.get("Route_Pos")) or 1,
                    "legacy_source": str(row.get("Source") or "").strip(),
                },
            }
        )

    destination_rules = []
    if df_param_dest is not None and not df_param_dest.empty:
        seen_destination_rules = set()
        for row in df_param_dest.to_dict(orient="records"):
            iata_code = str(row.get("Dest_IATA") or "").strip().upper()
            if not iata_code or iata_code in seen_destination_rules:
                continue
            seen_destination_rules.add(iata_code)
            destination_rules.append(
                {
                    "iata_code": iata_code,
                    "city": str(row.get("Dest_Ville") or iata_code).strip(),
                    "country": str(row.get("Dest_Pays") or "").strip(),
                    "weekly_frequency": _clean_int(row.get("Freq_Semaine")),
                    "max_cartons_per_flight": _clean_int(row.get("Max_Colis_Par_Vol")),
                    "priority": 0,
                }
            )

    expected_assignments = []
    for row in filtered_planning_df.sort_values(["Date_Vol", "Numero_Vol", "BE_Numero"]).to_dict(
        orient="records"
    ):
        expected_assignments.append(
            [
                str(row.get("BE_Numero") or "").strip(),
                _normalize_flight_number(row.get("Numero_Vol")),
                str(row.get("Benevole") or "").strip(),
            ]
        )

    expected_result = {
        "assignment_count": len(expected_assignments),
    }
    legacy_total_flights = _clean_int(stats.get("nb_vols_total"))
    if legacy_total_flights == len(flights):
        for source_key, target_key in (
            ("nb_vols_total", "nb_vols_total"),
            ("nb_vols_sans_be_compatible", "nb_vols_sans_be_compatible"),
            ("nb_vols_sans_benevole_compatible", "nb_vols_sans_benevole_compatible"),
            ("nb_vols_sans_compatibilite_complete", "nb_vols_sans_compatibilite_complete"),
        ):
            value = _clean_int(stats.get(source_key))
            if value is not None:
                expected_result[target_key] = value

    return {
        "case_name": case_name,
        "week_start": week_start,
        "week_end": week_end,
        "shipments": shipments,
        "volunteers": volunteers,
        "flights": flights,
        "destination_rules": destination_rules,
        "expected_assignments": expected_assignments,
        "expected_result": expected_result,
    }
