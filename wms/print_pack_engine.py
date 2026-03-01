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


def _resolve_root_category_name(product):
    category = getattr(product, "category", None)
    if category is None:
        return ""
    visited_ids = set()
    while getattr(category, "parent", None) is not None:
        category_id = getattr(category, "id", None)
        if category_id in visited_ids:
            break
        if category_id is not None:
            visited_ids.add(category_id)
        category = category.parent
    return getattr(category, "name", "") or ""


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
        carton_count_attr = getattr(shipment, "carton_count", None)
        if carton_count_attr is not None:
            carton_total_count = carton_count_attr
        elif hasattr(shipment, "carton_set"):
            carton_total_count = shipment.carton_set.count()
        else:
            carton_total_count = 1
        destination = getattr(shipment, "destination", None)
        destination_iata = ""
        if destination is not None:
            destination_iata = getattr(destination, "iata_code", "") or ""

        shipment_items = []
        if hasattr(shipment, "carton_set"):
            carton_qs = shipment.carton_set.all().order_by("code")
            for carton_position, shipment_carton in enumerate(carton_qs, start=1):
                carton_items = shipment_carton.cartonitem_set.select_related(
                    "product_lot__product__category__parent",
                    "product_lot__location",
                )
                for carton_item in carton_items:
                    product = carton_item.product_lot.product
                    shipment_items.append(
                        {
                            "carton_code": shipment_carton.code,
                            "carton_position": carton_position,
                            "category_root": _resolve_root_category_name(product),
                            "brand": product.brand or "",
                            "product_name": product.name,
                            "quantity": carton_item.quantity,
                            "expires_on": carton_item.product_lot.expires_on,
                        }
                    )
        payload["shipment"] = {
            "id": shipment.id,
            "reference": shipment.reference,
            "carton_total_count": carton_total_count,
            "destination_iata": destination_iata,
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
            "items": shipment_items,
        }
    if carton is not None:
        items = []
        if hasattr(carton, "cartonitem_set"):
            for carton_item in carton.cartonitem_set.select_related(
                "product_lot__product",
                "product_lot__location",
            ):
                product = carton_item.product_lot.product
                location = carton_item.product_lot.location
                if location:
                    location_label = f"{location.zone} - {location.aisle} - {location.shelf}"
                else:
                    location_label = ""
                items.append(
                    {
                        "category_root": _resolve_root_category_name(product),
                        "product_name": product.name,
                        "brand": product.brand or "",
                        "quantity": carton_item.quantity,
                        "expires_on": carton_item.product_lot.expires_on,
                        "location": location_label,
                    }
                )
        payload["carton"] = {
            "id": carton.id,
            "code": carton.code,
            "items": items,
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
