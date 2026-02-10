
def _value_is_blank(value):
    if value is None:
        return True
    return not str(value).strip()


def _row_is_empty(row):
    for value in row.values():
        if not _value_is_blank(value):
            return False
    return True
