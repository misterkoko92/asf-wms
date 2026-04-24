from wms.portal_order_handlers import create_portal_order


def submit_portal_order(
    *,
    user,
    profile,
    destination_payload,
    notes,
    line_items,
    ready_carton_ids=None,
    inbound_delivery_data=None,
):
    return create_portal_order(
        user=user,
        profile=profile,
        recipient_name=destination_payload["recipient_name"],
        recipient_contact=destination_payload["recipient_contact"],
        destination_address=destination_payload["destination_address"],
        destination_city=destination_payload["destination_city"],
        destination_country=destination_payload["destination_country"],
        notes=notes,
        line_items=line_items,
        ready_carton_ids=ready_carton_ids,
        inbound_delivery_data=inbound_delivery_data,
    )
