from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from .forms import (
    ScanIncompleteProductBulkUpdateForm,
    ScanIncompleteProductForm,
    ScanReceiptAssociationForm,
)
from .forms_billing import ReceiptShipmentAllocationForm
from .incomplete_products import (
    apply_incomplete_products_bulk_update,
    build_incomplete_products_context,
    build_incomplete_products_queryset,
)
from .models import (
    Order,
    OrderReviewStatus,
    Product,
    Receipt,
    ReceiptShipmentAllocation,
    ReceiptType,
)
from .order_helpers import attach_order_documents_to_shipment
from .receipt_detail_helpers import build_receipt_detail_payload
from .receipt_handlers import (
    build_hors_format_lines,
    handle_receipt_action,
    handle_receipt_association_post,
)
from .receipt_list_queries import build_receipts_list_context
from .receipt_listing_state import (
    build_receive_listing_context,
    build_receive_listing_state,
)
from .receipt_pallet_state import (
    build_receive_pallet_context,
    build_receive_pallet_state,
)
from .receipt_scan_state import build_receipt_scan_state
from .scan_helpers import build_product_options
from .services import create_shipment_for_order
from .status_presenters import present_shipment_status
from .view_permissions import scan_staff_required

TEMPLATE_RECEIPTS_VIEW = "scan/receipts_view.html"
TEMPLATE_RECEIVE = "scan/receive.html"
TEMPLATE_RECEIVE_PALLET = "scan/receive_pallet.html"
TEMPLATE_RECEIVE_LISTING = "scan/receive_listing.html"
TEMPLATE_RECEIVE_ASSOCIATION = "scan/receive_association.html"
TEMPLATE_RECEIPT_DETAIL = "scan/receipt_detail.html"

ACTIVE_RECEIPTS_VIEW = "receipts_view"
ACTIVE_RECEIVE = "receive"
ACTIVE_RECEIVE_ASSOCIATION = "receive_association"


def _safe_next_url(request, *, default):
    candidate = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return default


def _render_scan_receive(request, *, product_options, receipt_state):
    return render(
        request,
        TEMPLATE_RECEIVE,
        {
            "active": ACTIVE_RECEIVE,
            "products_json": product_options,
            "select_form": receipt_state["select_form"],
            "create_form": receipt_state["create_form"],
            "line_form": receipt_state["line_form"],
            "selected_receipt": receipt_state["selected_receipt"],
            "receipt_lines": receipt_state["receipt_lines"],
            "pending_count": receipt_state["pending_count"],
        },
    )


def _render_receive_association(
    request,
    *,
    create_form,
    line_count,
    line_values,
    line_errors,
    selected_receipt,
    allocation_form,
    receipt_allocations,
):
    return render(
        request,
        TEMPLATE_RECEIVE_ASSOCIATION,
        {
            "active": ACTIVE_RECEIVE_ASSOCIATION,
            "create_form": create_form,
            "line_count": line_count,
            "line_values": line_values,
            "line_errors": line_errors,
            "selected_receipt": selected_receipt,
            "allocation_form": allocation_form,
            "receipt_allocations": receipt_allocations,
            "workflow_context": _build_receive_association_workflow_context(
                request=request,
                selected_receipt=selected_receipt,
            ),
        },
    )


def _selected_association_receipt(request):
    receipt_id = (request.POST.get("receipt_id") or request.GET.get("receipt_id") or "").strip()
    if not receipt_id:
        return None
    return get_object_or_404(
        Receipt.objects.select_related("source_contact", "carrier_contact"),
        pk=receipt_id,
        receipt_type=ReceiptType.ASSOCIATION,
    )


def _build_receipt_allocation_rows(receipt):
    if receipt is None:
        return []
    return list(
        ReceiptShipmentAllocation.objects.select_related("shipment", "created_by")
        .filter(receipt=receipt)
        .order_by("shipment__reference", "id")
    )


def _requested_inbound_order(request):
    raw_order_id = (request.POST.get("order_id") or request.GET.get("order_id") or "").strip()
    if not raw_order_id:
        return None
    try:
        order_id = int(raw_order_id)
    except (TypeError, ValueError):
        return None
    return (
        Order.objects.filter(id=order_id, inbound_delivery__isnull=False)
        .select_related("association_contact", "inbound_delivery__receipt")
        .prefetch_related(
            "shipment_links__shipment",
            "inbound_delivery__receipt__shipper_cartons",
        )
        .first()
    )


def _workflow_order_for_receipt(*, request, selected_receipt):
    if selected_receipt is not None:
        try:
            inbound_delivery = selected_receipt.order_inbound_delivery
        except AttributeError:
            inbound_delivery = None
        except type(selected_receipt).order_inbound_delivery.RelatedObjectDoesNotExist:
            inbound_delivery = None
        if inbound_delivery is not None:
            return (
                Order.objects.filter(id=inbound_delivery.order_id)
                .select_related("association_contact", "inbound_delivery__receipt")
                .prefetch_related(
                    "shipment_links__shipment",
                    "inbound_delivery__receipt__shipper_cartons",
                )
                .first()
            )
    return _requested_inbound_order(request)


def _build_receive_association_workflow_context(*, request, selected_receipt):
    order = _workflow_order_for_receipt(request=request, selected_receipt=selected_receipt)
    if order is None:
        return None
    inbound_delivery = getattr(order, "inbound_delivery", None)
    receipt = selected_receipt or getattr(inbound_delivery, "receipt", None)
    linked_shipments = []
    for link in order.shipment_links.all():
        shipment = getattr(link, "shipment", None)
        if shipment is None:
            continue
        linked_shipments.append(
            {
                "id": shipment.id,
                "reference": shipment.reference,
                "status_label": present_shipment_status(shipment)["label"],
            }
        )
    shipper_cartons = list(receipt.shipper_cartons.all()) if receipt is not None else []
    return {
        "order": order,
        "reference_label": order.reference or f"CMD-{order.id}",
        "receipt": receipt,
        "declared_carton_count": int(getattr(inbound_delivery, "declared_carton_count", 0) or 0),
        "can_create_linked_shipment": (
            bool(receipt is not None) and order.review_status == OrderReviewStatus.APPROVED
        ),
        "linked_shipments": linked_shipments,
        "shipper_received_unassigned_carton_count": sum(
            1 for carton in shipper_cartons if not getattr(carton, "shipment_id", None)
        ),
    }


@scan_staff_required
@require_http_methods(["GET"])
def scan_receipts_view(request):
    return render(
        request,
        TEMPLATE_RECEIPTS_VIEW,
        {
            "active": ACTIVE_RECEIPTS_VIEW,
            **build_receipts_list_context(request),
        },
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_receipt_detail(request, receipt_id):
    receipt = get_object_or_404(
        Receipt.objects.select_related(
            "source_contact", "carrier_contact", "warehouse"
        ).prefetch_related(
            "lines__product",
            "lines__location",
            "hors_format_items",
            "shipment_allocations__shipment",
        ),
        id=receipt_id,
    )
    return render(
        request,
        TEMPLATE_RECEIPT_DETAIL,
        {
            "active": ACTIVE_RECEIPTS_VIEW,
            "detail": build_receipt_detail_payload(receipt),
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_receive(request):
    product_options = build_product_options()
    action = request.POST.get("action", "")
    receipt_state = build_receipt_scan_state(request, action=action)

    if request.method == "POST":
        response, handler_lines, handler_pending = handle_receipt_action(
            request,
            action=action,
            select_form=receipt_state["select_form"],
            create_form=receipt_state["create_form"],
            line_form=receipt_state["line_form"],
            selected_receipt=receipt_state["selected_receipt"],
        )
        if response:
            return response
        if handler_lines is not None:
            receipt_state["receipt_lines"] = handler_lines
            receipt_state["pending_count"] = handler_pending
    return _render_scan_receive(
        request,
        product_options=product_options,
        receipt_state=receipt_state,
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_receive_pallet(request):
    action = request.POST.get("action", "")
    state = build_receive_pallet_state(request, action=action)
    if state["response"]:
        return state["response"]

    return render(
        request,
        TEMPLATE_RECEIVE_PALLET,
        build_receive_pallet_context(state),
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_receive_listing(request):
    action = request.POST.get("action", "")
    listing_action = action if action.startswith("listing_") else ""
    state = build_receive_listing_state(request, action=listing_action)
    if state["response"]:
        return state["response"]

    context = build_receive_listing_context(state)
    last_import_product_ids = (
        request.session.get("pallet_listing_last_incomplete_product_ids") or []
    )
    queryset = build_incomplete_products_queryset(product_ids=last_import_product_ids)
    bulk_form = None
    if (
        request.method == "POST"
        and action == "bulk_update_incomplete_products"
        and last_import_product_ids
    ):
        bulk_form = ScanIncompleteProductBulkUpdateForm(
            request.POST,
            product_queryset=queryset,
        )
        if bulk_form.is_valid():
            updated_count, field_name = apply_incomplete_products_bulk_update(
                form=bulk_form,
                product_ids=last_import_product_ids,
            )
            messages.success(
                request,
                f"{updated_count} produit(s) incomplet(s) mis à jour ({field_name}).",
            )
            queryset = build_incomplete_products_queryset(product_ids=last_import_product_ids)
            bulk_form = ScanIncompleteProductBulkUpdateForm(product_queryset=queryset)

    incomplete_products_context = build_incomplete_products_context(
        queryset=queryset,
        bulk_form=bulk_form,
        action_url=reverse("scan:scan_receive_listing"),
        edit_next_url=reverse("scan:scan_receive_listing"),
        card_id="scan-receive-listing-incomplete-products-card",
    )
    context.update(
        {
            "show_incomplete_products_card": bool(
                incomplete_products_context["incomplete_products"]
            ),
            **incomplete_products_context,
        }
    )
    if context["show_incomplete_products_card"] and context.get("listing_focus_card_id") in {
        None,
        "",
        "scan-receive-listing-intake-card",
    }:
        context["listing_focus_card_id"] = "scan-receive-listing-incomplete-products-card"
    return render(request, TEMPLATE_RECEIVE_LISTING, context)


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_receive_listing_product_edit(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    default_next_url = reverse("scan:scan_receive_listing")
    next_url = _safe_next_url(request, default=default_next_url)
    form = ScanIncompleteProductForm(request.POST or None, instance=product)
    if request.method == "POST" and (request.POST.get("action") or "").strip() == "save":
        if form.is_valid():
            updated_product = form.save(commit=False)
            updated_product.is_incomplete = False
            updated_product.save()
            messages.success(request, f"Produit {updated_product.name} complété.")
            return redirect(next_url)

    return render(
        request,
        "scan/receive_listing_product_edit.html",
        {
            "active": (
                "stock_update"
                if next_url.startswith(reverse("scan:scan_stock_update"))
                else "receive_listing"
            ),
            "product": product,
            "form": form,
            "next_url": next_url,
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_receive_association(request):
    action = (request.POST.get("action") or "").strip()
    selected_receipt = _selected_association_receipt(request)
    line_count, line_values = (
        build_hors_format_lines(request) if action != "add_allocation" else (0, [])
    )
    line_errors = {}
    requested_order = _requested_inbound_order(request)
    create_form_initial = {}
    if requested_order is not None:
        create_form_initial["inbound_delivery_order"] = requested_order.id
        if requested_order.association_contact_id:
            create_form_initial["source_contact"] = requested_order.association_contact_id
    create_form = (
        ScanReceiptAssociationForm(
            request.POST or None,
            request.FILES or None,
            initial=create_form_initial,
        )
        if request.method != "POST" or action != "add_allocation"
        else ScanReceiptAssociationForm(initial=create_form_initial)
    )
    allocation_form = (
        ReceiptShipmentAllocationForm(request.POST or None, receipt=selected_receipt)
        if selected_receipt is not None
        else None
    )
    if request.method == "POST":
        if action == "create_linked_shipment":
            order = _workflow_order_for_receipt(request=request, selected_receipt=selected_receipt)
            if order is None:
                messages.error(request, "Commande expéditeur introuvable.")
            elif order.review_status != OrderReviewStatus.APPROVED:
                messages.error(request, "Commande non validée.")
            else:
                shipment = create_shipment_for_order(order=order, force_new=True)
                attach_order_documents_to_shipment(order, shipment)
                messages.success(
                    request,
                    f"Expédition {shipment.reference} créée depuis la réception association.",
                )
                return redirect("scan:scan_shipment_edit", shipment_id=shipment.id)
        elif action == "add_allocation" and selected_receipt is not None:
            allocation_form = ReceiptShipmentAllocationForm(request.POST, receipt=selected_receipt)
            if allocation_form.is_valid():
                allocation = allocation_form.save(commit=False)
                allocation.receipt = selected_receipt
                allocation.created_by = request.user
                allocation.save()
                messages.success(
                    request,
                    f"Allocation ajoutée vers expédition {allocation.shipment.reference}.",
                )
                return redirect(
                    f"{reverse('scan:scan_receive_association')}?receipt_id={selected_receipt.id}"
                )
        else:
            response, line_errors = handle_receipt_association_post(
                request,
                create_form=create_form,
                line_values=line_values,
                line_count=line_count,
            )
            if response:
                return response

    return _render_receive_association(
        request,
        create_form=create_form,
        line_count=line_count,
        line_values=line_values,
        line_errors=line_errors,
        selected_receipt=selected_receipt,
        allocation_form=allocation_form,
        receipt_allocations=_build_receipt_allocation_rows(selected_receipt),
    )
