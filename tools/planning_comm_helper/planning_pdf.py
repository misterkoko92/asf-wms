from __future__ import annotations

import platform
import subprocess
from pathlib import Path


class PlanningPdfConversionError(RuntimeError):
    """Raised when Excel automation cannot generate the planning PDF."""


def convert_workbook_to_pdf(workbook_path: str | Path, pdf_path: str | Path | None = None) -> Path:
    workbook = Path(workbook_path).expanduser().resolve()
    if not workbook.exists():
        raise PlanningPdfConversionError(f"Workbook not found: {workbook}")

    output_path = (
        Path(pdf_path).expanduser().resolve() if pdf_path else workbook.with_suffix(".pdf")
    )
    system = platform.system()
    if system == "Windows":
        return _convert_with_windows_excel(workbook, output_path)
    if system == "Darwin":
        return _convert_with_macos_excel(workbook, output_path)
    raise PlanningPdfConversionError(
        "Excel automation is unavailable on this platform. LibreOffice fallback is not supported."
    )


def _convert_with_windows_excel(workbook_path: Path, pdf_path: Path) -> Path:
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:
        raise PlanningPdfConversionError(
            "Excel automation is unavailable on Windows. LibreOffice fallback is not supported."
        ) from exc

    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    workbook = None
    try:
        workbook = excel.Workbooks.Open(str(workbook_path))
        workbook.ExportAsFixedFormat(0, str(pdf_path))
    except Exception as exc:  # pragma: no cover - platform-specific
        raise PlanningPdfConversionError(
            "Excel automation failed to generate the planning PDF. LibreOffice fallback is not supported."
        ) from exc
    finally:  # pragma: no branch
        if workbook is not None:
            workbook.Close(False)
        excel.Quit()

    if not pdf_path.exists():
        raise PlanningPdfConversionError("Excel did not generate the planning PDF.")
    return pdf_path


def _convert_with_macos_excel(workbook_path: Path, pdf_path: Path) -> Path:
    script = f'''
        set workbookFile to POSIX file "{_applescript_escape(str(workbook_path))}"
        set pdfFile to POSIX file "{_applescript_escape(str(pdf_path))}"
        tell application "Microsoft Excel"
            activate
            set display alerts to false
            set wb to open workbook workbook file name (workbookFile as alias as string)
            save wb in pdfFile as PDF file format
            close wb saving no
            set display alerts to true
        end tell
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PlanningPdfConversionError(
            "Excel automation failed to generate the planning PDF on macOS. LibreOffice fallback is not supported."
        )
    if not pdf_path.exists():
        raise PlanningPdfConversionError("Excel did not generate the planning PDF.")
    return pdf_path


def _applescript_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
