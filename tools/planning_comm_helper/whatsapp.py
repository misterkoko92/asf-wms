from __future__ import annotations

import platform
import subprocess
from time import sleep
from urllib.parse import quote


class WhatsAppPayloadError(ValueError):
    """Raised when a WhatsApp draft payload is incomplete."""


def build_whatsapp_url(recipient_contact: str, body: str) -> str:
    digits = "".join(char for char in str(recipient_contact or "") if char.isdigit())
    if not digits:
        raise WhatsAppPayloadError("WhatsApp recipient contact is required.")
    if not str(body or "").strip():
        raise WhatsAppPayloadError("WhatsApp message body is required.")
    return f"https://wa.me/{digits}?text={quote(str(body or ''))}"


def validate_whatsapp_draft(draft: dict[str, object]) -> None:
    wa_url = str(draft.get("wa_url") or "").strip()
    if wa_url:
        return
    build_whatsapp_url(
        str(draft.get("recipient_contact") or ""),
        str(draft.get("body") or ""),
    )


def _default_opener(url: str) -> None:
    system = platform.system()
    if system == "Darwin":
        subprocess.Popen(["open", url])
        return
    if system == "Windows":
        subprocess.Popen(["cmd", "/c", "start", "", url], shell=True)
        return
    subprocess.Popen(["xdg-open", url])


def open_whatsapp_drafts(
    drafts: list[dict[str, object]],
    *,
    opener=None,
    pause_seconds: float = 0.1,
) -> int:
    open_url = opener or _default_opener
    opened_count = 0
    for draft in drafts:
        validate_whatsapp_draft(draft)
        url = str(draft.get("wa_url") or "").strip() or build_whatsapp_url(
            str(draft.get("recipient_contact") or ""),
            str(draft.get("body") or ""),
        )
        open_url(url)
        opened_count += 1
        if pause_seconds:
            sleep(pause_seconds)
    return opened_count
