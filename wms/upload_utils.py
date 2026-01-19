from pathlib import Path

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


def validate_upload(file_obj):
    suffix = Path(file_obj.name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        return f"Format non autorise: {file_obj.name}"
    max_size = PORTAL_MAX_FILE_SIZE_MB * 1024 * 1024
    if file_obj.size > max_size:
        return f"Fichier trop volumineux: {file_obj.name}"
    return None
