from io import BytesIO

from django.core.files.base import ContentFile
from django.utils import timezone
from openpyxl import load_workbook

from .models import (
    GeneratedPrintArtifact,
    GeneratedPrintArtifactItem,
    GeneratedPrintArtifactStatus,
    PrintPack,
)
from .print_pack_excel import fill_workbook_cells
from .print_pack_graph import convert_excel_to_pdf_via_graph
from .print_pack_pdf import merge_pdf_documents


class PrintPackEngineError(RuntimeError):
    """Raised when pack generation cannot be completed."""


def _build_mapping_payload(*, shipment=None, carton=None, document=None):
    payload = {
        "shipment": {},
        "carton": {},
        "document": {
            "doc_type": getattr(document, "doc_type", ""),
            "variant": getattr(document, "variant", ""),
        },
    }
    if shipment is not None:
        payload["shipment"] = {
            "id": shipment.id,
            "reference": shipment.reference,
            "shipper_name": shipment.shipper_name,
            "recipient_name": shipment.recipient_name,
            "recipient": {
                "full_name": shipment.recipient_name,
            },
            "correspondent_name": shipment.correspondent_name,
            "destination_address": shipment.destination_address,
            "destination_country": shipment.destination_country,
            "requested_delivery_date": shipment.requested_delivery_date,
            "notes": shipment.notes,
        }
    if carton is not None:
        payload["carton"] = {
            "id": carton.id,
            "code": carton.code,
        }
    return payload


def _render_document_xlsx_bytes(*, document, shipment=None, carton=None):
    if not document.xlsx_template_file:
        raise PrintPackEngineError(
            f"Missing xlsx template file for doc_type={document.doc_type}."
        )
    with document.xlsx_template_file.open("rb") as stream:
        template_bytes = stream.read()
    workbook = load_workbook(BytesIO(template_bytes))
    mappings = list(document.cell_mappings.order_by("sequence", "id"))
    payload = _build_mapping_payload(
        shipment=shipment,
        carton=carton,
        document=document,
    )
    fill_workbook_cells(workbook, mappings, payload)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _artifact_basename(*, pack_code):
    stamp = timezone.now().strftime("%Y%m%d%H%M%S")
    return f"print-pack-{pack_code}-{stamp}"


def generate_pack(*, pack_code, shipment=None, carton=None, user=None, variant=None):
    pack = PrintPack.objects.filter(code=pack_code, active=True).first()
    if pack is None:
        raise PrintPackEngineError(f"Unknown active pack: {pack_code}")

    documents_qs = pack.documents.filter(enabled=True)
    if variant:
        documents_qs = documents_qs.filter(variant=variant)
    documents = list(documents_qs.order_by("sequence", "id"))
    if not documents:
        raise PrintPackEngineError(f"No enabled documents configured for pack {pack_code}.")

    artifact = GeneratedPrintArtifact.objects.create(
        shipment=shipment,
        carton=carton,
        pack_code=pack.code,
        status=GeneratedPrintArtifactStatus.GENERATED,
        created_by=user,
    )

    generated_pdfs = []
    for document in documents:
        xlsx_bytes = _render_document_xlsx_bytes(
            document=document,
            shipment=shipment,
            carton=carton,
        )
        xlsx_name = f"{pack.code}-{document.doc_type}-{document.id}.xlsx"
        pdf_bytes = convert_excel_to_pdf_via_graph(
            xlsx_bytes=xlsx_bytes,
            filename=xlsx_name,
        )
        generated_pdfs.append(pdf_bytes)

        item = GeneratedPrintArtifactItem.objects.create(
            artifact=artifact,
            doc_type=document.doc_type,
            variant=document.variant or "",
            sequence=document.sequence,
        )
        item.source_xlsx_file.save(
            xlsx_name,
            ContentFile(xlsx_bytes),
            save=False,
        )
        item.generated_pdf_file.save(
            f"{pack.code}-{document.doc_type}-{document.id}.pdf",
            ContentFile(pdf_bytes),
            save=False,
        )
        item.save(update_fields=["source_xlsx_file", "generated_pdf_file"])

    if len(generated_pdfs) == 1:
        merged_pdf = generated_pdfs[0]
    else:
        merged_pdf = merge_pdf_documents(generated_pdfs)

    artifact_name = f"{_artifact_basename(pack_code=pack.code)}.pdf"
    artifact.pdf_file.save(artifact_name, ContentFile(merged_pdf), save=False)
    artifact.status = GeneratedPrintArtifactStatus.SYNC_PENDING
    artifact.save(update_fields=["pdf_file", "status"])
    return artifact
