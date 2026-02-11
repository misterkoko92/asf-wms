from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from wms import import_utils


class _FakeWorkbook:
    def __init__(self, *, active=None, sheetnames=None, by_name=None):
        self.active = active
        self.sheetnames = sheetnames or []
        self._by_name = by_name or {}
        self.closed = False

    def __getitem__(self, key):
        return self._by_name[key]

    def close(self):
        self.closed = True


class _FakeSheetRows:
    def __init__(self, rows):
        self._rows = list(rows)

    def iter_rows(self, values_only=True):
        return iter(self._rows)


class _FakeXlsCell:
    def __init__(self, value):
        self.value = value


class _FakeXlsSheet:
    def __init__(self, rows):
        self._rows = rows
        self.nrows = len(rows)
        self.ncols = len(rows[0]) if rows else 0

    def row(self, index):
        return [_FakeXlsCell(value) for value in self._rows[index]]

    def cell_value(self, row_index, col_index):
        return self._rows[row_index][col_index]


class _FakePdf:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _TruthyThenFalsyTable(list):
    def __init__(self, rows):
        super().__init__(rows)
        self._calls = 0

    def __bool__(self):
        self._calls += 1
        return self._calls == 1


class ImportUtilsTests(SimpleTestCase):
    def test_normalize_header_and_guess_utf16_encoding(self):
        self.assertEqual(import_utils.normalize_header("  Nom Produit  "), "nom_produit")
        self.assertEqual(import_utils.normalize_header("CategOrie-1"), "categorie_1")
        self.assertEqual(import_utils._guess_utf16_encoding(b"\x00A\x00B\x00C\x00D"), "utf-16-be")
        self.assertEqual(import_utils._guess_utf16_encoding(b"A\x00B\x00C\x00D\x00"), "utf-16-le")
        self.assertIsNone(import_utils._guess_utf16_encoding(b"ab"))
        self.assertIsNone(import_utils._guess_utf16_encoding(b"\x00\x00AA"))

    def test_decode_text_handles_none_strings_and_various_bytes(self):
        self.assertEqual(import_utils.decode_text(None), "")
        self.assertEqual(import_utils.decode_text("abc"), "abc")
        self.assertEqual(import_utils.decode_text(123), "123")
        self.assertEqual(import_utils.decode_text(b""), "")
        self.assertEqual(import_utils.decode_text(b"\xef\xbb\xbfhello"), "hello")

        utf16_text = "a,b\n1,2\n".encode("utf-16-le")
        self.assertEqual(import_utils.decode_text(utf16_text), "a,b\n1,2\n")

        cp1252_text = "café".encode("cp1252")
        self.assertEqual(import_utils.decode_text(cp1252_text), "café")

        mixed_nulls = b"\x00\x00AAB"
        self.assertEqual(import_utils.decode_text(mixed_nulls), "\x00\x00AAB")

        cp1252_invalid_but_latin1_valid = b"\x81"
        self.assertEqual(
            import_utils.decode_text(cp1252_invalid_but_latin1_valid),
            "\x81",
        )

    def test_iter_csv_rows_normalizes_keys(self):
        rows = list(import_utils.iter_csv_rows("Nom Produit;Quantité\nMask;3\n"))
        self.assertEqual(rows, [{"nom_produit": "Mask", "quantite": "3"}])

    def test_iter_xlsx_rows_handles_missing_dependency_empty_and_success(self):
        with mock.patch("wms.import_utils.load_workbook", None):
            with self.assertRaisesMessage(ValueError, "openpyxl is required"):
                list(import_utils.iter_xlsx_rows(b"data"))

        empty_sheet = _FakeSheetRows([])
        empty_workbook = _FakeWorkbook(active=empty_sheet)
        with mock.patch("wms.import_utils.load_workbook", return_value=empty_workbook):
            with self.assertRaisesMessage(ValueError, "Excel file is empty."):
                list(import_utils.iter_xlsx_rows(b"data"))

        sheet = _FakeSheetRows(
            [
                ("Nom", "Quantite", None),
                ("Mask", 2, "x"),
                ("Gloves", 5, "y"),
            ]
        )
        workbook = _FakeWorkbook(active=sheet)
        with mock.patch("wms.import_utils.load_workbook", return_value=workbook):
            rows = list(import_utils.iter_xlsx_rows(b"data"))
        self.assertEqual(
            rows,
            [
                {"nom": "Mask", "quantite": 2},
                {"nom": "Gloves", "quantite": 5},
            ],
        )

    def test_iter_xls_rows_handles_missing_dependency_empty_and_success(self):
        with mock.patch("wms.import_utils.xlrd", None):
            with self.assertRaisesMessage(ValueError, "xlrd is required"):
                list(import_utils.iter_xls_rows(b"data"))

        empty_sheet = _FakeXlsSheet([])
        workbook = SimpleNamespace(sheet_by_index=lambda idx: empty_sheet)
        fake_xlrd = SimpleNamespace(open_workbook=lambda **kwargs: workbook)
        with mock.patch("wms.import_utils.xlrd", fake_xlrd):
            with self.assertRaisesMessage(ValueError, "Excel file is empty."):
                list(import_utils.iter_xls_rows(b"data"))

        sheet = _FakeXlsSheet([["Nom", "Quantite"], ["Mask", 3], ["Gloves", 4]])
        workbook = SimpleNamespace(sheet_by_index=lambda idx: sheet)
        fake_xlrd = SimpleNamespace(open_workbook=lambda **kwargs: workbook)
        with mock.patch("wms.import_utils.xlrd", fake_xlrd):
            rows = list(import_utils.iter_xls_rows(b"data"))
        self.assertEqual(
            rows,
            [
                {"nom": "Mask", "quantite": 3},
                {"nom": "Gloves", "quantite": 4},
            ],
        )

        sheet_with_blank_header = _FakeXlsSheet([["Nom", ""], ["Mask", 3]])
        workbook = SimpleNamespace(sheet_by_index=lambda idx: sheet_with_blank_header)
        fake_xlrd = SimpleNamespace(open_workbook=lambda **kwargs: workbook)
        with mock.patch("wms.import_utils.xlrd", fake_xlrd):
            rows = list(import_utils.iter_xls_rows(b"data"))
        self.assertEqual(rows, [{"nom": "Mask"}])

    def test_iter_import_rows_dispatches_and_rejects_unknown_extension(self):
        with mock.patch("wms.import_utils.iter_csv_rows", return_value=iter([{"a": 1}])) as csv_mock:
            rows = list(import_utils.iter_import_rows(b"x", ".csv"))
        self.assertEqual(rows, [{"a": 1}])
        csv_mock.assert_called_once()

        with mock.patch("wms.import_utils.iter_xlsx_rows", return_value=iter([{"x": 1}])) as xlsx_mock:
            rows = list(import_utils.iter_import_rows(b"x", ".xlsx"))
        self.assertEqual(rows, [{"x": 1}])
        xlsx_mock.assert_called_once()

        with mock.patch("wms.import_utils.iter_xls_rows", return_value=iter([{"x": 2}])) as xls_mock:
            rows = list(import_utils.iter_import_rows(b"x", ".xls"))
        self.assertEqual(rows, [{"x": 2}])
        xls_mock.assert_called_once()

        with self.assertRaisesMessage(ValueError, "Format de fichier non supporté."):
            import_utils.iter_import_rows(b"x", ".pdf")

    def test_sanitize_headers_and_coerce_cell(self):
        self.assertEqual(import_utils._sanitize_headers([], row_length=2), ["Colonne 1", "Colonne 2"])
        self.assertEqual(
            import_utils._sanitize_headers(["Nom", ""], row_length=3),
            ["Nom", "Colonne 2", "Colonne 3"],
        )
        self.assertEqual(import_utils._coerce_cell(None), "")
        self.assertEqual(import_utils._coerce_cell(3.0), "3")
        self.assertEqual(import_utils._coerce_cell("  x  "), "x")

    def test_extract_csv_table_handles_empty_and_comma_delimiter(self):
        with self.assertRaisesMessage(ValueError, "CSV vide."):
            import_utils._extract_csv_table(" \n ")

        headers, rows = import_utils._extract_csv_table("name,qty\nMask,3\n")
        self.assertEqual(headers, ["name", "qty"])
        self.assertEqual(rows, [["Mask", "3"]])

        with mock.patch("wms.import_utils.csv.reader", return_value=iter(())):
            with self.assertRaisesMessage(ValueError, "CSV vide."):
                import_utils._extract_csv_table("name,qty\nMask,3\n")

    def test_extract_xlsx_table_covers_error_and_success_cases(self):
        with mock.patch("wms.import_utils.load_workbook", None):
            with self.assertRaisesMessage(ValueError, "openpyxl est requis"):
                import_utils._extract_xlsx_table(b"x")

        active_sheet = _FakeSheetRows([("A",), ("1",)])
        workbook = _FakeWorkbook(active=active_sheet, sheetnames=["Main"])
        with mock.patch("wms.import_utils.load_workbook", return_value=workbook):
            with self.assertRaisesMessage(ValueError, "Feuille inconnue: Missing"):
                import_utils._extract_xlsx_table(b"x", sheet_name="Missing")
        self.assertTrue(workbook.closed)

        workbook = _FakeWorkbook(active=active_sheet, sheetnames=["Main"])
        with mock.patch("wms.import_utils.load_workbook", return_value=workbook):
            with self.assertRaisesMessage(ValueError, "Ligne des titres invalide"):
                import_utils._extract_xlsx_table(b"x", header_row=0)
        self.assertTrue(workbook.closed)

        empty_sheet = _FakeSheetRows([])
        workbook = _FakeWorkbook(active=empty_sheet, sheetnames=["Main"])
        with mock.patch("wms.import_utils.load_workbook", return_value=workbook):
            with self.assertRaisesMessage(ValueError, "Excel vide."):
                import_utils._extract_xlsx_table(b"x")
        self.assertTrue(workbook.closed)

        sheet = _FakeSheetRows(
            [
                ("ignored",),
                ("Nom", "Quantite"),
                ("Mask", 3.0),
            ]
        )
        workbook = _FakeWorkbook(active=sheet, sheetnames=["Main"])
        with mock.patch("wms.import_utils.load_workbook", return_value=workbook):
            headers, rows = import_utils._extract_xlsx_table(b"x", header_row=2)
        self.assertEqual(headers, ["Nom", "Quantite"])
        self.assertEqual(rows, [["Mask", "3"]])
        self.assertTrue(workbook.closed)

        named_sheet = _FakeSheetRows([("Nom",), ("Mask",)])
        workbook = _FakeWorkbook(
            active=active_sheet,
            sheetnames=["Main", "Named"],
            by_name={"Named": named_sheet},
        )
        with mock.patch("wms.import_utils.load_workbook", return_value=workbook):
            headers, rows = import_utils._extract_xlsx_table(
                b"x",
                sheet_name="Named",
            )
        self.assertEqual(headers, ["Nom"])
        self.assertEqual(rows, [["Mask"]])
        self.assertTrue(workbook.closed)

    def test_extract_xls_table_covers_error_and_success_cases(self):
        with mock.patch("wms.import_utils.xlrd", None):
            with self.assertRaisesMessage(ValueError, "xlrd est requis"):
                import_utils._extract_xls_table(b"x")

        class FakeXlrError(Exception):
            pass

        fake_xlrd = SimpleNamespace(
            biffh=SimpleNamespace(XLRDError=FakeXlrError),
        )
        workbook = SimpleNamespace(
            sheet_by_name=mock.Mock(side_effect=FakeXlrError("missing")),
            sheet_by_index=mock.Mock(),
        )
        fake_xlrd.open_workbook = mock.Mock(return_value=workbook)
        with mock.patch("wms.import_utils.xlrd", fake_xlrd):
            with self.assertRaisesMessage(ValueError, "Feuille inconnue: Missing"):
                import_utils._extract_xls_table(b"x", sheet_name="Missing")

        empty_sheet = _FakeXlsSheet([])
        workbook = SimpleNamespace(sheet_by_index=lambda idx: empty_sheet)
        fake_xlrd.open_workbook = mock.Mock(return_value=workbook)
        with mock.patch("wms.import_utils.xlrd", fake_xlrd):
            with self.assertRaisesMessage(ValueError, "Excel vide."):
                import_utils._extract_xls_table(b"x")

        sheet = _FakeXlsSheet([["Nom", "Qte"], ["Mask", 1]])
        workbook = SimpleNamespace(sheet_by_index=lambda idx: sheet)
        fake_xlrd.open_workbook = mock.Mock(return_value=workbook)
        with mock.patch("wms.import_utils.xlrd", fake_xlrd):
            with self.assertRaisesMessage(ValueError, "Ligne des titres invalide"):
                import_utils._extract_xls_table(b"x", header_row=3)

        workbook = SimpleNamespace(sheet_by_index=lambda idx: sheet)
        fake_xlrd.open_workbook = mock.Mock(return_value=workbook)
        with mock.patch("wms.import_utils.xlrd", fake_xlrd):
            headers, rows = import_utils._extract_xls_table(b"x")
        self.assertEqual(headers, ["Nom", "Qte"])
        self.assertEqual(rows, [["Mask", "1"]])

    def test_extract_pdf_table_covers_errors_and_success(self):
        with mock.patch("wms.import_utils.pdfplumber", None):
            with self.assertRaisesMessage(ValueError, "pdfplumber est requis"):
                import_utils._extract_pdf_table(b"x")

        page = SimpleNamespace(extract_table=lambda: None, extract_text=lambda: "")
        fake_pdf_module = SimpleNamespace(open=lambda _stream: _FakePdf([page]))
        with mock.patch("wms.import_utils.pdfplumber", fake_pdf_module):
            with self.assertRaisesMessage(ValueError, "Plage de pages PDF invalide."):
                import_utils._extract_pdf_table(b"x", page_start=2, page_end=1)

        with mock.patch("wms.import_utils.pdfplumber", fake_pdf_module):
            with self.assertRaisesMessage(ValueError, "PDF scanne non supporte"):
                import_utils._extract_pdf_table(b"x")

        page_with_table = SimpleNamespace(
            extract_table=lambda: [["Nom", "Qte"], ["Mask", "2"]],
            extract_text=lambda: "",
        )
        page_with_text = SimpleNamespace(
            extract_table=lambda: None,
            extract_text=lambda: "Nom  Qte\nGloves  5",
        )
        fake_pdf_module = SimpleNamespace(
            open=lambda _stream: _FakePdf([page_with_table, page_with_text])
        )
        with mock.patch("wms.import_utils.pdfplumber", fake_pdf_module):
            headers, rows = import_utils._extract_pdf_table(b"x")
        self.assertEqual(headers, ["Nom", "Qte"])
        self.assertEqual(rows, [["Mask", "2"], ["Gloves", "5"]])

        flaky_table = _TruthyThenFalsyTable([["Nom", "Qte"], ["Mask", "2"]])
        page_with_flaky_table = SimpleNamespace(
            extract_table=lambda: flaky_table,
            extract_text=lambda: "",
        )
        fake_pdf_module = SimpleNamespace(open=lambda _stream: _FakePdf([page_with_flaky_table]))
        with mock.patch("wms.import_utils.pdfplumber", fake_pdf_module):
            with self.assertRaisesMessage(
                ValueError,
                "Impossible d'extraire un tableau du PDF.",
            ):
                import_utils._extract_pdf_table(b"x")

    def test_extract_tabular_data_dispatch(self):
        with mock.patch("wms.import_utils._extract_csv_table", return_value=(["a"], [["1"]])):
            self.assertEqual(import_utils.extract_tabular_data(b"x", ".csv"), (["a"], [["1"]]))
        with mock.patch("wms.import_utils._extract_xlsx_table", return_value=(["a"], [["1"]])):
            self.assertEqual(
                import_utils.extract_tabular_data(b"x", ".xlsx", sheet_name="S", header_row=2),
                (["a"], [["1"]]),
            )
        with mock.patch("wms.import_utils._extract_xls_table", return_value=(["a"], [["1"]])):
            self.assertEqual(import_utils.extract_tabular_data(b"x", ".xls"), (["a"], [["1"]]))
        with mock.patch("wms.import_utils._extract_pdf_table", return_value=(["a"], [["1"]])):
            self.assertEqual(
                import_utils.extract_tabular_data(b"x", ".pdf", pdf_pages=(1, 2)),
                (["a"], [["1"]]),
            )
        with self.assertRaisesMessage(ValueError, "Format de fichier non supporté."):
            import_utils.extract_tabular_data(b"x", ".doc")

    def test_get_pdf_page_count_and_list_excel_sheets(self):
        with mock.patch("wms.import_utils.pdfplumber", None):
            with self.assertRaisesMessage(ValueError, "pdfplumber est requis"):
                import_utils.get_pdf_page_count(b"x")

        fake_pdf_module = SimpleNamespace(open=lambda _stream: _FakePdf([1, 2, 3]))
        with mock.patch("wms.import_utils.pdfplumber", fake_pdf_module):
            self.assertEqual(import_utils.get_pdf_page_count(b"x"), 3)

        with mock.patch("wms.import_utils.load_workbook", None):
            with self.assertRaisesMessage(ValueError, "openpyxl est requis"):
                import_utils.list_excel_sheets(b"x", ".xlsx")

        workbook = _FakeWorkbook(active=None, sheetnames=["Main", "Annexe"])
        with mock.patch("wms.import_utils.load_workbook", return_value=workbook):
            self.assertEqual(import_utils.list_excel_sheets(b"x", ".xlsx"), ["Main", "Annexe"])
        self.assertTrue(workbook.closed)

        with mock.patch("wms.import_utils.xlrd", None):
            with self.assertRaisesMessage(ValueError, "xlrd est requis"):
                import_utils.list_excel_sheets(b"x", ".xls")

        fake_xlrd = SimpleNamespace(
            open_workbook=lambda **kwargs: SimpleNamespace(sheet_names=lambda: ["Sheet1"])
        )
        with mock.patch("wms.import_utils.xlrd", fake_xlrd):
            self.assertEqual(import_utils.list_excel_sheets(b"x", ".xls"), ["Sheet1"])
        self.assertEqual(import_utils.list_excel_sheets(b"x", ".csv"), [])

    def test_get_value_and_parsers(self):
        self.assertEqual(import_utils.get_value({"a": 1}, "x", "a"), 1)
        self.assertIsNone(import_utils.get_value({"a": 1}, "x", "y"))

        self.assertEqual(import_utils.parse_str("  x "), "x")
        self.assertIsNone(import_utils.parse_str(" "))
        self.assertIsNone(import_utils.parse_str(None))

        self.assertIsNone(import_utils.parse_decimal(None))
        self.assertEqual(str(import_utils.parse_decimal("12,5")), "12.5")
        self.assertEqual(str(import_utils.parse_decimal(3)), "3")
        self.assertEqual(str(import_utils.parse_decimal(4.2)), "4.2")
        self.assertEqual(str(import_utils.parse_decimal(import_utils.Decimal("5.1"))), "5.1")
        self.assertIsNone(import_utils.parse_decimal("   "))
        with self.assertRaisesMessage(ValueError, "Invalid decimal value"):
            import_utils.parse_decimal("x")

        self.assertEqual(import_utils.parse_int("2.5"), 3)
        self.assertIsNone(import_utils.parse_int(""))

        self.assertIs(import_utils.parse_bool(True), True)
        self.assertIs(import_utils.parse_bool(False), False)
        self.assertIs(import_utils.parse_bool("oui"), True)
        self.assertIs(import_utils.parse_bool("no"), False)
        self.assertIsNone(import_utils.parse_bool(" "))
        self.assertIsNone(import_utils.parse_bool(None))
        with self.assertRaisesMessage(ValueError, "Invalid boolean value"):
            import_utils.parse_bool("maybe")

        self.assertEqual(import_utils.parse_tokens("a| b, c "), ["a", "b", "c"])
        self.assertEqual(import_utils.parse_tokens(""), [])
