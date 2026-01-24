import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
from .view_permissions import require_superuser as _require_superuser


@login_required
@require_http_methods(["GET"])
def scan_print_templates(request):
    _require_superuser(request)
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
    return render(
        request,
        "scan/print_template_list.html",
        {
            "active": "print_templates",
            "shell_class": "scan-shell-wide",
            "templates": items,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_print_template_edit(request, doc_type):
    _require_superuser(request)
    doc_map = dict(DOCUMENT_TEMPLATES)
    if doc_type not in doc_map:
        raise Http404("Template not found")

    template = (
        PrintTemplate.objects.filter(doc_type=doc_type)
        .select_related("updated_by")
        .first()
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "save").strip()
        layout_data = None

        if action == "restore":
            version_id = request.POST.get("version_id")
            if not version_id:
                messages.error(request, "Version requise.")
                return redirect("scan:scan_print_template_edit", doc_type=doc_type)
            version = get_object_or_404(
                PrintTemplateVersion, pk=version_id, template__doc_type=doc_type
            )
            layout_data = version.layout or {}
        elif action == "reset":
            if template is None:
                messages.info(request, "Ce modele est deja sur la version par defaut.")
                return redirect("scan:scan_print_template_edit", doc_type=doc_type)
            layout_data = {}
        else:
            layout_json = request.POST.get("layout_json") or ""
            try:
                layout_data = json.loads(layout_json) if layout_json else {}
            except json.JSONDecodeError:
                messages.error(request, "Le layout fourni est invalide.")
                return redirect("scan:scan_print_template_edit", doc_type=doc_type)

        previous_layout = template.layout if template else None
        if not layout_changed(previous_layout, layout_data):
            messages.info(request, "Aucun changement detecte.")
            return redirect("scan:scan_print_template_edit", doc_type=doc_type)

        with transaction.atomic():
            if template is None:
                template = PrintTemplate.objects.create(
                    doc_type=doc_type,
                    layout=layout_data,
                    updated_by=request.user,
                )
            else:
                template.layout = layout_data
                template.updated_by = request.user
                template.save(update_fields=["layout", "updated_by", "updated_at"])

            next_version = (
                template.versions.aggregate(max_version=Max("version"))["max_version"]
                or 0
            ) + 1
            PrintTemplateVersion.objects.create(
                template=template,
                version=next_version,
                layout=layout_data,
                created_by=request.user,
            )

        if action == "reset":
            messages.success(request, "Modele remis par defaut.")
        elif action == "restore":
            messages.success(request, "Version restauree.")
        else:
            messages.success(request, "Modele enregistre.")
        return redirect("scan:scan_print_template_edit", doc_type=doc_type)

    default_layout = DEFAULT_LAYOUTS.get(doc_type, {"blocks": []})
    layout = template.layout if template and template.layout else default_layout

    shipments = []
    for shipment in Shipment.objects.select_related("destination").order_by(
        "reference", "id"
    )[:30]:
        dest = (
            shipment.destination.city
            if shipment.destination and shipment.destination.city
            else shipment.destination_address
        )
        label = shipment.reference
        if dest:
            label = f"{label} - {dest}"
        shipments.append({"id": shipment.id, "label": label})
    shipments.sort(key=lambda item: str(item["label"] or "").lower())

    products = []
    if doc_type in {"product_label", "product_qr"}:
        for product in Product.objects.order_by("name")[:30]:
            label = product.name
            if product.sku:
                label = f"{product.sku} - {label}"
            products.append({"id": product.id, "label": label})
        products.sort(key=lambda item: str(item["label"] or "").lower())

    versions = []
    if template:
        versions = list(
            template.versions.select_related("created_by").order_by("-version")
        )

    return render(
        request,
        "scan/print_template_edit.html",
        {
            "active": "print_templates",
            "shell_class": "scan-shell-wide",
            "doc_type": doc_type,
            "doc_label": doc_map[doc_type],
            "template": template,
            "layout": layout,
            "block_library": BLOCK_LIBRARY,
            "shipments": shipments,
            "products": products,
            "versions": versions,
        },
    )


@login_required
@require_http_methods(["POST"])
def scan_print_template_preview(request):
    _require_superuser(request)
    doc_type = (request.POST.get("doc_type") or "").strip()
    if doc_type not in dict(DOCUMENT_TEMPLATES):
        raise Http404("Template not found")

    layout_json = request.POST.get("layout_json") or ""
    try:
        layout_data = json.loads(layout_json) if layout_json else {"blocks": []}
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    shipment_id = request.POST.get("shipment_id") or ""
    shipment = None
    if shipment_id.isdigit():
        shipment = (
            Shipment.objects.select_related("destination")
            .prefetch_related("carton_set")
            .filter(pk=int(shipment_id))
            .first()
        )

    if doc_type == "shipment_label":
        labels = []
        if shipment:
            cartons = list(shipment.carton_set.order_by("code")[:6])
            total = shipment.carton_set.count() or 1
            if not cartons:
                label_context = build_sample_label_context()
                blocks = render_layout_from_layout(layout_data, label_context)
                labels.append({"blocks": blocks})
            else:
                for index, _carton in enumerate(cartons, start=1):
                    label_context = build_label_context(
                        shipment, position=index, total=total
                    )
                    blocks = render_layout_from_layout(layout_data, label_context)
                    labels.append({"blocks": blocks})
        else:
            label_context = build_sample_label_context()
            blocks = render_layout_from_layout(layout_data, label_context)
            labels.append({"blocks": blocks})

        return render(request, "print/dynamic_labels.html", {"labels": labels})

    if doc_type == "product_label":
        product_id = request.POST.get("product_id") or ""
        product = None
        if product_id.isdigit():
            product = (
                Product.objects.select_related("default_location", "default_location__warehouse")
                .filter(pk=int(product_id))
                .first()
            )
        if product:
            base_context = build_product_label_context(product)
        else:
            base_context = build_preview_context(doc_type)
        contexts = [dict(base_context) for _ in range(4)]
        pages, page_style = build_label_pages(
            layout_data,
            contexts,
            block_type="product_label",
            labels_per_page=4,
        )
        return render(
            request,
            "print/product_labels.html",
            {"pages": pages, "page_style": page_style},
        )
    if doc_type == "product_qr":
        product_id = request.POST.get("product_id") or ""
        product = None
        if product_id.isdigit():
            product = (
                Product.objects.select_related("default_location", "default_location__warehouse")
                .filter(pk=int(product_id))
                .first()
            )
        if product:
            if not product.qr_code_image:
                product.generate_qr_code()
                product.save(update_fields=["qr_code_image"])
            base_context = build_preview_context(doc_type, product=product)
        else:
            base_context = build_preview_context(doc_type)
        page_style = extract_block_style(layout_data, "product_qr_label")
        try:
            rows = int(page_style.get("page_rows") or 5)
            cols = int(page_style.get("page_columns") or 3)
        except (TypeError, ValueError):
            rows, cols = 5, 3
        labels_per_page = max(1, rows * cols)
        contexts = [dict(base_context) for _ in range(labels_per_page)]
        pages, page_style = build_label_pages(
            layout_data,
            contexts,
            block_type="product_qr_label",
            labels_per_page=labels_per_page,
        )
        return render(
            request,
            "print/product_qr_labels.html",
            {"pages": pages, "page_style": page_style},
        )

    context = build_preview_context(doc_type, shipment=shipment)
    blocks = render_layout_from_layout(layout_data, context)
    return render(request, "print/dynamic_document.html", {"blocks": blocks})
