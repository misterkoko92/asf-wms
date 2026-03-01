from datetime import date, datetime
from openpyxl.cell.cell import MergedCell
from openpyxl.utils.cell import coordinate_from_string


class PrintPackMappingError(ValueError):
    """Raised when an Excel mapping cannot be applied safely."""


def _mapping_get(mapping, key, default=None):
    if isinstance(mapping, dict):
        return mapping.get(key, default)
    return getattr(mapping, key, default)


def _resolve_source_value(payload, source_key):
    current = payload
    for segment in (source_key or "").split("."):
        segment = segment.strip()
        if not segment:
            continue
        if isinstance(current, dict):
            if segment not in current:
                return None
            current = current[segment]
            continue
        if hasattr(current, segment):
            current = getattr(current, segment)
            continue
        return None
    return current


def _split_repeating_source_key(source_key):
    key = (source_key or "").strip()
    if "[]" not in key:
        return None, None
    before, after = key.split("[]", 1)
    return before.rstrip("."), after.lstrip(".")


def _iter_repeating_values(payload, source_key):
    list_key, item_key = _split_repeating_source_key(source_key)
    if not list_key:
        return []
    rows = _resolve_source_value(payload, list_key)
    if not isinstance(rows, (list, tuple)):
        return []
    if not item_key:
        return list(rows)
    return [_resolve_source_value(row, item_key) for row in rows]


def _resolve_target_cell(worksheet, cell_ref):
    cell = worksheet[cell_ref]
    if isinstance(cell, MergedCell):
        for merged_range in worksheet.merged_cells.ranges:
            if cell.coordinate in merged_range:
                return worksheet[merged_range.start_cell.coordinate]
    return cell


def _is_missing(value):
    return value is None or (isinstance(value, str) and value.strip() == "")


def _apply_transform(value, transform):
    transform_key = (transform or "").strip().lower()
    if _is_missing(value):
        return ""
    if transform_key == "upper":
        return str(value).upper()
    if transform_key == "date_fr":
        if isinstance(value, (date, datetime)):
            return value.strftime("%d/%m/%Y")
        return str(value)
    return value


def fill_workbook_cells(workbook, mappings, payload):
    for mapping in mappings:
        worksheet_name = _mapping_get(mapping, "worksheet_name", "")
        cell_ref = _mapping_get(mapping, "cell_ref", "")
        source_key = _mapping_get(mapping, "source_key", "")
        transform = _mapping_get(mapping, "transform", "")
        required = bool(_mapping_get(mapping, "required", False))

        if worksheet_name not in workbook.sheetnames:
            raise PrintPackMappingError(f"Unknown worksheet: {worksheet_name}")
        worksheet = workbook[worksheet_name]

        if "[]" in source_key:
            column, base_row = coordinate_from_string(cell_ref)
            values = _iter_repeating_values(payload, source_key)
            if required and not values:
                raise PrintPackMappingError(
                    f"Missing required mapping value for {worksheet_name}!{cell_ref} ({source_key})"
                )
            for idx, raw_value in enumerate(values):
                if required and _is_missing(raw_value):
                    raise PrintPackMappingError(
                        f"Missing required mapping value for {worksheet_name}!{column}{base_row + idx} ({source_key})"
                    )
                target_cell = _resolve_target_cell(
                    worksheet,
                    f"{column}{base_row + idx}",
                )
                target_cell.value = _apply_transform(raw_value, transform)
            continue

        value = _resolve_source_value(payload, source_key)
        if required and _is_missing(value):
            raise PrintPackMappingError(
                f"Missing required mapping value for {worksheet_name}!{cell_ref} ({source_key})"
            )

        target_cell = _resolve_target_cell(worksheet, cell_ref)
        target_cell.value = _apply_transform(value, transform)
    return workbook
