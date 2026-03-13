from __future__ import annotations

import platform
from pathlib import Path

from tools.planning_comm_helper import excel_pdf


class PlanningPdfConversionError(excel_pdf.ExcelPdfConversionError):
    """Raised when Excel automation cannot generate the planning PDF."""


def convert_workbook_to_pdf(
    workbook_path: str | Path,
    pdf_path: str | Path | None = None,
    *,
    strict: bool = True,
) -> Path:
    workbook = Path(workbook_path).expanduser().resolve()
    if not workbook.exists():
        raise PlanningPdfConversionError(f"Workbook not found: {workbook}")

    output_path = (
        Path(pdf_path).expanduser().resolve() if pdf_path else workbook.with_suffix(".pdf")
    )
    system = platform.system()
    if system == "Windows":
        return _convert_with_windows_excel(workbook, output_path, strict=strict)
    if system == "Darwin":
        return _convert_with_macos_excel(workbook, output_path, strict=strict)
    raise PlanningPdfConversionError("Excel automation is unavailable on this platform.")


def _convert_with_windows_excel(workbook_path: Path, pdf_path: Path, *, strict: bool = True) -> Path:
    return excel_pdf._convert_with_windows_excel(workbook_path, pdf_path, strict=strict)


def _convert_with_macos_excel(workbook_path: Path, pdf_path: Path, *, strict: bool = True) -> Path:
    return excel_pdf._convert_with_macos_excel(workbook_path, pdf_path, strict=strict)


def _applescript_escape(value: str) -> str:
    return excel_pdf._applescript_escape(value)
