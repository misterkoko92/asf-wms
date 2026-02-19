from .contact_filters import TAG_CORRESPONDENT, TAG_RECIPIENT, TAG_SHIPPER
from .scan_helpers import (
    build_available_cartons,
    build_product_options,
    build_shipment_line_values,
)
from .shipment_helpers import build_shipment_contact_payload
from .view_utils import resolve_contact_by_name


def build_shipment_form_payload():
    product_options = build_product_options()
    available_cartons = build_available_cartons()
    (
        destinations_json,
        shipper_contacts_json,
        recipient_contacts_json,
        correspondent_contacts_json,
    ) = build_shipment_contact_payload()
    return (
        product_options,
        available_cartons,
        destinations_json,
        shipper_contacts_json,
        recipient_contacts_json,
        correspondent_contacts_json,
    )


def build_carton_selection_data(available_cartons, assigned_carton_options=None):
    if not assigned_carton_options:
        allowed_carton_ids = {str(carton["id"]) for carton in available_cartons}
        return list(available_cartons), allowed_carton_ids
    cartons_by_id = {str(carton["id"]): carton for carton in available_cartons}
    for carton in assigned_carton_options:
        cartons_by_id.setdefault(str(carton["id"]), carton)
    return list(cartons_by_id.values()), set(cartons_by_id.keys())


def _build_order_line_product_code(order_line):
    product = getattr(order_line, "product", None)
    if not product:
        return ""
    sku = (getattr(product, "sku", "") or "").strip()
    if sku:
        return sku
    return (getattr(product, "name", "") or "").strip()


def build_shipment_order_line_values(order_lines):
    values = []
    for order_line in order_lines or []:
        quantity = (
            getattr(order_line, "remaining_quantity", None)
            if hasattr(order_line, "remaining_quantity")
            else None
        )
        if quantity is None:
            quantity = getattr(order_line, "quantity", 0)
        try:
            quantity_value = int(quantity or 0)
        except (TypeError, ValueError):
            quantity_value = 0
        if quantity_value <= 0:
            continue

        product_code = _build_order_line_product_code(order_line)
        if not product_code:
            continue

        values.append(
            {
                "carton_id": "",
                "product_code": product_code,
                "quantity": str(quantity_value),
            }
        )
    return values


def build_shipment_edit_initial(shipment, assigned_cartons, *, order_line_count=0):
    shipper_contact = getattr(shipment, "shipper_contact_ref", None) or resolve_contact_by_name(
        TAG_SHIPPER,
        shipment.shipper_name,
    )
    recipient_contact = getattr(shipment, "recipient_contact_ref", None) or resolve_contact_by_name(
        TAG_RECIPIENT,
        shipment.recipient_name,
    )
    correspondent_contact = None
    if shipment.destination and shipment.destination.correspondent_contact_id:
        correspondent_contact = shipment.destination.correspondent_contact
    else:
        correspondent_contact = getattr(shipment, "correspondent_contact_ref", None) or resolve_contact_by_name(
            TAG_CORRESPONDENT,
            shipment.correspondent_name,
        )

    return {
        "destination": shipment.destination_id,
        "shipper_contact": shipper_contact.id if shipper_contact else None,
        "recipient_contact": recipient_contact.id if recipient_contact else None,
        "correspondent_contact": correspondent_contact.id
        if correspondent_contact
        else None,
        "carton_count": max(1, len(assigned_cartons), int(order_line_count or 0)),
    }


def build_shipment_edit_line_values(assigned_cartons, carton_count, *, order_line_values=None):
    if assigned_cartons:
        return [
            {"carton_id": carton.id, "product_code": "", "quantity": ""}
            for carton in assigned_cartons
        ]
    if order_line_values:
        return list(order_line_values[:carton_count])
    return build_shipment_line_values(carton_count)


def build_shipment_form_context(
    *,
    form,
    product_options,
    cartons_json,
    carton_count,
    line_values,
    line_errors,
    destinations_json,
    shipper_contacts_json,
    recipient_contacts_json,
    correspondent_contacts_json,
):
    return {
        "form": form,
        "products_json": product_options,
        "cartons_json": cartons_json,
        "carton_count": carton_count,
        "line_values": line_values,
        "line_errors": line_errors,
        "destinations_json": destinations_json,
        "shipper_contacts_json": shipper_contacts_json,
        "recipient_contacts_json": recipient_contacts_json,
        "correspondent_contacts_json": correspondent_contacts_json,
    }
