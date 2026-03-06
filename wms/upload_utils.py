from pathlib import Path
from typing import Any

ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".xlsx",
    ".xls",
    ".doc",
    ".docx",
}
PORTAL_MAX_FILE_SIZE_MB = 10

_OFFICE_LEGACY_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ZIP_SIGNATURES = (
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"PK\x07\x08",
)
_MAGIC_SIGNATURES_BY_EXTENSION = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".doc": (_OFFICE_LEGACY_SIGNATURE,),
    ".xls": (_OFFICE_LEGACY_SIGNATURE,),
    ".docx": _ZIP_SIGNATURES,
    ".xlsx": _ZIP_SIGNATURES,
}
_MAX_SIGNATURE_BYTES = max(
    len(signature)
    for signatures in _MAGIC_SIGNATURES_BY_EXTENSION.values()
    for signature in signatures
)


def _read_file_header(file_obj, length) -> bytes:
    read = getattr(file_obj, "read", None)
    if not callable(read):
        return b""

    position = None
    tell = getattr(file_obj, "tell", None)
    if callable(tell):
        try:
            position = tell()
        except Exception:
            position = None

    try:
        header: Any = read(length) or b""
    except Exception:
        header = b""

    seek = getattr(file_obj, "seek", None)
    if callable(seek):
        try:
            seek(position if position is not None else 0)
        except Exception:
            position = None

    if isinstance(header, bytes):
        return header
    if isinstance(header, bytearray):
        return bytes(header)
    if isinstance(header, str):
        return header.encode()
    return b""


def _has_valid_file_signature(file_obj, suffix):
    expected_signatures = _MAGIC_SIGNATURES_BY_EXTENSION.get(suffix)
    if not expected_signatures:
        return True

    header = _read_file_header(file_obj, _MAX_SIGNATURE_BYTES)
    if not header:
        return False

    return any(header.startswith(signature) for signature in expected_signatures)


def validate_upload(file_obj):
    suffix = Path(file_obj.name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        return f"Format non autorise: {file_obj.name}"
    max_size = PORTAL_MAX_FILE_SIZE_MB * 1024 * 1024
    if file_obj.size > max_size:
        return f"Fichier trop volumineux: {file_obj.name}"
    if not _has_valid_file_signature(file_obj, suffix):
        return f"Contenu de fichier invalide: {file_obj.name}"
    return None
