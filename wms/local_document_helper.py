from __future__ import annotations

from django.http import Http404, HttpResponse, JsonResponse

from .print_pack_xlsx import XLSX_CONTENT_TYPE

HELPER_REQUEST_PARAM = "helper"
HELPER_DOCUMENT_PARAM = "helper_document"
LOCAL_DOCUMENT_HELPER_ORIGIN = "127.0.0.1:38555"


def is_local_helper_job_request(request) -> bool:
    return str(request.GET.get(HELPER_REQUEST_PARAM) or "").strip() == "1"


def get_local_helper_document_index(request) -> int | None:
    raw_value = str(request.GET.get(HELPER_DOCUMENT_PARAM) or "").strip()
    if not raw_value:
        return None
    try:
        document_index = int(raw_value)
    except ValueError as exc:
        raise Http404("Helper document index is invalid.") from exc
    if document_index < 0:
        raise Http404("Helper document index is invalid.")
    return document_index


def build_local_helper_job_response(
    request,
    *,
    pack_code,
    render_documents,
    shipment=None,
    carton=None,
) -> JsonResponse:
    documents = list(render_documents())
    payload = {
        "documents": [
            {
                "filename": entry.filename,
                "download_url": _helper_document_download_url(request, index),
            }
            for index, entry in enumerate(documents)
        ],
        "output_filename": _helper_output_filename(
            pack_code=pack_code,
            shipment=shipment,
            carton=carton,
        ),
        "merge": len(documents) > 1,
        "open_after_render": True,
    }
    return JsonResponse(payload)


def build_local_helper_document_response(
    request,
    *,
    render_documents,
) -> HttpResponse:
    document_index = get_local_helper_document_index(request)
    if document_index is None:
        raise Http404("Helper document index is required.")

    documents = list(render_documents())
    if document_index >= len(documents):
        raise Http404("Helper document was not found.")

    document = documents[document_index]
    response = HttpResponse(document.payload, content_type=XLSX_CONTENT_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{document.filename}"'
    return response


def _helper_document_download_url(request, document_index: int) -> str:
    params = request.GET.copy()
    params.pop(HELPER_REQUEST_PARAM, None)
    params[HELPER_DOCUMENT_PARAM] = str(document_index)
    return f"{request.path}?{params.urlencode()}"


def _helper_output_filename(*, pack_code, shipment=None, carton=None) -> str:
    if carton is not None and getattr(carton, "code", ""):
        return f"print-pack-{pack_code}-{carton.code}.pdf"
    if shipment is not None and getattr(shipment, "reference", ""):
        return f"print-pack-{pack_code}-{shipment.reference}.pdf"
    return f"print-pack-{pack_code}.pdf"
