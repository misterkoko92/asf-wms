from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from .document_scan import DocumentScanStatus
from .document_scan_queue import queue_document_scan
from .models import Document, DocumentType, Shipment
from .upload_utils import validate_upload


def handle_shipment_document_upload(request, *, shipment_id):
    shipment = get_object_or_404(Shipment, pk=shipment_id)
    uploaded = request.FILES.get("document_file")
    if not uploaded:
        messages.error(request, "Fichier requis.")
        return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)

    validation_error = validate_upload(uploaded)
    if validation_error:
        messages.error(request, validation_error)
        return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)

    document = Document.objects.create(
        shipment=shipment,
        doc_type=DocumentType.ADDITIONAL,
        file=uploaded,
        scan_status=DocumentScanStatus.PENDING,
        scan_message="Scan antivirus en cours.",
    )
    queue_document_scan(document)
    messages.success(request, "Document ajouté.")
    return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)


def handle_shipment_document_delete(request, *, shipment_id, document_id):
    shipment = get_object_or_404(Shipment, pk=shipment_id)
    document = get_object_or_404(
        Document, pk=document_id, shipment=shipment, doc_type=DocumentType.ADDITIONAL
    )
    if document.file:
        document.file.delete(save=False)
    document.delete()
    messages.success(request, "Document supprime.")
    return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)
