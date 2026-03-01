from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from django.http import HttpResponse
from django.utils import timezone

from .print_pack_engine import PrintPackEngineError

XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
ZIP_CONTENT_TYPE = "application/zip"


def _content_disposition(filename):
    safe_name = (filename or "").replace('"', "")
    return f'attachment; filename="{safe_name}"'


def build_xlsx_fallback_response(*, documents, pack_code):
    if not documents:
        raise PrintPackEngineError("No generated XLSX documents to return.")

    response = None
    if len(documents) == 1:
        entry = documents[0]
        response = HttpResponse(entry.payload, content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = _content_disposition(entry.filename)
    else:
        buffer = BytesIO()
        with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
            for entry in documents:
                archive.writestr(entry.filename, entry.payload)
        stamp = timezone.now().strftime("%Y%m%d%H%M%S")
        zip_name = f"print-pack-{pack_code}-{stamp}.zip"
        response = HttpResponse(buffer.getvalue(), content_type=ZIP_CONTENT_TYPE)
        response["Content-Disposition"] = _content_disposition(zip_name)

    response["X-WMS-Print-Mode"] = "xlsx-fallback"
    return response
