import re
import unicodedata

NON_PRODUCT_LISTING_PATTERNS = (
    "TOTAL",
    "SOUS-TOTAL",
    "VALORISATION",
    "FRAIS DE TRANSPORT",
    "TRANSPORT",
    "PORT",
    "MANUTENTION",
)

REPEATED_HEADER_PATTERNS = (
    "EAN",
    "DESIGNATION",
    "PRIX HT",
    "PU HT",
    "QTE",
    "QUANTITE",
    "TOTAL HT",
)


def normalize_listing_search_text(value):
    text = str(value or "").strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"\s+", " ", text)
    return text.strip().upper()


def _iter_row_values(row):
    if isinstance(row, dict):
        return list(row.values())
    return list(row or [])


def is_non_product_listing_row(row):
    values = [
        normalize_listing_search_text(value)
        for value in _iter_row_values(row)
        if normalize_listing_search_text(value)
    ]
    if not values:
        return False

    joined = " | ".join(values)
    if any(pattern in joined for pattern in NON_PRODUCT_LISTING_PATTERNS):
        return True

    repeated_header_hits = sum(1 for pattern in REPEATED_HEADER_PATTERNS if pattern in values)
    return repeated_header_hits >= 3
