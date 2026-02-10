def sync_carton_shipment_stock_movements(
    *,
    obj,
    original,
    stock_movement_model,
    movement_type_out,
    created_by,
):
    if original and original.shipment_id != obj.shipment_id:
        if obj.shipment:
            stock_movement_model.objects.filter(
                related_carton=obj,
                movement_type=movement_type_out,
            ).update(related_shipment=obj.shipment)
        else:
            stock_movement_model.objects.filter(
                related_carton=obj,
                movement_type=movement_type_out,
            ).update(related_shipment=None)

    if not obj.shipment:
        return
    if stock_movement_model.objects.filter(
        related_carton=obj,
        movement_type=movement_type_out,
    ).exists():
        return

    items = list(
        obj.cartonitem_set.select_related(
            "product_lot",
            "product_lot__product",
        )
    )
    if not items:
        return
    for item in items:
        stock_movement_model.objects.create(
            movement_type=movement_type_out,
            product=item.product_lot.product,
            product_lot=item.product_lot,
            quantity=item.quantity,
            from_location=item.product_lot.location,
            related_carton=obj,
            related_shipment=obj.shipment,
            created_by=created_by,
        )


def unpack_cartons_batch(
    *,
    queryset,
    user,
    unpack_carton_fn,
    stock_error_cls,
    transaction_module,
):
    unpacked = 0
    skipped = 0
    with transaction_module.atomic():
        for carton in queryset.select_related("shipment"):
            try:
                unpack_carton_fn(user=user, carton=carton)
                unpacked += 1
            except stock_error_cls:
                skipped += 1
    return unpacked, skipped
