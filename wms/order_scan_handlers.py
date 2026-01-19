from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from .models import Order, OrderStatus
from .scan_helpers import resolve_product
from .services import (
    StockError,
    create_shipment_for_order,
    prepare_order,
    reserve_stock_for_order,
)


def get_order_state(order):
    if not order:
        return [], 0
    order_lines = list(order.lines.select_related("product"))
    remaining_total = sum(line.remaining_quantity for line in order_lines)
    return order_lines, remaining_total


def handle_order_action(
    request,
    *,
    action,
    select_form,
    create_form,
    line_form,
    selected_order,
):
    if action == "select_order" and select_form.is_valid():
        order = select_form.cleaned_data["order"]
        return redirect(f"{reverse('scan:scan_order')}?order={order.id}"), None, None

    if action == "create_order" and create_form.is_valid():
        shipper_contact = create_form.cleaned_data["shipper_contact"]
        recipient_contact = create_form.cleaned_data["recipient_contact"]
        correspondent_contact = create_form.cleaned_data["correspondent_contact"]
        order = Order.objects.create(
            reference="",
            status=OrderStatus.DRAFT,
            shipper_name=create_form.cleaned_data["shipper_name"]
            or (shipper_contact.name if shipper_contact else ""),
            recipient_name=create_form.cleaned_data["recipient_name"]
            or (recipient_contact.name if recipient_contact else ""),
            correspondent_name=create_form.cleaned_data["correspondent_name"]
            or (correspondent_contact.name if correspondent_contact else ""),
            shipper_contact=shipper_contact,
            recipient_contact=recipient_contact,
            correspondent_contact=correspondent_contact,
            destination_address=create_form.cleaned_data["destination_address"],
            destination_city=create_form.cleaned_data["destination_city"] or "",
            destination_country=create_form.cleaned_data["destination_country"] or "France",
            requested_delivery_date=create_form.cleaned_data["requested_delivery_date"],
            created_by=request.user,
            notes=create_form.cleaned_data["notes"] or "",
        )
        create_shipment_for_order(order=order)
        messages.success(
            request,
            f"Commande creee: {order.reference or f'Commande {order.id}'}",
        )
        return redirect(f"{reverse('scan:scan_order')}?order={order.id}"), None, None

    if action == "add_line":
        if not selected_order:
            line_form.add_error(None, "Selectionnez une commande.")
        elif selected_order.status in {OrderStatus.CANCELLED, OrderStatus.READY}:
            line_form.add_error(None, "Commande annulee.")
        elif selected_order.status == OrderStatus.PREPARING:
            line_form.add_error(None, "Commande en preparation.")
        elif line_form.is_valid():
            product = resolve_product(line_form.cleaned_data["product_code"])
            if not product:
                line_form.add_error("product_code", "Produit introuvable.")
            else:
                line, _ = selected_order.lines.get_or_create(
                    product=product, defaults={"quantity": 0}
                )
                previous_qty = line.quantity
                line.quantity += line_form.cleaned_data["quantity"]
                line.save(update_fields=["quantity"])
                try:
                    reserve_stock_for_order(order=selected_order)
                    messages.success(
                        request,
                        f"Ligne reservee: {product.name} ({line_form.cleaned_data['quantity']}).",
                    )
                except StockError as exc:
                    line.quantity = previous_qty
                    if line.quantity <= 0:
                        line.delete()
                    else:
                        line.save(update_fields=["quantity"])
                    line_form.add_error(None, str(exc))
                    order_lines, remaining_total = get_order_state(selected_order)
                    return None, order_lines, remaining_total
                return (
                    redirect(
                        f"{reverse('scan:scan_order')}?order={selected_order.id}"
                    ),
                    None,
                    None,
                )

    if action == "prepare_order" and selected_order:
        try:
            prepare_order(user=request.user, order=selected_order)
            messages.success(request, "Commande preparee.")
        except StockError as exc:
            messages.error(request, str(exc))
        return (
            redirect(f"{reverse('scan:scan_order')}?order={selected_order.id}"),
            None,
            None,
        )

    return None, None, None
