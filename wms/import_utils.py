import codecs
import csv
import io
import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO

try:
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover - optional dependency at runtime
    load_workbook = None

try:
    import xlrd
except ImportError:  # pragma: no cover - optional dependency at runtime
    xlrd = None


TRUE_VALUES = {"true", "1", "yes", "y", "oui", "o", "vrai"}
FALSE_VALUES = {"false", "0", "no", "n", "non", "faux"}


def normalize_header(value):
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _guess_utf16_encoding(data):
    sample = data[:2000]
    if len(sample) < 4:
        return None
    even_zeros = sum(1 for idx in range(0, len(sample), 2) if sample[idx] == 0)
    odd_zeros = sum(1 for idx in range(1, len(sample), 2) if sample[idx] == 0)
    if even_zeros > odd_zeros * 2:
        return "utf-16-be"
    if odd_zeros > even_zeros * 2:
        return "utf-16-le"
    return None


def decode_text(data):
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    if not isinstance(data, (bytes, bytearray)):
        return str(data)
    data = bytes(data)
    if not data:
        return ""

    for bom, encoding in (
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
        (codecs.BOM_UTF32_LE, "utf-32-le"),
        (codecs.BOM_UTF32_BE, "utf-32-be"),
    ):
        if data.startswith(bom):
            return data.decode(encoding)

    if b"\x00" in data[:2000]:
        guessed = _guess_utf16_encoding(data)
        if guessed:
            return data.decode(guessed)
        for encoding in ("utf-16", "utf-32"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue

    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def iter_csv_rows(data, delimiter=";"):
    text = decode_text(data)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    for row in reader:
        normalized = {normalize_header(k): v for k, v in row.items() if k}
        yield normalized


def iter_xlsx_rows(data):
    if load_workbook is None:
        raise ValueError("openpyxl is required to import Excel files.")
    workbook = load_workbook(BytesIO(data), data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        headers = next(rows)
    except StopIteration as exc:
        raise ValueError("Excel file is empty.") from exc
    normalized_headers = [normalize_header(str(h or "")) for h in headers]
    for row in rows:
        entry = {}
        for header, value in zip(normalized_headers, row):
            if not header:
                continue
            entry[header] = value
        yield entry


def iter_xls_rows(data):
    if xlrd is None:
        raise ValueError("xlrd is required to import .xls files.")
    workbook = xlrd.open_workbook(file_contents=data)
    sheet = workbook.sheet_by_index(0)
    if sheet.nrows == 0:
        raise ValueError("Excel file is empty.")
    headers = [normalize_header(cell.value) for cell in sheet.row(0)]
    for row_index in range(1, sheet.nrows):
        entry = {}
        for col_index, header in enumerate(headers):
            if not header:
                continue
            entry[header] = sheet.cell_value(row_index, col_index)
        yield entry


def iter_import_rows(data, extension):
    if extension == ".csv":
        return iter_csv_rows(data)
    if extension in {".xlsx", ".xlsm"}:
        return iter_xlsx_rows(data)
    if extension == ".xls":
        return iter_xls_rows(data)
    raise ValueError("Format de fichier non supporte.")


def get_value(row, *keys):
    for key in keys:
        if key in row:
            return row.get(key)
    return None


def parse_str(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_decimal(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value}") from exc


def parse_int(value):
    decimal_value = parse_decimal(value)
    if decimal_value is None:
        return None
    return int(decimal_value.to_integral_value(rounding=ROUND_HALF_UP))


def parse_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def parse_tokens(value):
    if not value:
        return []
    tokens = []
    for token in re.split(r"[|,]", str(value)):
        name = token.strip()
        if name:
            tokens.append(name)
    return tokens
