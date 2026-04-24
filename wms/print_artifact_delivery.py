from io import BytesIO

from django.conf import settings
from django.http import FileResponse

from .print_pack_engine import PrintPackEngineError, render_pack_xlsx_documents
from .print_pack_graph import GraphPdfConversionError
from .print_pack_xlsx import build_xlsx_fallback_response


def artifact_pdf_response(artifact, *, default_filename="document.pdf"):
    filename = (artifact.pdf_file.name or "").split("/")[-1] or default_filename
    with artifact.pdf_file.open("rb") as pdf_stream:
        response = FileResponse(BytesIO(pdf_stream.read()), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


def is_xlsx_fallback_enabled():
    return bool(getattr(settings, "PRINT_PACK_XLSX_FALLBACK_ENABLED", False))


def generate_pack_xlsx_response(
    *,
    pack_code,
    shipment=None,
    carton=None,
    variant=None,
    render_documents_fn=render_pack_xlsx_documents,
):
    documents = render_documents_fn(
        pack_code=pack_code,
        shipment=shipment,
        carton=carton,
        variant=variant,
    )
    return build_xlsx_fallback_response(documents=documents, pack_code=pack_code)


def try_generate_pack_artifact(
    *,
    generate_pack_fn,
    fallback_renderer,
    xlsx_fallback_renderer,
    **kwargs,
):
    try:
        return generate_pack_fn(**kwargs)
    except GraphPdfConversionError:
        if is_xlsx_fallback_enabled():
            return xlsx_fallback_renderer(
                pack_code=kwargs.get("pack_code"),
                shipment=kwargs.get("shipment"),
                carton=kwargs.get("carton"),
                variant=kwargs.get("variant"),
            )
        return fallback_renderer()
    except PrintPackEngineError:
        return fallback_renderer()
