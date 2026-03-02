from functools import lru_cache

from openpyxl.utils.cell import coordinate_from_string, get_column_letter


@lru_cache(maxsize=1)
def build_column_choices():
    return [get_column_letter(index) for index in range(1, 16385)]


def worksheet_row_choices(worksheet):
    max_row = max(1, int(getattr(worksheet, "max_row", 1) or 1))
    return list(range(1, max_row + 1))


def normalize_cell_ref(worksheet, cell_ref):
    column, row = coordinate_from_string((cell_ref or "").strip().upper())
    normalized_ref = f"{column}{row}"
    for merged_range in worksheet.merged_cells.ranges:
        if normalized_ref in merged_range:
            anchor = merged_range.start_cell.coordinate
            return anchor, str(merged_range)
    return normalized_ref, ""
