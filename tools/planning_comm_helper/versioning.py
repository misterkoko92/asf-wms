from __future__ import annotations

import platform

HELPER_VERSION = "0.1.0"
HELPER_CAPABILITIES = ("pdf_render", "excel_render", "pdf_merge")


def get_helper_runtime_metadata() -> dict[str, object]:
    return {
        "helper_version": HELPER_VERSION,
        "platform": platform.system(),
        "capabilities": list(HELPER_CAPABILITIES),
    }
