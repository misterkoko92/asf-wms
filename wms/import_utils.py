import codecs
import csv
import io
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from io import BytesIO

try:
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover - optional dependency at runtime
    load_workbook = None

try:
    import xlrd
except ImportError:  # pragma: no cover - optional dependency at runtime
    xlrd = None

try:
    import pdfplumber
except ImportError:  # pragma: no cover - optional dependency at runtime
    pdfplumber = None


TRUE_VALUES = {"true", "1", "yes", "y", "oui", "o", "vrai"}
FALSE_VALUES = {"false", "0", "no", "n", "non", "faux"}
PDF_WORD_ROW_TOLERANCE = 3
PDF_WORD_COLUMN_TOLERANCE = 48
PDF_PREVIEW_LINE_LIMIT = 2
PDF_PREVIEW_TEXT_LIMIT = 160


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
    if not isinstance(data, bytes | bytearray):
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

    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
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
    raise ValueError("Format de fichier non supporté.")


def _sanitize_headers(headers, row_length=None):
    cleaned = [str(value or "").strip() for value in (headers or [])]
    if row_length is None:
        row_length = len(cleaned)
    if not cleaned or all(not value for value in cleaned):
        return [f"Colonne {idx + 1}" for idx in range(row_length)]
    while len(cleaned) < row_length:
        cleaned.append("")
    normalized = []
    for idx, value in enumerate(cleaned, start=1):
        normalized.append(value or f"Colonne {idx}")
    return normalized


def _coerce_cell(value):
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
    return str(value).strip()


def _normalize_pdf_row(row):
    return [_coerce_cell(cell) for cell in (row or [])]


def _normalize_pdf_rows(rows):
    return [_normalize_pdf_row(row) for row in (rows or []) if row is not None]


def _split_pdf_text_line(line):
    raw = str(line or "").strip()
    if not raw:
        return []
    for pattern in (r"\s*\|\s*", r"\s*;\s*", r"\t+", r"\s{2,}"):
        cells = [_coerce_cell(cell) for cell in re.split(pattern, raw)]
        cells = [cell for cell in cells if cell]
        if len(cells) > 1:
            return cells
    return [_coerce_cell(raw)]


def _build_pdf_preview_text(text_lines):
    cleaned_lines = [_coerce_cell(line) for line in (text_lines or []) if _coerce_cell(line)]
    if not cleaned_lines:
        return ""
    preview = " | ".join(cleaned_lines[:PDF_PREVIEW_LINE_LIMIT])
    if len(preview) <= PDF_PREVIEW_TEXT_LIMIT:
        return preview
    return preview[: PDF_PREVIEW_TEXT_LIMIT - 1].rstrip() + "…"


def _is_usable_pdf_rows(rows):
    normalized_rows = _normalize_pdf_rows(rows)
    if len(normalized_rows) < 2:
        return False
    if len([cell for cell in normalized_rows[0] if cell]) < 2:
        return False
    return any(len([cell for cell in row if cell]) >= 2 for row in normalized_rows[1:])


def _extract_pdf_rows_from_text_lines(text_lines):
    rows = [_split_pdf_text_line(line) for line in (text_lines or [])]
    rows = [row for row in rows if row]
    if not _is_usable_pdf_rows(rows):
        return []
    return rows


def _group_pdf_words_by_row(words):
    grouped_rows = []
    for word in sorted(words, key=lambda item: (float(item["top"]), float(item["x0"]))):
        top = float(word["top"])
        current = None
        for row in grouped_rows:
            if abs(row["top"] - top) <= PDF_WORD_ROW_TOLERANCE:
                current = row
                break
        if current is None:
            current = {"top": top, "words": []}
            grouped_rows.append(current)
        current["words"].append(word)
        current["top"] = sum(float(existing["top"]) for existing in current["words"]) / len(
            current["words"]
        )
    return grouped_rows


def _derive_pdf_column_anchors(grouped_rows):
    anchors = []
    for row in grouped_rows:
        for word in sorted(row["words"], key=lambda item: float(item["x0"])):
            x0 = float(word["x0"])
            anchor_index = None
            for idx, anchor in enumerate(anchors):
                if abs(anchor - x0) <= PDF_WORD_COLUMN_TOLERANCE:
                    anchor_index = idx
                    break
            if anchor_index is None:
                anchors.append(x0)
            else:
                anchors[anchor_index] = (anchors[anchor_index] + x0) / 2
    return sorted(anchors)


def _extract_pdf_rows_from_words(page):
    extract_words = getattr(page, "extract_words", None)
    if not callable(extract_words):
        return []
    raw_words = extract_words() or []
    words = []
    for word in raw_words:
        text = _coerce_cell(word.get("text"))
        if not text or "x0" not in word or "top" not in word:
            continue
        words.append({"text": text, "x0": float(word["x0"]), "top": float(word["top"])})
    if not words:
        return []

    grouped_rows = _group_pdf_words_by_row(words)
    anchors = _derive_pdf_column_anchors(grouped_rows)
    if len(anchors) < 2:
        return []

    rows = []
    for row in sorted(grouped_rows, key=lambda item: item["top"]):
        cells = [""] * len(anchors)
        last_index = 0
        for word in sorted(row["words"], key=lambda item: item["x0"]):
            candidate_indexes = range(last_index, len(anchors))
            index = min(candidate_indexes, key=lambda idx: abs(anchors[idx] - word["x0"]))
            last_index = index
            cells[index] = f"{cells[index]} {word['text']}".strip()
        last_filled = max((idx for idx, value in enumerate(cells) if value), default=-1)
        if last_filled >= 0:
            rows.append(cells[: last_filled + 1])
    if not _is_usable_pdf_rows(rows):
        return []
    return rows


def _select_pdf_page_rows(page):
    table = page.extract_table()
    table_rows = _normalize_pdf_rows(table)
    if _is_usable_pdf_rows(table_rows):
        return table_rows, "table"

    text_lines = [line for line in (page.extract_text() or "").splitlines() if line.strip()]
    text_rows = _extract_pdf_rows_from_text_lines(text_lines)
    if text_rows:
        return text_rows, "text"

    word_rows = _extract_pdf_rows_from_words(page)
    if word_rows:
        return word_rows, "words"

    return [], "none"


def _resolve_pdf_page_numbers(total_pages, page_numbers=None, page_start=None, page_end=None):
    if page_numbers is not None:
        numbers = []
        for value in page_numbers:
            number = parse_int(value)
            if number is None or number < 1 or number > total_pages:
                raise ValueError("Plage de pages PDF invalide.")
            if number not in numbers:
                numbers.append(number)
        if not numbers:
            raise ValueError("Plage de pages PDF invalide.")
        return numbers

    start = page_start or 1
    end = page_end or total_pages
    if start < 1 or end < start or end > total_pages:
        raise ValueError("Plage de pages PDF invalide.")
    return list(range(start, end + 1))


def _extract_csv_table(data):
    text = decode_text(data)
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("CSV vide.")
    delimiter = ";"
    if "," in lines[0] and ";" not in lines[0]:
        delimiter = ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise ValueError("CSV vide.") from exc
    rows = [[_coerce_cell(cell) for cell in row] for row in reader]
    return _sanitize_headers(headers), rows


def _extract_xlsx_table(data, sheet_name=None, header_row=1):
    if load_workbook is None:
        raise ValueError("openpyxl est requis pour importer .xlsx/.xlsm.")
    workbook = load_workbook(BytesIO(data), data_only=True)
    if sheet_name:
        if sheet_name not in workbook.sheetnames:
            workbook.close()
            raise ValueError(f"Feuille inconnue: {sheet_name}")
        sheet = workbook[sheet_name]
    else:
        sheet = workbook.active
    if header_row < 1:
        workbook.close()
        raise ValueError("Ligne des titres invalide (doit etre >= 1).")
    rows = sheet.iter_rows(values_only=True)
    headers = None
    data_rows = []
    for index, row in enumerate(rows, start=1):
        if index < header_row:
            continue
        if headers is None:
            headers = _sanitize_headers(row)
            continue
        data_rows.append([_coerce_cell(cell) for cell in row])
    if headers is None:
        workbook.close()
        raise ValueError("Excel vide.")
    workbook.close()
    return headers, data_rows


def _extract_xls_table(data, sheet_name=None, header_row=1):
    if xlrd is None:
        raise ValueError("xlrd est requis pour importer .xls.")
    workbook = xlrd.open_workbook(file_contents=data)
    if sheet_name:
        try:
            sheet = workbook.sheet_by_name(sheet_name)
        except xlrd.biffh.XLRDError as exc:
            raise ValueError(f"Feuille inconnue: {sheet_name}") from exc
    else:
        sheet = workbook.sheet_by_index(0)
    if sheet.nrows == 0:
        raise ValueError("Excel vide.")
    if header_row < 1 or header_row > sheet.nrows:
        raise ValueError("Ligne des titres invalide (hors limites).")
    header_index = header_row - 1
    headers = [sheet.cell_value(header_index, col) for col in range(sheet.ncols)]
    headers = _sanitize_headers(headers, row_length=sheet.ncols)
    rows = []
    for row_index in range(header_index + 1, sheet.nrows):
        row = [sheet.cell_value(row_index, col) for col in range(sheet.ncols)]
        rows.append([_coerce_cell(cell) for cell in row])
    return headers, rows


def _extract_pdf_table(data, page_start=None, page_end=None, page_numbers=None):
    if pdfplumber is None:
        raise ValueError("pdfplumber est requis pour importer des PDF texte.")
    with pdfplumber.open(BytesIO(data)) as pdf:
        total_pages = len(pdf.pages)
        page_sequence = _resolve_pdf_page_numbers(
            total_pages,
            page_numbers=page_numbers,
            page_start=page_start,
            page_end=page_end,
        )
        tables = []
        for page_number in page_sequence:
            rows, _strategy = _select_pdf_page_rows(pdf.pages[page_number - 1])
            if rows:
                tables.append(rows)
        if not tables:
            raise ValueError("PDF scanne non supporte (aucun texte detecte).")
    headers = None
    rows = []
    for table in tables:
        normalized_table = _normalize_pdf_rows(table)
        if not normalized_table:
            continue
        if headers is None:
            headers = normalized_table[0]
            rows.extend(normalized_table[1:])
        else:
            rows.extend(
                normalized_table[1:] if normalized_table[0] == headers else normalized_table
            )
    if headers is None:
        raise ValueError("Impossible d'extraire un tableau du PDF.")
    max_len = max(len(headers), *(len(row) for row in rows)) if rows else len(headers)
    headers = _sanitize_headers(headers, row_length=max_len)
    normalized_rows = []
    for row in rows:
        padded = list(row) + [""] * (max_len - len(row))
        normalized_rows.append([_coerce_cell(cell) for cell in padded])
    return headers, normalized_rows


def analyze_pdf_listing(data):
    if pdfplumber is None:
        raise ValueError("pdfplumber est requis pour importer des PDF texte.")
    with pdfplumber.open(BytesIO(data)) as pdf:
        total_pages = len(pdf.pages)
        page_diagnostics = []
        extractable_pages = []
        for number, page in enumerate(pdf.pages, start=1):
            text_lines = [line for line in (page.extract_text() or "").splitlines() if line.strip()]
            has_text = bool(text_lines)
            table = page.extract_table()
            has_table = table is not None and len(table) > 0
            rows, extraction_strategy = _select_pdf_page_rows(page)
            extractable = bool(rows)
            if extractable:
                extractable_pages.append(number)
            column_count = max((len(row or []) for row in rows), default=0)
            page_diagnostics.append(
                {
                    "number": number,
                    "has_text": has_text,
                    "has_table": has_table,
                    "extractable": extractable,
                    "line_count": len(rows) if rows else len(text_lines),
                    "column_count": column_count,
                    "extraction_strategy": extraction_strategy,
                    "preview_text": _build_pdf_preview_text(text_lines),
                }
            )

    if not extractable_pages:
        mode = "scan"
    elif len(extractable_pages) == total_pages:
        mode = "text"
    else:
        mode = "mixed"

    recommended_pages = {
        "mode": "all",
        "start": None,
        "end": None,
        "pages": list(extractable_pages),
    }
    if extractable_pages and len(extractable_pages) != total_pages:
        recommended_pages = {
            "mode": "detected",
            "start": extractable_pages[0],
            "end": extractable_pages[-1],
            "pages": list(extractable_pages),
        }

    return {
        "total_pages": total_pages,
        "mode": mode,
        "pages": page_diagnostics,
        "extractable_pages": extractable_pages,
        "recommended_pages": recommended_pages,
    }


def extract_tabular_data(data, extension, sheet_name=None, header_row=1, pdf_pages=None):
    if extension == ".csv":
        return _extract_csv_table(data)
    if extension in {".xlsx", ".xlsm"}:
        return _extract_xlsx_table(data, sheet_name=sheet_name, header_row=header_row)
    if extension == ".xls":
        return _extract_xls_table(data, sheet_name=sheet_name, header_row=header_row)
    if extension == ".pdf":
        page_start = None
        page_end = None
        page_numbers = None
        if pdf_pages:
            if isinstance(pdf_pages, list):
                page_numbers = pdf_pages
            else:
                page_start, page_end = pdf_pages
        return _extract_pdf_table(
            data,
            page_start=page_start,
            page_end=page_end,
            page_numbers=page_numbers,
        )
    raise ValueError("Format de fichier non supporté.")


def get_pdf_page_count(data):
    if pdfplumber is None:
        raise ValueError("pdfplumber est requis pour importer des PDF texte.")
    with pdfplumber.open(BytesIO(data)) as pdf:
        return len(pdf.pages)


def list_excel_sheets(data, extension):
    if extension in {".xlsx", ".xlsm"}:
        if load_workbook is None:
            raise ValueError("openpyxl est requis pour importer .xlsx/.xlsm.")
        workbook = load_workbook(BytesIO(data), data_only=True)
        sheet_names = list(workbook.sheetnames)
        workbook.close()
        return sheet_names
    if extension == ".xls":
        if xlrd is None:
            raise ValueError("xlrd est requis pour importer .xls.")
        workbook = xlrd.open_workbook(file_contents=data)
        return workbook.sheet_names()
    return []


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


def _normalize_decimal_text(value):
    original = unicodedata.normalize("NFKC", str(value).strip())
    if not original:
        return ""
    text = re.sub(r"[^\d,.\-+]", "", original)
    if not re.search(r"\d", text):
        return original

    sign = ""
    if text[0] in "+-":
        sign = text[0]
        text = text[1:]
    text = text.replace("+", "").replace("-", "")

    last_comma = text.rfind(",")
    last_dot = text.rfind(".")
    if last_comma != -1 and last_dot != -1:
        if last_comma > last_dot:
            text = text.replace(".", "")
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    elif text.count(",") > 1:
        parts = text.split(",")
        text = "".join(parts[:-1]) + "." + parts[-1]
    elif text.count(".") > 1:
        parts = text.split(".")
        text = "".join(parts[:-1]) + "." + parts[-1]
    else:
        text = text.replace(",", ".")
    return f"{sign}{text}"


def parse_decimal(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float):
        return Decimal(str(value))
    text = _normalize_decimal_text(value)
    if not text:
        return None
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
