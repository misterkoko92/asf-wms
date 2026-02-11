import json

from django.contrib import messages
from django.db import transaction
from django.db.models import Max
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import PrintTemplate, PrintTemplateVersion, Product, Shipment
from .print_context import (
    build_label_context,
    build_preview_context,
    build_product_label_context,
    build_sample_label_context,
)
from .print_layouts import BLOCK_LIBRARY, DEFAULT_LAYOUTS, DOCUMENT_TEMPLATES
from .print_renderer import layout_changed, render_layout_from_layout
from .print_utils import build_label_pages, extract_block_style
from .view_permissions import (
    require_superuser as _require_superuser,
    scan_staff_required,
)

TEMPLATE_PRINT_TEMPLATE_LIST = "scan/print_template_list.html"
TEMPLATE_PRINT_TEMPLATE_EDIT = "scan/print_template_edit.html"
TEMPLATE_DYNAMIC_LABELS = "print/dynamic_labels.html"
TEMPLATE_DYNAMIC_DOCUMENT = "print/dynamic_document.html"
TEMPLATE_PRODUCT_LABELS = "print/product_labels.html"
TEMPLATE_PRODUCT_QR_LABELS = "print/product_qr_labels.html"

ACTIVE_PRINT_TEMPLATES = "print_templates"
SHELL_CLASS_WIDE = "scan-shell-wide"

DOC_LABEL_MAP = dict(DOCUMENT_TEMPLATES)
PRODUCT_DOC_TYPES = {"product_label", "product_qr"}


def _redirect_template_edit(doc_type):
    return redirect("scan:scan_print_template_edit", doc_type=doc_type)


def _load_print_template(doc_type):
    return (
        PrintTemplate.objects.filter(doc_type=doc_type)
        .select_related("updated_by")
        .first()
    )


def _resolve_edit_layout_data(request, *, action, doc_type, template):
    if action == "restore":
        version_id = request.POST.get("version_id")
        if not version_id:
            messages.error(request, "Version requise.")
            return None, _redirect_template_edit(doc_type)
        version = get_object_or_404(
            PrintTemplateVersion, pk=version_id, template__doc_type=doc_type
        )
        return version.layout or {}, None

    if action == "reset":
        if template is None:
            messages.info(request, "Ce modèle est déjà sur la version par défaut.")
            return None, _redirect_template_edit(doc_type)
        return {}, None

    layout_json = request.POST.get("layout_json") or ""
    try:
        return json.loads(layout_json) if layout_json else {}, None
    except json.JSONDecodeError:
        messages.error(request, "Le layout fourni est invalide.")
        return None, _redirect_template_edit(doc_type)


def _save_template_layout(*, template, doc_type, layout_data, user):
    with transaction.atomic():
        if template is None:
            template = PrintTemplate.objects.create(
                doc_type=doc_type,
                layout=layout_data,
                updated_by=user,
            )
        else:
            template.layout = layout_data
            template.updated_by = user
            template.save(update_fields=["layout", "updated_by", "updated_at"])

        next_version = (
            template.versions.aggregate(max_version=Max("version"))["max_version"] or 0
        ) + 1
        PrintTemplateVersion.objects.create(
            template=template,
            version=next_version,
            layout=layout_data,
            created_by=user,
        )
    return template


def _notify_edit_success(request, *, action):
    if action == "reset":
        messages.success(request, "Modèle remis par défaut.")
    elif action == "restore":
        messages.success(request, "Version restaurée.")
    else:
        messages.success(request, "Modèle enregistré.")


def _build_template_list_items():
    template_map = {
        template.doc_type: template
        for template in PrintTemplate.objects.select_related("updated_by")
    }
    items = []
    for doc_type, label in DOCUMENT_TEMPLATES:
        template = template_map.get(doc_type)
        items.append(
            {
                "doc_type": doc_type,
                "label": label,
                "has_override": bool(template and template.layout),
                "updated_at": template.updated_at if template else None,
                "updated_by": template.updated_by if template else None,
            }
        )
    return items


def _build_shipment_choices():
    shipments = []
    for shipment in Shipment.objects.select_related("destination").order_by(
        "reference", "id"
    )[:30]:
        destination = (
            shipment.destination.city
            if shipment.destination and shipment.destination.city
            else shipment.destination_address
        )
        label = shipment.reference
        if destination:
            label = f"{label} - {destination}"
        shipments.append({"id": shipment.id, "label": label})
    shipments.sort(key=lambda item: str(item["label"] or "").lower())
    return shipments


def _build_product_choices(doc_type):
    if doc_type not in PRODUCT_DOC_TYPES:
        return []

    products = []
    for product in Product.objects.order_by("name")[:30]:
        label = product.name
        if product.sku:
            label = f"{product.sku} - {label}"
        products.append({"id": product.id, "label": label})
    products.sort(key=lambda item: str(item["label"] or "").lower())
    return products


def _build_template_versions(template):
    if template is None:
        return []
    return list(template.versions.select_related("created_by").order_by("-version"))


def _build_edit_context(*, doc_type, template):
    default_layout = DEFAULT_LAYOUTS.get(doc_type, {"blocks": []})
    layout = template.layout if template and template.layout else default_layout
    return {
        "active": ACTIVE_PRINT_TEMPLATES,
        "shell_class": SHELL_CLASS_WIDE,
        "doc_type": doc_type,
        "doc_label": DOC_LABEL_MAP[doc_type],
        "template": template,
        "layout": layout,
        "block_library": BLOCK_LIBRARY,
        "shipments": _build_shipment_choices(),
        "products": _build_product_choices(doc_type),
        "versions": _build_template_versions(template),
    }


def _parse_preview_layout(request):
    layout_json = request.POST.get("layout_json") or ""
    try:
        return (json.loads(layout_json) if layout_json else {"blocks": []}), None
    except json.JSONDecodeError:
        return None, HttpResponse(status=400)


def _load_preview_shipment(raw_shipment_id):
    if not raw_shipment_id.isdigit():
        return None
    return (
        Shipment.objects.select_related("destination")
        .prefetch_related("carton_set")
        .filter(pk=int(raw_shipment_id))
        .first()
    )


def _load_preview_product(raw_product_id):
    if not raw_product_id.isdigit():
        return None
    return (
        Product.objects.select_related("default_location", "default_location__warehouse")
        .filter(pk=int(raw_product_id))
        .first()
    )


def _render_shipment_label_preview(request, *, layout_data, shipment):
    labels = []
    if shipment:
        cartons = list(shipment.carton_set.order_by("code")[:6])
        total = shipment.carton_set.count() or 1
        if cartons:
            for index, _carton in enumerate(cartons, start=1):
                label_context = build_label_context(shipment, position=index, total=total)
                blocks = render_layout_from_layout(layout_data, label_context)
                labels.append({"blocks": blocks})
        else:
            label_context = build_sample_label_context()
            blocks = render_layout_from_layout(layout_data, label_context)
            labels.append({"blocks": blocks})
    else:
        label_context = build_sample_label_context()
        blocks = render_layout_from_layout(layout_data, label_context)
        labels.append({"blocks": blocks})
    return render(request, TEMPLATE_DYNAMIC_LABELS, {"labels": labels})


def _render_product_label_preview(request, *, layout_data, product):
    if product:
        base_context = build_product_label_context(product)
    else:
        base_context = build_preview_context("product_label")
    contexts = [dict(base_context) for _ in range(4)]
    pages, page_style = build_label_pages(
        layout_data,
        contexts,
        block_type="product_label",
        labels_per_page=4,
    )
    return render(
        request,
        TEMPLATE_PRODUCT_LABELS,
        {"pages": pages, "page_style": page_style},
    )


def _resolve_product_qr_grid(layout_data):
    page_style = extract_block_style(layout_data, "product_qr_label")
    try:
        rows = int(page_style.get("page_rows") or 5)
        cols = int(page_style.get("page_columns") or 3)
    except (TypeError, ValueError):
        rows, cols = 5, 3
    return max(1, rows * cols)


def _render_product_qr_preview(request, *, layout_data, product):
    if product:
        if not product.qr_code_image:
            product.generate_qr_code()
            product.save(update_fields=["qr_code_image"])
        base_context = build_preview_context("product_qr", product=product)
    else:
        base_context = build_preview_context("product_qr")
    labels_per_page = _resolve_product_qr_grid(layout_data)
    contexts = [dict(base_context) for _ in range(labels_per_page)]
    pages, page_style = build_label_pages(
        layout_data,
        contexts,
        block_type="product_qr_label",
        labels_per_page=labels_per_page,
    )
    return render(
        request,
        TEMPLATE_PRODUCT_QR_LABELS,
        {"pages": pages, "page_style": page_style},
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_print_templates(request):
    _require_superuser(request)
    return render(
        request,
        TEMPLATE_PRINT_TEMPLATE_LIST,
        {
            "active": ACTIVE_PRINT_TEMPLATES,
            "shell_class": SHELL_CLASS_WIDE,
            "templates": _build_template_list_items(),
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_print_template_edit(request, doc_type):
    _require_superuser(request)
    if doc_type not in DOC_LABEL_MAP:
        raise Http404("Template not found")

    template = _load_print_template(doc_type)
    if request.method == "POST":
        action = (request.POST.get("action") or "save").strip()
        layout_data, response = _resolve_edit_layout_data(
            request,
            action=action,
            doc_type=doc_type,
            template=template,
        )
        if response:
            return response

        previous_layout = template.layout if template else None
        if not layout_changed(previous_layout, layout_data):
            messages.info(request, "Aucun changement detecte.")
            return _redirect_template_edit(doc_type)

        _save_template_layout(
            template=template,
            doc_type=doc_type,
            layout_data=layout_data,
            user=request.user,
        )
        _notify_edit_success(request, action=action)
        return _redirect_template_edit(doc_type)

    return render(
        request,
        TEMPLATE_PRINT_TEMPLATE_EDIT,
        _build_edit_context(doc_type=doc_type, template=template),
    )


@scan_staff_required
@require_http_methods(["POST"])
def scan_print_template_preview(request):
    _require_superuser(request)
    doc_type = (request.POST.get("doc_type") or "").strip()
    if doc_type not in DOC_LABEL_MAP:
        raise Http404("Template not found")

    layout_data, response = _parse_preview_layout(request)
    if response:
        return response

    shipment = _load_preview_shipment(request.POST.get("shipment_id") or "")
    if doc_type == "shipment_label":
        return _render_shipment_label_preview(
            request,
            layout_data=layout_data,
            shipment=shipment,
        )

    product = _load_preview_product(request.POST.get("product_id") or "")
    if doc_type == "product_label":
        return _render_product_label_preview(
            request,
            layout_data=layout_data,
            product=product,
        )
    if doc_type == "product_qr":
        return _render_product_qr_preview(
            request,
            layout_data=layout_data,
            product=product,
        )

    context = build_preview_context(doc_type, shipment=shipment)
    blocks = render_layout_from_layout(layout_data, context)
    return render(request, TEMPLATE_DYNAMIC_DOCUMENT, {"blocks": blocks})
