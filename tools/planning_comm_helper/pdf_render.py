from __future__ import annotations

import base64
import os
import platform
import subprocess
import tempfile
import uuid
from io import BytesIO
from pathlib import Path

from tools.planning_comm_helper.excel_pdf import convert_workbook_to_pdf

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:  # pragma: no cover - optional dependency at runtime
    PdfReader = None
    PdfWriter = None


class PdfRenderJobError(ValueError):
    """Raised when a local PDF render job payload is invalid or cannot complete."""


HELPER_RENDER_DIRNAME = "ASF Planning Communication Helper"


def render_pdf_job(
    payload: dict[str, object],
    *,
    temp_dir: str | Path | None = None,
) -> dict[str, object]:
    documents = _require_documents(payload)
    output_filename = _resolve_output_filename(payload)
    merge = bool(payload.get("merge"))
    open_after_render = bool(payload.get("open_after_render"))
    for document in documents:
        _parse_document(document)
    temp_root = Path(temp_dir) if temp_dir else _default_temp_root()
    temp_root.mkdir(parents=True, exist_ok=True)

    rendered_paths = [
        _render_document(document=document, temp_root=temp_root)
        for document in documents
    ]
    final_path = _build_final_output(
        rendered_paths=rendered_paths,
        temp_root=temp_root,
        output_filename=output_filename,
        merge=merge,
    )

    if open_after_render:
        _open_path(final_path)

    return {
        "ok": True,
        "output_filename": final_path.name,
        "opened": open_after_render,
        "warning_messages": [],
    }


def _default_temp_root() -> Path:
    system = platform.system()
    if system == "Darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / HELPER_RENDER_DIRNAME
            / "pdf-render"
        )
    if system == "Windows":
        return _windows_local_appdata_root() / "ASF" / "planning_comm_helper" / "pdf-render"
    return Path(tempfile.gettempdir()) / "planning-helper"


def _windows_local_appdata_root() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata)
    return Path.home() / "AppData" / "Local"


def _require_documents(payload: dict[str, object]) -> list[dict[str, object]]:
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise PdfRenderJobError("At least one document is required.")
    if not all(isinstance(document, dict) for document in documents):
        raise PdfRenderJobError("Documents must be objects.")
    return documents


def _resolve_output_filename(payload: dict[str, object]) -> str:
    output_filename = str(payload.get("output_filename") or "").strip() or "document.pdf"
    if not output_filename.lower().endswith(".pdf"):
        output_filename = f"{output_filename}.pdf"
    return output_filename


def _render_document(*, document: dict[str, object], temp_root: Path) -> Path:
    filename, content_base64 = _parse_document(document)

    workbook_path = temp_root / f"{uuid.uuid4().hex}-{Path(filename).name}"
    try:
        workbook_path.write_bytes(base64.b64decode(content_base64))
    except Exception as exc:
        raise PdfRenderJobError(f"Invalid base64 content for document {filename}.") from exc

    return convert_workbook_to_pdf(workbook_path)


def _parse_document(document: dict[str, object]) -> tuple[str, str]:
    filename = str(document.get("filename") or "").strip()
    content_base64 = str(document.get("content_base64") or "").strip()
    if not filename or not content_base64:
        raise PdfRenderJobError("Document filename and content are required.")
    return filename, content_base64


def _build_final_output(
    *,
    rendered_paths: list[Path],
    temp_root: Path,
    output_filename: str,
    merge: bool,
) -> Path:
    if not rendered_paths:
        raise PdfRenderJobError("At least one rendered PDF is required.")

    final_path = temp_root / output_filename
    if len(rendered_paths) == 1:
        source_path = rendered_paths[0]
        if source_path != final_path:
            final_path.write_bytes(source_path.read_bytes())
        return final_path

    if not merge:
        raise PdfRenderJobError("Multiple documents require merge=true.")

    merged_bytes = merge_pdf_documents([path.read_bytes() for path in rendered_paths])
    final_path.write_bytes(merged_bytes)
    return final_path


def merge_pdf_documents(pdf_list: list[bytes]) -> bytes:
    if not pdf_list:
        raise PdfRenderJobError("No PDF documents were provided for merge.")
    if PdfReader is None or PdfWriter is None:
        raise PdfRenderJobError("pypdf is required to merge PDF documents.")

    writer = PdfWriter()
    for payload in pdf_list:
        reader = PdfReader(BytesIO(payload))
        for page in reader.pages:
            writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _open_path(path: Path) -> None:
    system = platform.system()
    if system == "Windows":  # pragma: no cover - platform-specific
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    command = ["open" if system == "Darwin" else "xdg-open", str(path)]
    subprocess.run(command, capture_output=True, check=False)  # pragma: no cover
