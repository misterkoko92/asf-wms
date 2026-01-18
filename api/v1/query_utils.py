from decimal import Decimal


def parse_bool(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "oui"}:
        return True
    if text in {"0", "false", "no", "n", "non"}:
        return False
    return None


def parse_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_decimal(value):
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except (TypeError, ValueError, ArithmeticError):
        return None
