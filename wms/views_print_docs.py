from io import BytesIO

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from .documents import resolve_carton_item_expires_on
from .local_document_helper import (
    build_local_helper_document_response,
    build_local_helper_job_response,
    get_local_helper_document_index,
    is_local_helper_job_request,
)
from .models import Carton, Shipment
from .prepare_kits_helpers import _parse_carton_ids, build_prepare_kits_picking_context
from .print_context import (
    build_carton_contact_label_context,
    build_carton_picking_context,
    build_label_context,
    build_shipment_document_context,
)
from .print_delivery import wants_browser_print, wants_external_pdf
from .print_pack_engine import (
    PrintPackEngineError,
    generate_pack,
    render_pack_document_xlsx_documents,
    render_pack_xlsx_documents,
)
from .print_pack_graph import GraphPdfConversionError, convert_excel_to_pdf_via_graph
from .print_pack_pdf import impose_two_up_pdf_on_a4, merge_pdf_documents
from .print_pack_routing import (
    resolve_carton_packing_pack,
    resolve_carton_picking_pack,
    resolve_pack_request,
)
from .print_pack_xlsx import build_xlsx_fallback_response
from .print_renderer import get_template_layout, render_layout_from_layout
from .shipment_document_handlers import (
    handle_shipment_document_delete,
    handle_shipment_document_upload,
)
from .shipment_view_helpers import render_carton_document, render_shipment_document
from .view_permissions import scan_staff_required

TEMPLATE_DYNAMIC_DOCUMENT = "print/dynamic_document.html"
TEMPLATE_PACKING_LIST_CARTON = "print/liste_colisage_carton.html"
TEMPLATE_PICKING_LIST_CARTON = "print/picking_list_carton.html"
TEMPLATE_SHIPMENT_PRINT_BUNDLE = "scan/shipment_print_bundle.html"
TEMPLATE_SHIPMENT_PRINT_BUNDLE_LOT = "scan/shipment_print_bundle_lot.html"
TEMPLATE_CARTON_PRINT_BUNDLE_LOT = "scan/carton_print_bundle_lot.html"
TEMPLATE_SHIPMENT_BUNDLE_A4 = "print/shipment_bundle_a4.html"
TEMPLATE_SHIPMENT_BUNDLE_A5_TWO_UP = "print/shipment_bundle_a5_two_up.html"

SHIPMENT_VIEW_DOCUMENT_CONFIG = {
    "shipment_note": {
        "pack_code": "C",
        "doc_type": "shipment_note",
        "variant": "shipment",
        "repeat_per_carton": False,
    },
    "customs": {
        "pack_code": "C",
        "doc_type": "shipment_note",
        "render_doc_type": "customs_note",
        "variant": "shipment",
        "repeat_per_carton": False,
    },
    "packing_list": {
        "pack_code": "B",
        "doc_type": "packing_list_shipment",
        "variant": "shipment",
        "repeat_per_carton": False,
    },
    "donation": {
        "pack_code": "B",
        "doc_type": "donation_certificate",
        "variant": "shipment",
        "repeat_per_carton": True,
    },
    "contact": {
        "pack_code": "C",
        "doc_type": "contact_label",
        "variant": "shipment",
        "repeat_per_carton": True,
    },
    "labels": {
        "pack_code": "D",
        "doc_type": "destination_label",
        "variant": "single_label",
        "repeat_per_carton": True,
    },
}


def _get_shipment_by_id(shipment_id):
    return get_object_or_404(Shipment, pk=shipment_id)


def _get_shipment_by_reference(shipment_ref):
    return get_object_or_404(Shipment, reference=shipment_ref)


def _get_shipment_carton_or_404(shipment, carton_id):
    carton = shipment.carton_set.filter(pk=carton_id).first()
    if carton is None:
        raise Http404(_("Carton introuvable pour cette expédition."))
    return carton


def _build_standalone_carton_context(carton):
    item_rows = []
    weight_total_g = 0
    for item in carton.cartonitem_set.select_related("product_lot", "product_lot__product"):
        product = item.product_lot.product
        if product.weight_g:
            weight_total_g += product.weight_g * item.quantity
        item_rows.append(
            {
                "product": product.name,
                "lot": item.product_lot.lot_code or "N/A",
                "quantity": item.quantity,
                "expires_on": resolve_carton_item_expires_on(item),
            }
        )
    return {
        "document_date": timezone.localdate(),
        "shipment_ref": "-",
        "carton_code": carton.code,
        "item_rows": item_rows,
        "carton_weight_kg": weight_total_g / 1000 if weight_total_g else None,
        "hide_footer": True,
    }


def _render_carton_document_with_layout(request, context):
    layout_override = get_template_layout("packing_list_carton")
    if layout_override:
        blocks = render_layout_from_layout(layout_override, context)
        return render(request, TEMPLATE_DYNAMIC_DOCUMENT, {"blocks": blocks})
    return render(request, TEMPLATE_PACKING_LIST_CARTON, context)


def _artifact_pdf_response(artifact):
    filename = (artifact.pdf_file.name or "").split("/")[-1] or "document.pdf"
    with artifact.pdf_file.open("rb") as pdf_stream:
        response = FileResponse(BytesIO(pdf_stream.read()), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


def _generate_pack_pdf_response(request, *, pack_code, shipment=None, carton=None, variant=None):
    artifact = generate_pack(
        pack_code=pack_code,
        shipment=shipment,
        carton=carton,
        user=getattr(request, "user", None),
        variant=variant,
    )
    return _artifact_pdf_response(artifact)


def _is_xlsx_fallback_enabled():
    return bool(getattr(settings, "PRINT_PACK_XLSX_FALLBACK_ENABLED", False))


def _generate_pack_xlsx_response(*, pack_code, shipment=None, carton=None, variant=None):
    documents = render_pack_xlsx_documents(
        pack_code=pack_code,
        shipment=shipment,
        carton=carton,
        variant=variant,
    )
    return build_xlsx_fallback_response(documents=documents, pack_code=pack_code)


def _render_pack_xlsx_documents(*, pack_code, shipment=None, carton=None, variant=None):
    return render_pack_xlsx_documents(
        pack_code=pack_code,
        shipment=shipment,
        carton=carton,
        variant=variant,
    )


def _ordered_shipment_cartons(shipment):
    return list(shipment.carton_set.all().order_by("code"))


def _shipment_view_document_or_404(document_key):
    config = SHIPMENT_VIEW_DOCUMENT_CONFIG.get((document_key or "").strip())
    if config is None:
        raise Http404("Document type not found")
    return config


def _render_shipment_view_xlsx_documents(shipment, document_key):
    config = _shipment_view_document_or_404(document_key)
    cartons = _ordered_shipment_cartons(shipment) if config["repeat_per_carton"] else None
    render_kwargs = {
        "pack_code": config["pack_code"],
        "doc_type": config["doc_type"],
        "variant": config["variant"],
        "shipment": shipment,
        "cartons": cartons,
    }
    if config.get("render_doc_type"):
        render_kwargs["render_doc_type"] = config["render_doc_type"]
    return render_pack_document_xlsx_documents(
        **render_kwargs,
    )


def _build_inline_pdf_response(pdf_bytes, *, filename):
    response = FileResponse(BytesIO(pdf_bytes), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


def _build_pdf_response_from_xlsx_documents(documents, *, filename, two_up_on_a4=False):
    pdf_documents = []
    for document in documents:
        pdf_documents.append(
            convert_excel_to_pdf_via_graph(
                xlsx_bytes=document.payload,
                filename=document.filename,
            )
        )
    if not pdf_documents:
        raise PrintPackEngineError("No XLSX documents were provided for PDF rendering.")
    if two_up_on_a4:
        merged_pdf = impose_two_up_pdf_on_a4(pdf_documents)
    elif len(pdf_documents) == 1:
        merged_pdf = pdf_documents[0]
    else:
        merged_pdf = merge_pdf_documents(pdf_documents)
    return _build_inline_pdf_response(merged_pdf, filename=filename)


def _build_shipment_view_bundle_a4_xlsx_documents(shipment):
    documents = []
    documents.extend(
        render_pack_document_xlsx_documents(
            pack_code="C",
            doc_type="shipment_note",
            variant="shipment",
            shipment=shipment,
            cartons=None,
        )
    )
    documents.extend(
        render_pack_document_xlsx_documents(
            pack_code="C",
            doc_type="shipment_note",
            render_doc_type="customs_note",
            variant="shipment",
            shipment=shipment,
            cartons=None,
        )
    )
    return documents


def _build_shipment_view_bundle_a5_xlsx_documents(shipment):
    documents = []
    documents.extend(
        render_pack_document_xlsx_documents(
            pack_code="B",
            doc_type="packing_list_shipment",
            variant="shipment",
            shipment=shipment,
            cartons=None,
        )
    )
    for carton in _ordered_shipment_cartons(shipment):
        documents.extend(
            render_pack_document_xlsx_documents(
                pack_code="B",
                doc_type="donation_certificate",
                variant="shipment",
                shipment=shipment,
                cartons=[carton],
            )
        )
        documents.extend(
            render_pack_document_xlsx_documents(
                pack_code="D",
                doc_type="destination_label",
                variant="single_label",
                shipment=shipment,
                cartons=[carton],
            )
        )
        documents.extend(
            render_pack_document_xlsx_documents(
                pack_code="C",
                doc_type="contact_label",
                variant="shipment",
                shipment=shipment,
                cartons=[carton],
            )
        )
    return documents


def _shipment_view_bundle_documents(shipment, bundle_key):
    bundle_key = (bundle_key or "").strip()
    if bundle_key == "a4":
        return _build_shipment_view_bundle_a4_xlsx_documents(shipment), False
    if bundle_key == "a5":
        return _build_shipment_view_bundle_a5_xlsx_documents(shipment), True
    raise Http404("Bundle type not found")


def _shipment_view_bundle_fallback_code(bundle_key):
    return f"SV-{(bundle_key or '').strip().upper() or 'PDF'}"


def _shipment_bundle_action(label, url):
    return {"label": label, "url": url}


def _html_delivery_url(url):
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}delivery=html"


def _render_print_partial(template_name, context):
    return render_to_string(template_name, context)


def _build_shipment_paper_bundle_sections(shipment):
    return [
        {
            "id": "shipment-paper-section-shipment_note",
            "html": _render_print_partial(
                "print/partials/shipment_note_body.html",
                build_shipment_document_context(shipment, "shipment_note"),
            ),
        },
        {
            "id": "shipment-paper-section-customs",
            "html": _render_print_partial(
                "print/partials/customs_note_body.html",
                build_shipment_document_context(shipment, "customs"),
            ),
        },
        {
            "id": "shipment-paper-section-packing_list",
            "html": _render_print_partial(
                "print/partials/packing_list_shipment_body.html",
                build_shipment_document_context(shipment, "packing_list_shipment"),
            ),
        },
    ]


def _build_shipment_label_payload(shipment, carton, *, position, total):
    label_context = build_label_context(shipment, position=position, total=total)
    return {
        "city": label_context["label_city"],
        "iata": label_context["label_iata"],
        "shipment_ref": label_context["label_shipment_ref"],
        "position": label_context["label_position"],
        "total": label_context["label_total"],
        "qr_url": label_context.get("label_qr_url") or "",
        "carton_id": carton.id,
    }


def _build_shipment_standard_label_bundle_items(request, shipment):
    shipment.ensure_qr_code(request=request)
    cartons = _ordered_shipment_cartons(shipment)
    total = len(cartons)
    items = []
    for doc_type in ("contact_label", "shipment_label", "donation_certificate"):
        for position, carton in enumerate(cartons, start=1):
            if doc_type == "contact_label":
                html = _render_print_partial(
                    "print/partials/contact_label_body.html",
                    build_carton_contact_label_context(shipment, carton),
                )
            elif doc_type == "shipment_label":
                html = _render_print_partial(
                    "print/partials/shipment_label_body.html",
                    {
                        "label": _build_shipment_label_payload(
                            shipment,
                            carton,
                            position=position,
                            total=total,
                        )
                    },
                )
            else:
                html = _render_print_partial(
                    "print/partials/donation_certificate_body.html",
                    build_shipment_document_context(shipment, "donation_certificate"),
                )
            items.append(
                {
                    "wrapper_id": f"shipment-standard-labels-item-{doc_type}-{carton.id}",
                    "doc_type": doc_type,
                    "html": html,
                }
            )
    return items


def _shipment_view_bundle_context(request, shipment, bundle_key):
    ordered_cartons = _ordered_shipment_cartons(shipment)
    bundle_key = (bundle_key or "").strip()
    if bundle_key == "all":
        return {
            "template_name": TEMPLATE_SHIPMENT_PRINT_BUNDLE,
            "context": {
                "shipment": shipment,
                "bundle_id": "shipment-print-bundle",
                "bundle_title": _("Imprimer tous les documents d'expédition"),
                "lot_actions": [
                    _shipment_bundle_action(
                        _("Lot papier A4"),
                        f"/scan/shipment/{shipment.id}/print-bundle/paper/",
                    ),
                    _shipment_bundle_action(
                        _("Lot rouleau continu"),
                        f"/scan/shipment/{shipment.id}/print-bundle/carton_lists/",
                    ),
                    _shipment_bundle_action(
                        _("Lot étiquettes standard"),
                        f"/scan/shipment/{shipment.id}/print-bundle/standard_labels/",
                    ),
                ],
            },
        }
    if bundle_key == "paper":
        return {
            "template_name": TEMPLATE_SHIPMENT_BUNDLE_A4,
            "context": {
                "shipment": shipment,
                "bundle_title": _("Lot papier A4"),
                "bundle_sections": _build_shipment_paper_bundle_sections(shipment),
                "hide_footer": True,
            },
        }
    if bundle_key == "carton_lists":
        return {
            "template_name": TEMPLATE_SHIPMENT_PRINT_BUNDLE_LOT,
            "context": {
                "shipment": shipment,
                "bundle_id": "shipment-carton-lists-bundle",
                "bundle_title": _("Lot rouleau continu"),
                "bundle_actions": [],
                "bundle_rows": [
                    {
                        "code": carton.code,
                        "actions": [
                            _shipment_bundle_action(
                                _("Liste colisage"),
                                _html_delivery_url(
                                    reverse(
                                        "scan:scan_shipment_carton_document",
                                        args=[shipment.id, carton.id],
                                    )
                                ),
                            )
                        ],
                    }
                    for carton in ordered_cartons
                ],
            },
        }
    if bundle_key == "standard_labels":
        return {
            "template_name": TEMPLATE_SHIPMENT_BUNDLE_A5_TWO_UP,
            "context": {
                "shipment": shipment,
                "bundle_title": _("Lot étiquettes standard"),
                "bundle_items": _build_shipment_standard_label_bundle_items(request, shipment),
            },
        }
    raise Http404("Bundle type not found")


def _try_generate_pack_pdf_response(
    request,
    *,
    pack_code,
    shipment=None,
    carton=None,
    variant=None,
    fallback_renderer,
):
    try:
        return _generate_pack_pdf_response(
            request,
            pack_code=pack_code,
            shipment=shipment,
            carton=carton,
            variant=variant,
        )
    except GraphPdfConversionError:
        if _is_xlsx_fallback_enabled():
            return _generate_pack_xlsx_response(
                pack_code=pack_code,
                shipment=shipment,
                carton=carton,
                variant=variant,
            )
        return fallback_renderer()
    except PrintPackEngineError:
        return fallback_renderer()


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_document(request, shipment_id, doc_type):
    shipment = _get_shipment_by_id(shipment_id)
    pack_route = resolve_pack_request(doc_type)
    if pack_route:
        render_documents = lambda: _render_pack_xlsx_documents(
            pack_code=pack_route.pack_code,
            shipment=shipment,
            carton=None,
            variant=pack_route.variant,
        )
        if get_local_helper_document_index(request) is not None:
            return build_local_helper_document_response(
                request,
                render_documents=render_documents,
            )
        if is_local_helper_job_request(request):
            return build_local_helper_job_response(
                request,
                pack_code=pack_route.pack_code,
                render_documents=render_documents,
                shipment=shipment,
            )
        if wants_browser_print(request, default=False):
            return render_shipment_document(request, shipment, doc_type)
        return _try_generate_pack_pdf_response(
            request,
            pack_code=pack_route.pack_code,
            shipment=shipment,
            variant=pack_route.variant,
            fallback_renderer=lambda: render_shipment_document(request, shipment, doc_type),
        )
    return render_shipment_document(request, shipment, doc_type)


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_document_public(request, shipment_ref, doc_type):
    shipment = _get_shipment_by_reference(shipment_ref)
    pack_route = resolve_pack_request(doc_type)
    if pack_route:
        render_documents = lambda: _render_pack_xlsx_documents(
            pack_code=pack_route.pack_code,
            shipment=shipment,
            carton=None,
            variant=pack_route.variant,
        )
        if get_local_helper_document_index(request) is not None:
            return build_local_helper_document_response(
                request,
                render_documents=render_documents,
            )
        if is_local_helper_job_request(request):
            return build_local_helper_job_response(
                request,
                pack_code=pack_route.pack_code,
                render_documents=render_documents,
                shipment=shipment,
            )
        return _try_generate_pack_pdf_response(
            request,
            pack_code=pack_route.pack_code,
            shipment=shipment,
            variant=pack_route.variant,
            fallback_renderer=lambda: render_shipment_document(request, shipment, doc_type),
        )
    return render_shipment_document(request, shipment, doc_type)


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_carton_document(request, shipment_id, carton_id):
    shipment = _get_shipment_by_id(shipment_id)
    carton = _get_shipment_carton_or_404(shipment, carton_id)
    pack_route = resolve_carton_packing_pack()
    render_documents = lambda: _render_pack_xlsx_documents(
        pack_code=pack_route.pack_code,
        shipment=shipment,
        carton=carton,
        variant=pack_route.variant,
    )
    if get_local_helper_document_index(request) is not None:
        return build_local_helper_document_response(
            request,
            render_documents=render_documents,
        )
    if is_local_helper_job_request(request):
        return build_local_helper_job_response(
            request,
            pack_code=pack_route.pack_code,
            render_documents=render_documents,
            shipment=shipment,
            carton=carton,
        )
    if wants_browser_print(request, default=False):
        return render_carton_document(request, shipment, carton)
    return _try_generate_pack_pdf_response(
        request,
        pack_code=pack_route.pack_code,
        shipment=shipment,
        carton=carton,
        variant=pack_route.variant,
        fallback_renderer=lambda: render_carton_document(request, shipment, carton),
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_carton_document_public(request, shipment_ref, carton_id):
    shipment = _get_shipment_by_reference(shipment_ref)
    carton = _get_shipment_carton_or_404(shipment, carton_id)
    pack_route = resolve_carton_packing_pack()
    render_documents = lambda: _render_pack_xlsx_documents(
        pack_code=pack_route.pack_code,
        shipment=shipment,
        carton=carton,
        variant=pack_route.variant,
    )
    if get_local_helper_document_index(request) is not None:
        return build_local_helper_document_response(
            request,
            render_documents=render_documents,
        )
    if is_local_helper_job_request(request):
        return build_local_helper_job_response(
            request,
            pack_code=pack_route.pack_code,
            render_documents=render_documents,
            shipment=shipment,
            carton=carton,
        )
    return _try_generate_pack_pdf_response(
        request,
        pack_code=pack_route.pack_code,
        shipment=shipment,
        carton=carton,
        variant=pack_route.variant,
        fallback_renderer=lambda: render_carton_document(request, shipment, carton),
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_carton_document(request, carton_id):
    carton = get_object_or_404(
        Carton.objects.select_related("shipment"),
        pk=carton_id,
    )
    pack_route = resolve_carton_packing_pack()
    if carton.shipment_id:
        fallback_renderer = lambda: render_carton_document(
            request,
            carton.shipment,
            carton,
        )
    else:
        fallback_renderer = lambda: _render_carton_document_with_layout(
            request,
            _build_standalone_carton_context(carton),
        )
    render_documents = lambda: _render_pack_xlsx_documents(
        pack_code=pack_route.pack_code,
        shipment=carton.shipment if carton.shipment_id else None,
        carton=carton,
        variant=pack_route.variant,
    )
    if get_local_helper_document_index(request) is not None:
        return build_local_helper_document_response(
            request,
            render_documents=render_documents,
        )
    if is_local_helper_job_request(request):
        return build_local_helper_job_response(
            request,
            pack_code=pack_route.pack_code,
            render_documents=render_documents,
            shipment=carton.shipment if carton.shipment_id else None,
            carton=carton,
        )
    if wants_browser_print(request, default=False):
        if carton.shipment_id:
            return render_carton_document(
                request,
                carton.shipment,
                carton,
            )
        return _render_carton_document_with_layout(
            request,
            _build_standalone_carton_context(carton),
        )
    return _try_generate_pack_pdf_response(
        request,
        pack_code=pack_route.pack_code,
        shipment=carton.shipment if carton.shipment_id else None,
        carton=carton,
        variant=pack_route.variant,
        fallback_renderer=fallback_renderer,
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_carton_picking(request, carton_id):
    carton = get_object_or_404(
        Carton.objects.prefetch_related(
            "cartonitem_set__product_lot__product",
            "cartonitem_set__product_lot__location",
        ),
        pk=carton_id,
    )
    pack_route = resolve_carton_picking_pack()
    render_documents = lambda: _render_pack_xlsx_documents(
        pack_code=pack_route.pack_code,
        shipment=carton.shipment,
        carton=carton,
        variant=pack_route.variant,
    )
    if get_local_helper_document_index(request) is not None:
        return build_local_helper_document_response(
            request,
            render_documents=render_documents,
        )
    if is_local_helper_job_request(request):
        return build_local_helper_job_response(
            request,
            pack_code=pack_route.pack_code,
            render_documents=render_documents,
            shipment=carton.shipment,
            carton=carton,
        )
    return _try_generate_pack_pdf_response(
        request,
        pack_code=pack_route.pack_code,
        shipment=carton.shipment,
        carton=carton,
        variant=pack_route.variant,
        fallback_renderer=lambda: render(
            request,
            TEMPLATE_PICKING_LIST_CARTON,
            build_carton_picking_context(carton),
        ),
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_cartons_picking(request):
    carton_ids = _parse_carton_ids(request.GET.get("carton_ids"))
    context = build_prepare_kits_picking_context(carton_ids)
    if context is None:
        raise Http404(_("Aucun picking disponible."))
    return render(
        request,
        "print/picking_list_kits.html",
        {
            **context,
            "picking_title": _("Liste picking - colis"),
        },
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_cartons_view_bundle(request, bundle_key):
    carton_ids = _parse_carton_ids(request.GET.get("carton_ids"))
    cartons = list(Carton.objects.filter(id__in=carton_ids).order_by("code", "id"))
    if not cartons:
        raise Http404(_("Aucun carton sélectionné."))
    normalized_bundle_key = (bundle_key or "").strip()
    if normalized_bundle_key != "packing_lists":
        raise Http404(_("Lot de documents introuvable."))
    return render(
        request,
        TEMPLATE_CARTON_PRINT_BUNDLE_LOT,
        {
            "bundle_id": "carton-packing-lists-bundle",
            "bundle_title": _("Lot listes colisage"),
            "bundle_rows": [
                {
                    "code": carton.code,
                    "actions": [
                        {
                            "label": _("Liste colisage"),
                            "url": _html_delivery_url(
                                reverse("scan:scan_carton_document", args=[carton.id])
                            ),
                        }
                    ],
                }
                for carton in cartons
            ],
        },
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_view_document(request, shipment_id, document_key):
    shipment = _get_shipment_by_id(shipment_id)
    normalized_key = (document_key or "").strip()
    html_doc_types = {
        "shipment_note": "shipment_note",
        "customs": "customs",
        "packing_list": "packing_list_shipment",
        "contact": "contact_label",
    }
    if normalized_key in html_doc_types and not wants_external_pdf(request):
        return render_shipment_document(request, shipment, html_doc_types[normalized_key])
    if normalized_key == "contact":
        return render_shipment_document(request, shipment, "contact_label")
    config = _shipment_view_document_or_404(document_key)
    render_documents = lambda: _render_shipment_view_xlsx_documents(shipment, document_key)
    if get_local_helper_document_index(request) is not None:
        return build_local_helper_document_response(
            request,
            render_documents=render_documents,
        )
    if is_local_helper_job_request(request):
        return build_local_helper_job_response(
            request,
            pack_code=config["pack_code"],
            render_documents=render_documents,
            shipment=shipment,
        )

    documents = list(render_documents())
    try:
        return _build_pdf_response_from_xlsx_documents(
            documents,
            filename=f"shipment-view-{document_key}-{shipment.reference}.pdf",
            two_up_on_a4=False,
        )
    except (GraphPdfConversionError, PrintPackEngineError):
        return build_xlsx_fallback_response(
            documents=documents,
            pack_code=config["pack_code"],
        )


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_view_bundle(request, shipment_id, bundle_key):
    shipment = _get_shipment_by_id(shipment_id)
    bundle = _shipment_view_bundle_context(request, shipment, bundle_key)
    return render(
        request,
        bundle["template_name"],
        bundle["context"],
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_donation_certificate(request, shipment_id, carton_id):
    shipment = _get_shipment_by_id(shipment_id)
    _get_shipment_carton_or_404(shipment, carton_id)
    return render_shipment_document(request, shipment, "donation_certificate")


@scan_staff_required
@require_http_methods(["GET"])
def scan_shipment_view_bundle_pdf(request, shipment_id, bundle_key):
    shipment = _get_shipment_by_id(shipment_id)
    render_documents = lambda: _shipment_view_bundle_documents(shipment, bundle_key)[0]
    if get_local_helper_document_index(request) is not None:
        return build_local_helper_document_response(
            request,
            render_documents=render_documents,
        )
    if is_local_helper_job_request(request):
        return build_local_helper_job_response(
            request,
            pack_code=_shipment_view_bundle_fallback_code(bundle_key),
            render_documents=render_documents,
            shipment=shipment,
            output_filename=f"shipment-view-{bundle_key}-{shipment.reference}.pdf",
        )
    documents, two_up_on_a4 = _shipment_view_bundle_documents(shipment, bundle_key)
    try:
        return _build_pdf_response_from_xlsx_documents(
            documents,
            filename=f"shipment-view-{bundle_key}-{shipment.reference}.pdf",
            two_up_on_a4=two_up_on_a4,
        )
    except (GraphPdfConversionError, PrintPackEngineError):
        return build_xlsx_fallback_response(
            documents=documents,
            pack_code=_shipment_view_bundle_fallback_code(bundle_key),
        )


@scan_staff_required
@require_http_methods(["POST"])
def scan_shipment_document_upload(request, shipment_id):
    return handle_shipment_document_upload(request, shipment_id=shipment_id)


@scan_staff_required
@require_http_methods(["POST"])
def scan_shipment_document_delete(request, shipment_id, document_id):
    return handle_shipment_document_delete(
        request, shipment_id=shipment_id, document_id=document_id
    )
