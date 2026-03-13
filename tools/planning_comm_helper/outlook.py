from __future__ import annotations

import base64
import platform
import subprocess
import tempfile
import uuid
from pathlib import Path

from tools.planning_comm_helper.excel_pdf import convert_workbook_to_pdf


class OutlookPayloadError(ValueError):
    """Raised when an Outlook draft payload is incomplete."""


EXCEL_ATTACHMENT_TYPES = {"excel_workbook", "planning_workbook"}


def _clean_address_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [entry.strip() for entry in value.replace(",", ";").split(";") if entry.strip()]
    return [str(entry).strip() for entry in value if str(entry).strip()]


def validate_outlook_draft(draft: dict[str, object]) -> None:
    if not str(draft.get("subject") or "").strip():
        raise OutlookPayloadError("Email subject is required.")
    if not str(draft.get("body_html") or "").strip():
        raise OutlookPayloadError("Email HTML body is required.")
    attachments = draft.get("attachments") or []
    if not isinstance(attachments, list):
        raise OutlookPayloadError("Email attachments must be a list.")


def _materialize_attachments(
    attachments: list[dict[str, object]],
    *,
    temp_root: Path,
) -> list[str]:
    temp_root.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for attachment in attachments:
        filename = str(attachment.get("filename") or "").strip()
        content_base64 = str(attachment.get("content_base64") or "").strip()
        if not filename or not content_base64:
            raise OutlookPayloadError("Attachment filename and content are required.")

        attachment_path = temp_root / f"{uuid.uuid4().hex}-{filename}"
        attachment_path.write_bytes(base64.b64decode(content_base64))

        if attachment.get("attachment_type") in EXCEL_ATTACHMENT_TYPES:
            pdf_path = convert_workbook_to_pdf(attachment_path)
            paths.append(str(pdf_path))
            continue
        paths.append(str(attachment_path))
    return paths


def open_outlook_drafts(
    drafts: list[dict[str, object]],
    *,
    temp_dir: str | Path | None = None,
) -> int:
    system = platform.system()
    temp_root = Path(temp_dir) if temp_dir else Path(tempfile.mkdtemp(prefix="planning-helper-"))
    opened_count = 0
    for draft in drafts:
        validate_outlook_draft(draft)
        attachment_paths = _materialize_attachments(
            list(draft.get("attachments") or []),
            temp_root=temp_root,
        )
        if system == "Windows":
            _open_windows_outlook_draft(draft, attachment_paths)
        elif system == "Darwin":
            _open_macos_outlook_draft(draft, attachment_paths)
        else:
            raise RuntimeError("Outlook drafts are only supported on Windows and macOS.")
        opened_count += 1
    return opened_count


def _open_windows_outlook_draft(draft: dict[str, object], attachment_paths: list[str]) -> None:
    try:
        import win32com.client  # type: ignore
    except ImportError as exc:  # pragma: no cover - platform-specific
        raise RuntimeError("pywin32 is required to open Outlook drafts on Windows.") from exc

    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)
    to_list = _clean_address_list(draft.get("to") or draft.get("recipient_contact"))
    cc_list = _clean_address_list(draft.get("cc"))
    bcc_list = _clean_address_list(draft.get("bcc"))
    mail.To = "; ".join(to_list)
    mail.CC = "; ".join(cc_list)
    mail.BCC = "; ".join(bcc_list)
    mail.Subject = str(draft.get("subject") or "")
    mail.Display()
    signature_html = mail.HTMLBody or ""
    mail.HTMLBody = f"{draft.get('body_html', '')}{signature_html}"
    for path in attachment_paths:
        mail.Attachments.Add(path)
    mail.Display(True)


def _open_macos_outlook_draft(draft: dict[str, object], attachment_paths: list[str]) -> None:
    script_lines = [
        'tell application "Microsoft Outlook"',
        (
            'set newMessage to make new outgoing message with properties '
            f'{{subject:"{_applescript_escape(str(draft.get("subject") or ""))}", '
            f'content:"{_applescript_escape(str(draft.get("body_html") or ""))}\\n\\n"}}'
        ),
        "tell newMessage",
    ]
    for recipient in _clean_address_list(draft.get("to") or draft.get("recipient_contact")):
        script_lines.append(
            'make new recipient at end of to recipients with properties '
            f'{{email address:{{address:"{_applescript_escape(recipient)}"}}}}'
        )
    for recipient in _clean_address_list(draft.get("cc")):
        script_lines.append(
            'make new recipient at end of cc recipients with properties '
            f'{{email address:{{address:"{_applescript_escape(recipient)}"}}}}'
        )
    for recipient in _clean_address_list(draft.get("bcc")):
        script_lines.append(
            'make new recipient at end of bcc recipients with properties '
            f'{{email address:{{address:"{_applescript_escape(recipient)}"}}}}'
        )
    for path in attachment_paths:
        script_lines.append(
            'make new attachment at end of attachments with properties '
            f'{{file:(POSIX file "{_applescript_escape(path)}")}}'
        )
    script_lines.extend(["end tell", "open newMessage", "activate", "end tell"])
    result = subprocess.run(
        ["osascript", "-e", "\n".join(script_lines)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:  # pragma: no cover - platform-specific
        raise RuntimeError("AppleScript failed to open the Outlook draft.")


def _applescript_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
