from datetime import date, datetime


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

        value = _resolve_source_value(payload, source_key)
        if required and _is_missing(value):
            raise PrintPackMappingError(
                f"Missing required mapping value for {worksheet_name}!{cell_ref} ({source_key})"
            )

        workbook[worksheet_name][cell_ref].value = _apply_transform(value, transform)
    return workbook
