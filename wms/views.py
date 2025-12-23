from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.db import connection, transaction
from django.db.models import DateTimeField, F, IntegerField, Max, OuterRef, Q, Subquery, Sum
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce
from django.utils import timezone

from .forms import (
    ScanOutForm,
    ScanPackForm,
    ScanReceiptCreateForm,
    ScanReceiptAssociationForm,
    ScanReceiptLineForm,
    ScanReceiptPalletForm,
    ScanReceiptSelectForm,
    ScanStockUpdateForm,
    ScanOrderCreateForm,
    ScanOrderLineForm,
    ScanOrderSelectForm,
    ScanShipmentForm,
)
from .models import (
    Carton,
    CartonStatus,
    MovementType,
    Product,
    ProductCategory,
    ProductLot,
    Receipt,
    ReceiptHorsFormat,
    ReceiptStatus,
    ReceiptType,
    Order,
    OrderStatus,
    Shipment,
    ShipmentStatus,
    StockMovement,
    Warehouse,
    WmsChange,
)
from .scan_helpers import (
    build_available_cartons,
    build_carton_formats,
    build_location_data,
    build_pack_line_values,
    build_packing_bins,
    build_packing_result,
    build_product_options,
    build_shipment_line_values,
    parse_int,
    resolve_default_warehouse,
    resolve_carton_size,
    resolve_product,
    resolve_shipment,
)
from .services import (
    StockError,
    consume_stock,
    create_shipment_for_order,
    pack_carton,
    prepare_order,
    receive_receipt_line,
    receive_stock,
    reserve_stock_for_order,
)


@login_required
def scan_stock(request):
    query = (request.GET.get("q") or "").strip()
    category_id = (request.GET.get("category") or "").strip()
    warehouse_id = (request.GET.get("warehouse") or "").strip()
    sort = (request.GET.get("sort") or "name").strip()

    products = Product.objects.filter(is_active=True).select_related("category")
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(barcode__icontains=query)
            | Q(brand__icontains=query)
        )
    if category_id:
        products = products.filter(category_id=category_id)

    available_expr = ExpressionWrapper(
        F("quantity_on_hand") - F("quantity_reserved"),
        output_field=IntegerField(),
    )
    stock_lots = ProductLot.objects.filter(
        product_id=OuterRef("pk"),
        quantity_on_hand__gt=0,
    )
    if warehouse_id:
        stock_lots = stock_lots.filter(location__warehouse_id=warehouse_id)
    stock_total_subquery = (
        stock_lots.values("product_id")
        .annotate(total=Sum(available_expr))
        .values("total")
    )

    movements = StockMovement.objects.filter(product_id=OuterRef("pk"))
    if warehouse_id:
        movements = movements.filter(
            Q(to_location__warehouse_id=warehouse_id)
            | Q(from_location__warehouse_id=warehouse_id)
        )
    last_movement_subquery = (
        movements.values("product_id")
        .annotate(last=Max("created_at"))
        .values("last")
    )

    products = products.annotate(
        stock_total=Coalesce(Subquery(stock_total_subquery, output_field=IntegerField()), 0),
        last_movement_at=Subquery(last_movement_subquery, output_field=DateTimeField()),
    ).filter(stock_total__gt=0)

    sort_map = {
        "name": "name",
        "sku": "sku",
        "qty_desc": "-stock_total",
        "qty_asc": "stock_total",
        "category": "category__name",
    }
    products = products.order_by(sort_map.get(sort, "name"), "name")

    categories = ProductCategory.objects.all().order_by("name")
    warehouses = Warehouse.objects.all().order_by("name")

    return render(
        request,
        "scan/stock.html",
        {
            "active": "stock",
            "products": products,
            "categories": categories,
            "warehouses": warehouses,
            "query": query,
            "category_id": category_id,
            "warehouse_id": warehouse_id,
            "sort": sort,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_stock_update(request):
    product_options = build_product_options()
    location_data = build_location_data()
    create_form = ScanStockUpdateForm(request.POST or None)
    if request.method == "POST" and create_form.is_valid():
        product = getattr(create_form, "product", None)
        location = product.default_location if product else None
        if location is None:
            create_form.add_error(None, "Emplacement requis pour ce produit.")
        else:
            try:
                receive_stock(
                    user=request.user,
                    product=product,
                    quantity=create_form.cleaned_data["quantity"],
                    location=location,
                    lot_code=create_form.cleaned_data["lot_code"] or "",
                    received_on=timezone.localdate(),
                    expires_on=create_form.cleaned_data["expires_on"],
                    source_receipt=create_form.cleaned_data["donor_receipt"],
                )
                messages.success(request, "Stock mis a jour.")
                return redirect("scan:scan_stock_update")
            except StockError as exc:
                create_form.add_error(None, str(exc))
    return render(
        request,
        "scan/stock_update.html",
        {
            "active": "stock_update",
            "create_form": create_form,
            "products_json": product_options,
            "location_data": location_data,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_receive(request):
    product_options = build_product_options()
    action = request.POST.get("action", "")
    receipts_qs = Receipt.objects.select_related("warehouse").order_by(
        "-received_on", "-created_at"
    )[:50]
    select_form = ScanReceiptSelectForm(
        request.POST if action == "select_receipt" else None, receipts_qs=receipts_qs
    )
    create_form = ScanReceiptCreateForm(
        request.POST if action == "create_receipt" else None
    )

    receipt_id = request.GET.get("receipt") or request.POST.get("receipt_id")
    selected_receipt = None
    if receipt_id:
        selected_receipt = Receipt.objects.filter(id=receipt_id).first()

    line_form = ScanReceiptLineForm(
        request.POST if action == "add_line" else None,
        initial={"receipt_id": selected_receipt.id} if selected_receipt else None,
    )
    receipt_lines = []
    pending_count = 0
    if selected_receipt:
        receipt_lines = list(
            selected_receipt.lines.select_related("product", "location", "received_lot").all()
        )
        pending_count = sum(1 for line in receipt_lines if not line.received_lot_id)

    if request.method == "POST":
        if action == "select_receipt" and select_form.is_valid():
            receipt = select_form.cleaned_data["receipt"]
            return redirect(f"{reverse('scan:scan_receive')}?receipt={receipt.id}")
        if action == "create_receipt" and create_form.is_valid():
            receipt = Receipt.objects.create(
                reference="",
                receipt_type=create_form.cleaned_data["receipt_type"],
                status=ReceiptStatus.DRAFT,
                source_contact=create_form.cleaned_data["source_contact"],
                carrier_contact=create_form.cleaned_data["carrier_contact"],
                origin_reference=create_form.cleaned_data["origin_reference"],
                carrier_reference=create_form.cleaned_data["carrier_reference"],
                received_on=create_form.cleaned_data["received_on"],
                warehouse=create_form.cleaned_data["warehouse"],
                created_by=request.user,
                notes=create_form.cleaned_data["notes"] or "",
            )
            messages.success(
                request,
                f"Reception creee: {receipt.reference or f'Reception {receipt.id}'}",
            )
            return redirect(f"{reverse('scan:scan_receive')}?receipt={receipt.id}")
        if action == "add_line":
            if not selected_receipt:
                line_form.add_error(None, "Selectionnez une reception.")
            elif selected_receipt.status != ReceiptStatus.DRAFT:
                line_form.add_error(None, "Reception deja cloturee.")
            elif line_form.is_valid():
                product = resolve_product(line_form.cleaned_data["product_code"])
                if not product:
                    line_form.add_error("product_code", "Produit introuvable.")
                else:
                    location = (
                        line_form.cleaned_data["location"] or product.default_location
                    )
                    if location is None:
                        line_form.add_error(
                            "location",
                            "Emplacement requis ou definir un emplacement par defaut.",
                        )
                    else:
                        line = selected_receipt.lines.create(
                            product=product,
                            quantity=line_form.cleaned_data["quantity"],
                            lot_code=line_form.cleaned_data["lot_code"] or "",
                            expires_on=line_form.cleaned_data["expires_on"],
                            lot_status=line_form.cleaned_data["lot_status"] or "",
                            location=location,
                            storage_conditions=(
                                line_form.cleaned_data["storage_conditions"]
                                or product.storage_conditions
                            ),
                        )
                        if line_form.cleaned_data["receive_now"]:
                            try:
                                receive_receipt_line(user=request.user, line=line)
                                messages.success(
                                    request,
                                    f"Ligne receptionnee: {product.name} ({line.quantity}).",
                                )
                            except StockError as exc:
                                line_form.add_error(None, str(exc))
                                return render(
                                    request,
                                    "scan/receive.html",
                                    {
                                        "active": "receive",
                                        "products_json": product_options,
                                        "select_form": select_form,
                                        "create_form": create_form,
                                        "line_form": line_form,
                                        "selected_receipt": selected_receipt,
                                        "receipt_lines": receipt_lines,
                                        "pending_count": pending_count,
                                    },
                                )
                        else:
                            messages.success(
                                request,
                                f"Ligne ajoutee: {product.name} ({line.quantity}).",
                            )
                        return redirect(
                            f"{reverse('scan:scan_receive')}?receipt={selected_receipt.id}"
                        )
        if action == "receive_lines" and selected_receipt:
            processed = 0
            errors = []
            for line in selected_receipt.lines.select_related("product"):
                if line.received_lot_id:
                    continue
                try:
                    receive_receipt_line(user=request.user, line=line)
                    processed += 1
                except StockError as exc:
                    errors.append(str(exc))
            if processed:
                messages.success(
                    request, f"{processed} ligne(s) receptionnee(s)."
                )
            for error in errors:
                messages.error(request, error)
            return redirect(f"{reverse('scan:scan_receive')}?receipt={selected_receipt.id}")
    return render(
        request,
        "scan/receive.html",
        {
            "active": "receive",
            "products_json": product_options,
            "select_form": select_form,
            "create_form": create_form,
            "line_form": line_form,
            "selected_receipt": selected_receipt,
            "receipt_lines": receipt_lines,
            "pending_count": pending_count,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_receive_pallet(request):
    create_form = ScanReceiptPalletForm(request.POST or None)
    if request.method == "POST" and create_form.is_valid():
        warehouse = resolve_default_warehouse()
        if not warehouse:
            create_form.add_error(None, "Aucun entrepot configure.")
        else:
            receipt = Receipt.objects.create(
                receipt_type=ReceiptType.PALLET,
                status=ReceiptStatus.DRAFT,
                source_contact=create_form.cleaned_data["source_contact"],
                carrier_contact=create_form.cleaned_data["carrier_contact"],
                received_on=create_form.cleaned_data["received_on"],
                pallet_count=create_form.cleaned_data["pallet_count"],
                transport_request_date=create_form.cleaned_data[
                    "transport_request_date"
                ],
                warehouse=warehouse,
                created_by=request.user,
            )
            messages.success(
                request,
                f"Reception palette enregistree (ref {receipt.reference}).",
            )
            return redirect("scan:scan_receive_pallet")

    return render(
        request,
        "scan/receive_pallet.html",
        {
            "active": "receive_pallet",
            "create_form": create_form,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_receive_association(request):
    line_errors = {}
    line_count = parse_int(request.POST.get("hors_format_count")) or 0
    line_count = max(0, line_count)
    line_values = []
    for index in range(1, line_count + 1):
        description = (request.POST.get(f"line_{index}_description") or "").strip()
        line_values.append({"description": description})

    create_form = ScanReceiptAssociationForm(request.POST or None)
    if request.method == "POST" and create_form.is_valid():
        for index, line in enumerate(line_values, start=1):
            if not line["description"]:
                line_errors[str(index)] = ["Description requise."]

        if line_errors:
            create_form.add_error(None, "Renseignez les descriptions hors format.")
        else:
            warehouse = resolve_default_warehouse()
            if not warehouse:
                create_form.add_error(None, "Aucun entrepot configure.")
            else:
                receipt = Receipt.objects.create(
                    receipt_type=ReceiptType.ASSOCIATION,
                    status=ReceiptStatus.DRAFT,
                    source_contact=create_form.cleaned_data["source_contact"],
                    carrier_contact=create_form.cleaned_data["carrier_contact"],
                    received_on=create_form.cleaned_data["received_on"],
                    carton_count=create_form.cleaned_data["carton_count"],
                    hors_format_count=line_count or None,
                    warehouse=warehouse,
                    created_by=request.user,
                )
                for index, line in enumerate(line_values, start=1):
                    if line["description"]:
                        ReceiptHorsFormat.objects.create(
                            receipt=receipt,
                            line_number=index,
                            description=line["description"],
                        )
                messages.success(
                    request,
                    f"Reception association enregistree (ref {receipt.reference}).",
                )
                return redirect("scan:scan_receive_association")

    return render(
        request,
        "scan/receive_association.html",
        {
            "active": "receive_association",
            "create_form": create_form,
            "line_count": line_count,
            "line_values": line_values,
            "line_errors": line_errors,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_order(request):
    product_options = build_product_options()
    action = request.POST.get("action", "")
    orders_qs = Order.objects.select_related("shipment").order_by("-created_at")[:50]
    select_form = ScanOrderSelectForm(
        request.POST if action == "select_order" else None, orders_qs=orders_qs
    )
    create_form = ScanOrderCreateForm(
        request.POST if action == "create_order" else None
    )

    order_id = request.GET.get("order") or request.POST.get("order_id")
    selected_order = None
    if order_id:
        selected_order = Order.objects.select_related("shipment").filter(id=order_id).first()

    line_form = ScanOrderLineForm(
        request.POST if action == "add_line" else None,
        initial={"order_id": selected_order.id} if selected_order else None,
    )
    order_lines = []
    remaining_total = 0
    if selected_order:
        order_lines = list(selected_order.lines.select_related("product"))
        remaining_total = sum(line.remaining_quantity for line in order_lines)

    if request.method == "POST":
        if action == "select_order" and select_form.is_valid():
            order = select_form.cleaned_data["order"]
            return redirect(f"{reverse('scan:scan_order')}?order={order.id}")
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
            return redirect(f"{reverse('scan:scan_order')}?order={order.id}")
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
                    line, created = selected_order.lines.get_or_create(
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
                        return render(
                            request,
                            "scan/order.html",
                            {
                                "active": "order",
                                "products_json": product_options,
                                "select_form": select_form,
                                "create_form": create_form,
                                "line_form": line_form,
                                "selected_order": selected_order,
                                "order_lines": order_lines,
                                "remaining_total": remaining_total,
                            },
                        )
                    return redirect(f"{reverse('scan:scan_order')}?order={selected_order.id}")
        if action == "prepare_order" and selected_order:
            try:
                prepare_order(user=request.user, order=selected_order)
                messages.success(request, "Commande preparee.")
            except StockError as exc:
                messages.error(request, str(exc))
            return redirect(f"{reverse('scan:scan_order')}?order={selected_order.id}")

    return render(
        request,
        "scan/order.html",
        {
            "active": "order",
            "products_json": product_options,
            "select_form": select_form,
            "create_form": create_form,
            "line_form": line_form,
            "selected_order": selected_order,
            "order_lines": order_lines,
            "remaining_total": remaining_total,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_pack(request):
    form = ScanPackForm(request.POST or None)
    product_options = build_product_options()
    carton_formats, default_format = build_carton_formats()
    carton_errors = []
    line_errors = {}
    line_items = []
    packing_result = None

    packed_carton_ids = request.session.pop("pack_results", None)
    if packed_carton_ids:
        packing_result = build_packing_result(packed_carton_ids)

    if request.method == "POST":
        carton_format_id = (request.POST.get("carton_format_id") or "").strip()
        carton_custom = {
            "length_cm": request.POST.get("carton_length_cm", ""),
            "width_cm": request.POST.get("carton_width_cm", ""),
            "height_cm": request.POST.get("carton_height_cm", ""),
            "max_weight_g": request.POST.get("carton_max_weight_g", ""),
        }
        line_count = parse_int(request.POST.get("line_count")) or 1
        line_count = max(1, line_count)
        line_values = build_pack_line_values(line_count, request.POST)
        carton_size, carton_errors = resolve_carton_size(
            carton_format_id=carton_format_id, default_format=default_format, data=request.POST
        )
        if not carton_format_id:
            carton_format_id = (
                str(default_format.id) if default_format is not None else "custom"
            )

        if form.is_valid():
            shipment = resolve_shipment(form.cleaned_data["shipment_reference"])
            if form.cleaned_data["shipment_reference"] and not shipment:
                form.add_error("shipment_reference", "Expedition introuvable.")
            if carton_errors:
                for error in carton_errors:
                    form.add_error(None, error)

            for index in range(1, line_count + 1):
                prefix = f"line_{index}_"
                product_code = (request.POST.get(prefix + "product_code") or "").strip()
                quantity_raw = (request.POST.get(prefix + "quantity") or "").strip()
                if not product_code and not quantity_raw:
                    continue
                errors = []
                if not product_code:
                    errors.append("Produit requis.")
                quantity = None
                if not quantity_raw:
                    errors.append("Quantite requise.")
                else:
                    quantity = parse_int(quantity_raw)
                    if quantity is None or quantity <= 0:
                        errors.append("Quantite invalide.")
                product = resolve_product(product_code) if product_code else None
                if product_code and not product:
                    errors.append("Produit introuvable.")
                if errors:
                    line_errors[str(index)] = errors
                else:
                    line_items.append({"product": product, "quantity": quantity, "index": index})

            if form.is_valid() and not line_errors and not carton_errors:
                if not line_items:
                    form.add_error(None, "Ajoutez au moins un produit.")
                else:
                    bins, pack_errors, pack_warnings = build_packing_bins(
                        line_items, carton_size
                    )
                    if pack_errors:
                        for error in pack_errors:
                            form.add_error(None, error)
                    else:
                        try:
                            created_cartons = []
                            with transaction.atomic():
                                for bin_data in bins:
                                    carton = None
                                    for entry in bin_data["items"].values():
                                        carton = pack_carton(
                                            user=request.user,
                                            product=entry["product"],
                                            quantity=entry["quantity"],
                                            carton=carton,
                                            carton_code=None,
                                            shipment=shipment,
                                            current_location=form.cleaned_data[
                                                "current_location"
                                            ],
                                        )
                                    if carton:
                                        created_cartons.append(carton)
                            for warning in pack_warnings:
                                messages.warning(request, warning)
                            request.session["pack_results"] = [
                                carton.id for carton in created_cartons
                            ]
                            messages.success(
                                request,
                                f"{len(created_cartons)} carton(s) prepare(s).",
                            )
                            return redirect("scan:scan_pack")
                        except StockError as exc:
                            form.add_error(None, str(exc))
    else:
        carton_format_id = (
            str(default_format.id) if default_format is not None else "custom"
        )
        carton_custom = {
            "length_cm": default_format.length_cm if default_format else Decimal("40"),
            "width_cm": default_format.width_cm if default_format else Decimal("30"),
            "height_cm": default_format.height_cm if default_format else Decimal("30"),
            "max_weight_g": default_format.max_weight_g if default_format else 8000,
        }
        line_count = 1
        line_values = build_pack_line_values(line_count)
    return render(
        request,
        "scan/pack.html",
        {
            "form": form,
            "active": "pack",
            "products_json": product_options,
            "carton_formats": carton_formats,
            "carton_format_id": carton_format_id,
            "carton_custom": carton_custom,
            "line_count": line_count,
            "line_values": line_values,
            "line_errors": line_errors,
            "packing_result": packing_result,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_shipment_create(request):
    form = ScanShipmentForm(request.POST or None)
    product_options = build_product_options()
    available_cartons = build_available_cartons()
    available_carton_ids = {str(carton["id"]) for carton in available_cartons}
    line_errors = {}
    line_items = []

    if request.method == "POST":
        carton_count = form.cleaned_data["carton_count"] if form.is_valid() else 1
        if not form.is_valid():
            try:
                carton_count = max(1, int(request.POST.get("carton_count", 1)))
            except (TypeError, ValueError):
                carton_count = 1
        line_values = build_shipment_line_values(carton_count, request.POST)

        for index in range(1, carton_count + 1):
            prefix = f"line_{index}_"
            carton_id = (request.POST.get(prefix + "carton_id") or "").strip()
            product_code = (request.POST.get(prefix + "product_code") or "").strip()
            quantity_raw = (request.POST.get(prefix + "quantity") or "").strip()
            errors = []

            if carton_id and (product_code or quantity_raw):
                errors.append("Choisissez un carton OU creez un colis depuis un produit.")
            elif carton_id:
                if carton_id not in available_carton_ids:
                    errors.append("Carton indisponible.")
                else:
                    line_items.append({"carton_id": int(carton_id)})
            elif product_code or quantity_raw:
                if not product_code:
                    errors.append("Produit requis.")
                quantity = None
                if not quantity_raw:
                    errors.append("Quantite requise.")
                else:
                    try:
                        quantity = int(quantity_raw)
                        if quantity <= 0:
                            errors.append("Quantite invalide.")
                    except ValueError:
                        errors.append("Quantite invalide.")
                if product_code:
                    product = resolve_product(product_code)
                    if not product:
                        errors.append("Produit introuvable.")
                else:
                    product = None
                if not errors and product and quantity:
                    line_items.append({"product": product, "quantity": quantity})
            else:
                errors.append("Renseignez un carton ou un produit.")

            if errors:
                line_errors[str(index)] = errors

        if form.is_valid() and not line_errors:
            try:
                with transaction.atomic():
                    shipment = Shipment.objects.create(
                        status=ShipmentStatus.DRAFT,
                        shipper_name=form.cleaned_data["shipper_name"],
                        recipient_name=form.cleaned_data["recipient_name"],
                        correspondent_name=form.cleaned_data["correspondent_name"],
                        destination_address=form.cleaned_data["destination_address"],
                        destination_country="France",
                        created_by=request.user,
                    )
                    for item in line_items:
                        carton_id = item.get("carton_id")
                        if carton_id:
                            carton_query = Carton.objects.filter(
                                id=carton_id,
                                status=CartonStatus.READY,
                                shipment__isnull=True,
                            )
                            if connection.features.has_select_for_update:
                                carton_query = carton_query.select_for_update()
                            carton = carton_query.first()
                            if carton is None:
                                raise StockError("Carton indisponible.")
                            carton.shipment = shipment
                            carton.status = CartonStatus.ASSIGNED
                            carton.save(update_fields=["shipment", "status"])
                        else:
                            pack_carton(
                                user=request.user,
                                product=item["product"],
                                quantity=item["quantity"],
                                carton=None,
                                carton_code=None,
                                shipment=shipment,
                            )
                messages.success(
                    request,
                    f"Expedition creee: {shipment.reference}.",
                )
                return redirect("scan:scan_shipment_create")
            except StockError as exc:
                form.add_error(None, str(exc))
    else:
        carton_count = form.initial.get("carton_count", 1)
        line_values = build_shipment_line_values(carton_count)

    return render(
        request,
        "scan/shipment_create.html",
        {
            "form": form,
            "active": "shipment",
            "products_json": product_options,
            "cartons_json": available_cartons,
            "carton_count": carton_count,
            "line_values": line_values,
            "line_errors": line_errors,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def scan_out(request):
    form = ScanOutForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        product = resolve_product(form.cleaned_data["product_code"])
        if not product:
            form.add_error("product_code", "Produit introuvable.")
        else:
            shipment = resolve_shipment(form.cleaned_data["shipment_reference"])
            if form.cleaned_data["shipment_reference"] and not shipment:
                form.add_error("shipment_reference", "Expedition introuvable.")
            else:
                try:
                    with transaction.atomic():
                        consume_stock(
                            user=request.user,
                            product=product,
                            quantity=form.cleaned_data["quantity"],
                            movement_type=MovementType.OUT,
                            shipment=shipment,
                            reason_code=form.cleaned_data["reason_code"] or "scan_out",
                            reason_notes=form.cleaned_data["reason_notes"] or "",
                        )
                    messages.success(
                        request,
                        f"Suppression enregistree: {product.name} ({form.cleaned_data['quantity']}).",
                    )
                    return redirect("scan:scan_out")
                except StockError as exc:
                    form.add_error(None, str(exc))
    return render(request, "scan/out.html", {"form": form, "active": "out"})


@login_required
@require_http_methods(["GET"])
def scan_sync(request):
    state = WmsChange.get_state()
    return JsonResponse(
        {
            "version": state.version,
            "changed_at": state.last_changed_at.isoformat(),
        }
    )


SERVICE_WORKER_JS = """const CACHE_NAME = 'wms-scan-v17';
const ASSETS = [
  '/scan/',
  '/static/scan/scan.css',
  '/static/scan/scan.js',
  '/static/scan/manifest.json',
  '/static/scan/icon.svg'
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') {
    return;
  }
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});
"""


def scan_service_worker(request):
    response = HttpResponse(SERVICE_WORKER_JS, content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/scan/"
    return response
