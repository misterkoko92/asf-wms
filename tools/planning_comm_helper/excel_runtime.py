from __future__ import annotations

import importlib
import platform
import shutil
import subprocess
from typing import TypedDict

EXCEL_RUNTIME_BACKEND = "excel_desktop"
EXCEL_RUNTIME_READY = "ready"
EXCEL_RUNTIME_PLATFORM_UNSUPPORTED = "platform_unsupported"
EXCEL_RUNTIME_NOT_INSTALLED = "excel_not_installed"
EXCEL_RUNTIME_AUTOMATION_UNAVAILABLE = "excel_automation_unavailable"


class ExcelRuntimeStatus(TypedDict):
    backend: str
    status: str
    available: bool
    detail: str


def get_excel_runtime_status() -> ExcelRuntimeStatus:
    system = platform.system()
    if system == "Darwin":
        return _get_macos_excel_runtime_status()
    if system == "Windows":
        return _get_windows_excel_runtime_status()
    return _build_status(
        EXCEL_RUNTIME_PLATFORM_UNSUPPORTED,
        available=False,
        detail=f"Excel automation is unavailable on {system or 'this platform'}.",
    )


def build_runtime_unavailable_message(status: ExcelRuntimeStatus) -> str:
    message = f"Excel runtime unavailable ({status['status']})."
    detail = status.get("detail", "").strip()
    if detail:
        return f"{message} {detail}"
    return message


def _get_macos_excel_runtime_status() -> ExcelRuntimeStatus:
    osascript_path = shutil.which("osascript")
    if not osascript_path:
        return _build_status(
            EXCEL_RUNTIME_AUTOMATION_UNAVAILABLE,
            available=False,
            detail="Excel automation is unavailable on macOS because osascript is missing.",
        )
    try:
        result = subprocess.run(
            [osascript_path, "-e", 'id of app "Microsoft Excel"'],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return _build_status(
            EXCEL_RUNTIME_AUTOMATION_UNAVAILABLE,
            available=False,
            detail=f"Excel automation is unavailable on macOS. {exc}",
        )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        base_detail = "Microsoft Excel is not installed or not visible to AppleScript."
        if detail:
            base_detail = f"{base_detail} {detail}"
        return _build_status(
            EXCEL_RUNTIME_NOT_INSTALLED,
            available=False,
            detail=base_detail,
        )
    return _build_status(EXCEL_RUNTIME_READY, available=True, detail="")


def _get_windows_excel_runtime_status() -> ExcelRuntimeStatus:
    try:
        pythoncom = importlib.import_module("pythoncom")
        win32com_client = importlib.import_module("win32com.client")
    except ImportError:
        return _build_status(
            EXCEL_RUNTIME_AUTOMATION_UNAVAILABLE,
            available=False,
            detail="Excel automation is unavailable on Windows because COM modules are missing.",
        )

    excel = None
    com_initialized = False
    try:
        pythoncom.CoInitialize()
        com_initialized = True
        excel = win32com_client.Dispatch("Excel.Application")
    except Exception as exc:  # pragma: no cover - Windows-only automation
        detail = str(exc).strip()
        base_detail = "Microsoft Excel is not installed or automation is not available on Windows."
        if detail:
            base_detail = f"{base_detail} {detail}"
        return _build_status(
            EXCEL_RUNTIME_NOT_INSTALLED,
            available=False,
            detail=base_detail,
        )
    finally:  # pragma: no branch
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass
        if com_initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    return _build_status(EXCEL_RUNTIME_READY, available=True, detail="")


def _build_status(status: str, *, available: bool, detail: str) -> ExcelRuntimeStatus:
    return {
        "backend": EXCEL_RUNTIME_BACKEND,
        "status": status,
        "available": available,
        "detail": detail,
    }
