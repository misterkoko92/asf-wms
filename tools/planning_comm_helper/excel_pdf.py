from __future__ import annotations

import platform
import subprocess
from pathlib import Path


class ExcelPdfConversionError(RuntimeError):
    """Raised when Excel automation cannot generate a PDF."""


def convert_workbook_to_pdf(
    workbook_path: str | Path,
    pdf_path: str | Path | None = None,
    *,
    strict: bool = True,
) -> Path:
    workbook = Path(workbook_path).expanduser().resolve()
    if not workbook.exists():
        raise ExcelPdfConversionError(f"Workbook not found: {workbook}")

    output_path = (
        Path(pdf_path).expanduser().resolve() if pdf_path else workbook.with_suffix(".pdf")
    )
    system = platform.system()
    if system == "Windows":
        return _convert_with_windows_excel(workbook, output_path, strict=strict)
    if system == "Darwin":
        return _convert_with_macos_excel(workbook, output_path, strict=strict)
    raise ExcelPdfConversionError("Excel automation is unavailable on this platform.")


def _convert_with_windows_excel(workbook_path: Path, pdf_path: Path, *, strict: bool = True) -> Path:
    try:
        import pythoncom  # type: ignore
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise ExcelPdfConversionError("Excel automation is unavailable on Windows.") from exc

    com_initialized = False
    excel = None
    workbook = None
    try:
        pythoncom.CoInitialize()
        com_initialized = True
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        workbook = excel.Workbooks.Open(str(workbook_path))
        if strict:
            _prepare_windows_workbook_for_export(excel, workbook)
        workbook.ExportAsFixedFormat(0, str(pdf_path))
    except Exception as exc:  # pragma: no cover - platform-specific
        raise ExcelPdfConversionError("Excel automation failed to generate the PDF.") from exc
    finally:  # pragma: no branch
        if workbook is not None:
            workbook.Close(False)
        if excel is not None:
            excel.Quit()
        if com_initialized:
            pythoncom.CoUninitialize()

    if not pdf_path.exists():
        raise ExcelPdfConversionError("Excel did not generate the PDF.")
    return pdf_path


def _prepare_windows_workbook_for_export(excel, workbook) -> None:
    try:
        excel.Calculation = -4105  # xlCalculationAutomatic
    except Exception:  # pragma: no cover - defensive automation hook
        pass
    try:
        workbook.RefreshAll()
    except Exception:  # pragma: no cover - optional workbook capability
        pass
    try:
        excel.CalculateUntilAsyncQueriesDone()
    except Exception:  # pragma: no cover - not always supported
        pass
    try:
        excel.CalculateFullRebuild()
    except Exception:  # pragma: no cover - best effort recalculation
        try:
            workbook.Calculate()
        except Exception:
            pass


def _convert_with_macos_excel(workbook_path: Path, pdf_path: Path, *, strict: bool = True) -> Path:
    script = _build_macos_excel_script(
        workbook_path=workbook_path,
        pdf_path=pdf_path,
        strict=strict,
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ExcelPdfConversionError("Excel automation failed to generate the PDF on macOS.")
    if not pdf_path.exists():
        raise ExcelPdfConversionError("Excel did not generate the PDF.")
    return pdf_path


def _build_macos_excel_script(*, workbook_path: Path, pdf_path: Path, strict: bool) -> str:
    return f'''
        set workbookFile to POSIX file "{_applescript_escape(str(workbook_path))}"
        set pdfFile to POSIX file "{_applescript_escape(str(pdf_path))}"
        tell application "Microsoft Excel"
            activate
            set display alerts to false
            set wb to open workbook workbook file name workbookFile
            save wb in pdfFile as PDF file format
            close wb saving no
            set display alerts to true
        end tell
    '''


def _applescript_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
