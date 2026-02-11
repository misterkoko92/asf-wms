def build_stockmovement_form_response(
    *,
    request,
    admin_site,
    model_meta,
    form,
    title,
    render_fn,
):
    context = {
        **admin_site.each_context(request),
        "opts": model_meta,
        "form": form,
        "title": title,
    }
    return render_fn(request, "admin/wms/stockmovement/form.html", context)


def handle_receive_view(
    *,
    request,
    form_class,
    render_form,
    receive_stock_fn,
    redirect_fn,
    transaction_module,
    message_user,
):
    title = "Réception stock"
    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            product = form.cleaned_data["product"]
            status = form.cleaned_data["status"] or None
            location = form.cleaned_data["location"] or product.default_location
            if location is None:
                form.add_error(
                    "location",
                    "Emplacement requis ou définir un emplacement par défaut.",
                )
                return render_form(request, form, title)
            with transaction_module.atomic():
                lot = receive_stock_fn(
                    user=request.user,
                    product=product,
                    quantity=form.cleaned_data["quantity"],
                    location=location,
                    lot_code=form.cleaned_data["lot_code"] or "",
                    received_on=form.cleaned_data["received_on"],
                    expires_on=form.cleaned_data["expires_on"],
                    status=status,
                    storage_conditions=form.cleaned_data["storage_conditions"],
                )
            message_user(request, "Stock réceptionné et lot créé avec succès.")
            return redirect_fn("admin:wms_productlot_change", lot.id)
    else:
        form = form_class()
    return render_form(request, form, title)


def handle_adjust_view(
    *,
    request,
    form_class,
    render_form,
    adjust_stock_fn,
    stock_error_cls,
    redirect_fn,
    transaction_module,
    message_user,
):
    title = "Ajuster stock"
    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            lot = form.cleaned_data["product_lot"]
            delta = form.cleaned_data["quantity_delta"]
            try:
                with transaction_module.atomic():
                    adjust_stock_fn(
                        user=request.user,
                        lot=lot,
                        delta=delta,
                        reason_code=form.cleaned_data["reason_code"] or "",
                        reason_notes=form.cleaned_data["reason_notes"] or "",
                    )
                message_user(request, "Ajustement de stock enregistré.")
                return redirect_fn("admin:wms_productlot_change", lot.id)
            except stock_error_cls:
                form.add_error(
                    "quantity_delta",
                    "Stock insuffisant pour appliquer cette correction.",
                )
    else:
        form = form_class()
    return render_form(request, form, title)


def handle_transfer_view(
    *,
    request,
    form_class,
    render_form,
    transfer_stock_fn,
    stock_error_cls,
    redirect_fn,
    transaction_module,
    message_user,
):
    title = "Transférer stock"
    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            lot = form.cleaned_data["product_lot"]
            to_location = form.cleaned_data["to_location"]
            try:
                with transaction_module.atomic():
                    transfer_stock_fn(
                        user=request.user,
                        lot=lot,
                        to_location=to_location,
                    )
                message_user(request, "Transfert de stock enregistré.")
                return redirect_fn("admin:wms_productlot_change", lot.id)
            except stock_error_cls:
                form.add_error("to_location", "Le lot est déjà à cet emplacement.")
    else:
        form = form_class()
    return render_form(request, form, title)


def _map_pack_error_to_field(error_message):
    if "Carton deja lie" in error_message or "Carton déjà lié" in error_message:
        return "shipment"
    if "Stock insuffisant" in error_message:
        return "quantity"
    lowered = error_message.lower()
    if "carton expedie" in lowered or "carton expédié" in lowered:
        return "carton"
    if "expedition expediee" in lowered or "expédition expédiée" in lowered:
        return "shipment"
    return None


def handle_pack_view(
    *,
    request,
    form_class,
    render_form,
    pack_carton_fn,
    stock_error_cls,
    redirect_fn,
    transaction_module,
    message_user,
):
    title = "Préparer carton"
    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            with transaction_module.atomic():
                product = form.cleaned_data["product"]
                quantity = form.cleaned_data["quantity"]
                carton = form.cleaned_data["carton"]
                carton_code = form.cleaned_data["carton_code"]
                shipment = form.cleaned_data["shipment"]
                current_location = form.cleaned_data["current_location"]
                try:
                    carton = pack_carton_fn(
                        user=request.user,
                        product=product,
                        quantity=quantity,
                        carton=carton,
                        carton_code=carton_code,
                        shipment=shipment,
                        current_location=current_location,
                    )
                except stock_error_cls as exc:
                    message = str(exc)
                    form.add_error(_map_pack_error_to_field(message), message)
                    return render_form(request, form, title)

            message_user(request, "Carton préparé avec succès.")
            return redirect_fn("admin:wms_carton_change", carton.id)
    else:
        form = form_class()
    return render_form(request, form, title)
