
def _row_is_empty(row):
    for value in row.values():
        if value is None:
            continue
        if str(value).strip():
            return False
    return True
