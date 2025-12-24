from django.contrib import admin, messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone

from . import models
from django.utils.html import format_html

from .documents import (
    build_carton_rows,
    build_org_context,
    build_shipment_aggregate_rows,
    build_shipment_item_rows,
)
from .forms import AdjustStockForm, PackCartonForm, ReceiveStockForm, TransferStockForm
from .contact_filters import TAG_CORRESPONDENT, contacts_with_tags
from .services import (
    StockError,
    adjust_stock,
    create_shipment_for_order,
    pack_carton,
    prepare_order,
    receive_stock,
    receive_receipt_line,
    reserve_stock_for_order,
    transfer_stock,
    unpack_carton,
)


@admin.register(models.ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")
    search_fields = ("name",)
    list_select_related = ("parent",)


@admin.register(models.ProductTag)
class ProductTagAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "brand",
        "category",
        "default_location",
        "perishable",
        "quarantine_default",
        "is_active",
    )
    list_filter = (
        "is_active",
        "perishable",
        "quarantine_default",
        "category",
        "brand",
        "tags",
    )
    search_fields = ("sku", "name", "barcode", "brand")
    filter_horizontal = ("tags",)
    list_select_related = ("category", "default_location")
    readonly_fields = ("sku", "qr_code_preview")
    fields = (
        "sku",
        "name",
        "brand",
        "category",
        "tags",
        "barcode",
        "default_location",
        "length_cm",
        "width_cm",
        "height_cm",
        "weight_g",
        "volume_cm3",
        "storage_conditions",
        "perishable",
        "quarantine_default",
        "is_active",
        "qr_code_preview",
        "qr_code_image",
        "notes",
    )
    actions = ("archive_products", "unarchive_products", "generate_qr_codes")

    def qr_code_preview(self, obj):
        if obj.qr_code_image:
            return format_html(
                '<img src="{}" style="height: 120px; border: 1px solid #ccc;" />',
                obj.qr_code_image.url,
            )
        return "-"

    qr_code_preview.short_description = "QR code"

    def archive_products(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} produit(s) archives.")

    archive_products.short_description = "Archiver les produits"

    def unarchive_products(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} produit(s) reactives.")

    unarchive_products.short_description = "Reactiver les produits"

    def generate_qr_codes(self, request, queryset):
        count = 0
        for product in queryset:
            if not product.qr_code_image:
                product.generate_qr_code()
                product.save(update_fields=["qr_code_image"])
                count += 1
        self.message_user(request, f"{count} QR code(s) generes.")

    generate_qr_codes.short_description = "Generer les QR codes"


@admin.register(models.Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(models.Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "zone", "aisle", "shelf")
    list_filter = ("warehouse",)
    search_fields = ("warehouse__name", "zone", "aisle", "shelf")


class ReceiptLineInline(admin.TabularInline):
    model = models.ReceiptLine
    extra = 0
    autocomplete_fields = ("product", "location")
    fields = (
        "product",
        "quantity",
        "lot_code",
        "expires_on",
        "lot_status",
        "location",
        "storage_conditions",
        "received_lot",
        "received_at",
    )
    readonly_fields = ("received_lot", "received_at")


class ReceiptHorsFormatInline(admin.TabularInline):
    model = models.ReceiptHorsFormat
    extra = 0
    fields = ("line_number", "description")


@admin.register(models.Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "receipt_type",
        "status",
        "received_on",
        "pallet_count",
        "carton_count",
        "warehouse",
        "source_contact",
        "carrier_contact",
        "transport_request_date",
    )
    list_filter = ("receipt_type", "status", "warehouse")
    search_fields = (
        "reference",
        "origin_reference",
        "carrier_reference",
        "source_contact__name",
        "carrier_contact__name",
    )
    date_hierarchy = "received_on"
    inlines = [ReceiptLineInline, ReceiptHorsFormatInline]
    actions = ("receive_lines",)

    def receive_lines(self, request, queryset):
        processed = 0
        errors = []
        for receipt in queryset:
            for line in receipt.lines.select_related("product"):
                if line.received_lot_id:
                    continue
                try:
                    receive_receipt_line(user=request.user, line=line)
                    processed += 1
                except StockError as exc:
                    errors.append(f"{receipt}: {exc}")
        if processed:
            self.message_user(request, f"{processed} ligne(s) receptionnee(s).")
        for error in errors:
            self.message_user(request, error, level=messages.ERROR)

    receive_lines.short_description = "Receptionner les lignes"


@admin.register(models.ReceiptLine)
class ReceiptLineAdmin(admin.ModelAdmin):
    list_display = ("receipt", "product", "quantity", "location", "received_lot")
    list_filter = ("receipt__status", "receipt__warehouse", "product")
    search_fields = ("receipt__reference", "product__name", "product__sku")
    autocomplete_fields = ("receipt", "product", "location")
    actions = ("receive_selected_lines",)

    def receive_selected_lines(self, request, queryset):
        processed = 0
        errors = []
        for line in queryset.select_related("receipt", "product"):
            if line.received_lot_id:
                continue
            try:
                receive_receipt_line(user=request.user, line=line)
                processed += 1
            except StockError as exc:
                errors.append(f"{line.receipt}: {exc}")
        if processed:
            self.message_user(request, f"{processed} ligne(s) receptionnee(s).")
        for error in errors:
            self.message_user(request, error, level=messages.ERROR)

    receive_selected_lines.short_description = "Receptionner les lignes selectionnees"
    list_select_related = ("receipt", "receipt__warehouse", "product", "location", "received_lot")


@admin.register(models.CartonFormat)
class CartonFormatAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "length_cm",
        "width_cm",
        "height_cm",
        "max_weight_g",
        "is_default",
    )
    list_filter = ("is_default",)
    search_fields = ("name",)


@admin.register(models.ProductLot)
class ProductLotAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "lot_code",
        "status",
        "quantity_on_hand",
        "quantity_reserved",
        "quantity_available",
        "expires_on",
        "location",
        "source_receipt",
    )
    list_filter = ("status", "location__warehouse", "location", "product")
    search_fields = ("product__sku", "product__name", "lot_code")
    ordering = ("product__name", "expires_on")
    list_select_related = ("product", "location", "location__warehouse")
    actions = ("release_quarantine",)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("quantity_on_hand", "quantity_reserved")
        return ()

    def quantity_available(self, obj):
        return max(0, obj.quantity_on_hand - obj.quantity_reserved)

    quantity_available.short_description = "Disponible"

    def release_quarantine(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(
                request,
                "Seuls les admins peuvent liberer la quarantaine.",
                level=messages.ERROR,
            )
            return
        quarantined = queryset.filter(status=models.ProductLotStatus.QUARANTINED)
        updated = quarantined.update(
            status=models.ProductLotStatus.AVAILABLE,
            released_by=request.user,
            released_at=timezone.now(),
        )
        self.message_user(request, f"{updated} lot(s) libere(s) de quarantaine.")

    release_quarantine.short_description = "Liberer la quarantaine"


class CartonItemInline(admin.TabularInline):
    model = models.CartonItem
    extra = 0
    max_num = 0
    can_delete = False
    autocomplete_fields = ("product_lot",)
    fields = ("product_lot", "quantity")
    readonly_fields = ("product_lot", "quantity")

    def has_add_permission(self, request, obj=None):
        return False


class OrderLineInline(admin.TabularInline):
    model = models.OrderLine
    extra = 0
    autocomplete_fields = ("product",)
    fields = ("product", "quantity", "reserved_quantity", "prepared_quantity")
    readonly_fields = ("reserved_quantity", "prepared_quantity")


@admin.register(models.Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "status",
        "shipper_name",
        "recipient_name",
        "shipment_reference",
        "created_at",
    )
    list_filter = ("status", "destination_country")
    search_fields = ("reference", "shipper_name", "recipient_name")
    readonly_fields = ("shipment",)
    inlines = [OrderLineInline]
    actions = ("create_shipment", "reserve_order", "prepare_order_action")

    def shipment_reference(self, obj):
        return obj.shipment.reference if obj.shipment else "-"

    shipment_reference.short_description = "Expedition"

    def create_shipment(self, request, queryset):
        created = 0
        for order in queryset:
            if order.shipment_id:
                continue
            create_shipment_for_order(order=order)
            created += 1
        if created:
            self.message_user(request, f"{created} expedition(s) creee(s).")

    create_shipment.short_description = "Creer expedition"

    def reserve_order(self, request, queryset):
        processed = 0
        errors = []
        for order in queryset:
            try:
                reserve_stock_for_order(order=order)
                processed += 1
            except StockError as exc:
                errors.append(f"{order}: {exc}")
        if processed:
            self.message_user(request, f"{processed} commande(s) reservee(s).")
        for error in errors:
            self.message_user(request, error, level=messages.ERROR)

    reserve_order.short_description = "Reserver le stock"

    def prepare_order_action(self, request, queryset):
        processed = 0
        errors = []
        for order in queryset:
            try:
                prepare_order(user=request.user, order=order)
                processed += 1
            except StockError as exc:
                errors.append(f"{order}: {exc}")
        if processed:
            self.message_user(request, f"{processed} commande(s) preparee(s).")
        for error in errors:
            self.message_user(request, error, level=messages.ERROR)

    prepare_order_action.short_description = "Preparer les commandes"


@admin.register(models.OrderReservation)
class OrderReservationAdmin(admin.ModelAdmin):
    list_display = ("order_line", "product_lot", "quantity", "created_at")
    list_filter = ("order_line__order__status", "product_lot__product")
    search_fields = ("order_line__order__reference", "product_lot__product__name")
    autocomplete_fields = ("order_line", "product_lot")


@admin.register(models.OrderLine)
class OrderLineAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "quantity", "reserved_quantity", "prepared_quantity")
    list_filter = ("order__status", "product")
    search_fields = ("order__reference", "product__name", "product__sku")


@admin.register(models.Carton)
class CartonAdmin(admin.ModelAdmin):
    list_display = ("code", "status", "shipment", "current_location", "created_at")
    list_filter = ("status", "current_location__warehouse")
    search_fields = ("code", "shipment__reference")
    list_select_related = ("shipment", "current_location")
    inlines = (CartonItemInline,)
    actions = ("unpack_cartons",)

    def save_model(self, request, obj, form, change):
        original = None
        if change:
            original = models.Carton.objects.filter(pk=obj.pk).first()
        super().save_model(request, obj, form, change)
        if original and original.shipment_id != obj.shipment_id:
            if obj.shipment:
                models.StockMovement.objects.filter(
                    related_carton=obj, movement_type=models.MovementType.OUT
                ).update(related_shipment=obj.shipment)
            else:
                models.StockMovement.objects.filter(
                    related_carton=obj, movement_type=models.MovementType.OUT
                ).update(related_shipment=None)
        if obj.shipment:
            if not models.StockMovement.objects.filter(
                related_carton=obj, movement_type=models.MovementType.OUT
            ).exists():
                items = list(
                    obj.cartonitem_set.select_related(
                        "product_lot", "product_lot__product"
                    )
                )
                if items:
                    for item in items:
                        models.StockMovement.objects.create(
                            movement_type=models.MovementType.OUT,
                            product=item.product_lot.product,
                            product_lot=item.product_lot,
                            quantity=item.quantity,
                            from_location=item.product_lot.location,
                            related_carton=obj,
                            related_shipment=obj.shipment,
                            created_by=request.user,
                        )

    def unpack_cartons(self, request, queryset):
        unpacked = 0
        skipped = 0
        with transaction.atomic():
            for carton in queryset.select_related("shipment"):
                try:
                    unpack_carton(user=request.user, carton=carton)
                    unpacked += 1
                except StockError:
                    skipped += 1
        if unpacked:
            self.message_user(request, f"{unpacked} carton(s) deconditionne(s).")
        if skipped:
            self.message_user(
                request,
                f"{skipped} carton(s) ignores (deja expedies ou vides).",
                level=messages.WARNING,
            )

    unpack_cartons.short_description = "Deconditionner les cartons"


class CartonInline(admin.TabularInline):
    model = models.Carton
    extra = 0
    max_num = 0
    can_delete = False
    fields = ("code", "status", "current_location")
    readonly_fields = ("code",)


class DocumentInline(admin.TabularInline):
    model = models.Document
    extra = 0


@admin.register(models.Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ("city", "iata_code", "country", "correspondent_contact", "is_active")
    list_filter = ("country", "is_active")
    search_fields = ("city", "iata_code", "country", "correspondent_contact__name")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "correspondent_contact":
            kwargs["queryset"] = contacts_with_tags(TAG_CORRESPONDENT)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(models.Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    change_form_template = "admin/wms/shipment/change_form.html"
    readonly_fields = ("reference",)
    list_display = ("reference", "status", "shipper_name", "recipient_name", "created_at")
    list_filter = ("status", "destination_country")
    search_fields = ("reference", "shipper_name", "recipient_name")
    inlines = (CartonInline, DocumentInline)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:shipment_id>/print/<str:doc_type>/",
                self.admin_site.admin_view(self.print_document),
                name="wms_shipment_print_doc",
            ),
            path(
                "<int:shipment_id>/print/carton/<int:carton_id>/",
                self.admin_site.admin_view(self.print_carton_packing_list),
                name="wms_shipment_print_carton",
            ),
        ]
        return custom_urls + urls

    def print_document(self, request, shipment_id, doc_type):
        shipment = self.get_object(request, shipment_id)
        if shipment is None:
            raise Http404("Shipment not found")

        allowed = {
            "donation_certificate": "print/attestation_donation.html",
            "humanitarian_certificate": "print/attestation_aide_humanitaire.html",
            "customs": "print/attestation_douane.html",
            "shipment_note": "print/bon_expedition.html",
            "packing_list_shipment": "print/liste_colisage_lot.html",
        }
        template = allowed.get(doc_type)
        if template is None:
            raise Http404("Document type not found")

        cartons = shipment.carton_set.all().order_by("code")
        item_rows = build_shipment_item_rows(shipment)
        aggregate_rows = build_shipment_aggregate_rows(shipment)
        carton_rows = build_carton_rows(cartons)

        description = f"{cartons.count()} cartons, {len(aggregate_rows)} produits"
        if shipment.requested_delivery_date:
            description += (
                f", livraison souhaitee "
                f"{shipment.requested_delivery_date.strftime('%d/%m/%Y')}"
            )
        rows_for_template = (
            aggregate_rows if doc_type == "packing_list_shipment" else item_rows
        )

        context = {
            **build_org_context(),
            "document_ref": f"DOC-{shipment.reference}-{doc_type}".upper(),
            "document_date": timezone.localdate(),
            "shipment_ref": shipment.reference,
            "shipper_name": shipment.shipper_name,
            "shipper_contact": shipment.shipper_contact,
            "recipient_name": shipment.recipient_name,
            "recipient_contact": shipment.recipient_contact,
            "correspondent_name": shipment.correspondent_name,
            "destination_address": shipment.destination_address,
            "destination_country": shipment.destination_country,
            "carton_count": cartons.count(),
            "carton_rows": carton_rows,
            "item_rows": rows_for_template,
            "donor_name": shipment.shipper_name,
            "donation_description": shipment.notes or description,
            "humanitarian_purpose": shipment.notes or "Aide humanitaire",
            "shipment_description": description,
        }
        return render(request, template, context)

    def print_carton_packing_list(self, request, shipment_id, carton_id):
        shipment = self.get_object(request, shipment_id)
        if shipment is None:
            raise Http404("Shipment not found")
        carton = shipment.carton_set.filter(pk=carton_id).first()
        if carton is None:
            raise Http404("Carton not found for shipment")

        item_rows = []
        for item in carton.cartonitem_set.select_related(
            "product_lot", "product_lot__product"
        ):
            item_rows.append(
                {
                    "product": item.product_lot.product.name,
                    "lot": item.product_lot.lot_code or "N/A",
                    "quantity": item.quantity,
                }
            )

        context = {
            "shipment_ref": shipment.reference,
            "carton_code": carton.code,
            "item_rows": item_rows,
        }
        return render(request, "print/liste_colisage_carton.html", context)


@admin.register(models.StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    change_list_template = "admin/wms/stockmovement/change_list.html"
    list_display = (
        "movement_type",
        "product",
        "product_lot",
        "quantity",
        "from_location",
        "to_location",
        "created_at",
    )
    list_filter = ("movement_type", "created_at", "from_location__warehouse")
    search_fields = ("product__sku", "product__name", "product_lot__lot_code")
    list_select_related = ("product", "product_lot", "from_location", "to_location")

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "receive/",
                self.admin_site.admin_view(self.receive_view),
                name="wms_stockmovement_receive",
            ),
            path(
                "adjust/",
                self.admin_site.admin_view(self.adjust_view),
                name="wms_stockmovement_adjust",
            ),
            path(
                "transfer/",
                self.admin_site.admin_view(self.transfer_view),
                name="wms_stockmovement_transfer",
            ),
            path(
                "pack/",
                self.admin_site.admin_view(self.pack_view),
                name="wms_stockmovement_pack",
            ),
        ]
        return custom_urls + urls

    def receive_view(self, request):
        if request.method == "POST":
            form = ReceiveStockForm(request.POST)
            if form.is_valid():
                product = form.cleaned_data["product"]
                status = form.cleaned_data["status"] or None
                location = form.cleaned_data["location"] or product.default_location
                if location is None:
                    form.add_error(
                        "location", "Emplacement requis ou definir un emplacement par defaut."
                    )
                    return self._render_form(request, form, "Reception stock")
                with transaction.atomic():
                    lot = receive_stock(
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
                self.message_user(
                    request, "Stock receptionne et lot cree avec succes."
                )
                return redirect("admin:wms_productlot_change", lot.id)
        else:
            form = ReceiveStockForm()
        return self._render_form(request, form, "Reception stock")

    def adjust_view(self, request):
        if request.method == "POST":
            form = AdjustStockForm(request.POST)
            if form.is_valid():
                lot = form.cleaned_data["product_lot"]
                delta = form.cleaned_data["quantity_delta"]
                try:
                    with transaction.atomic():
                        adjust_stock(
                            user=request.user,
                            lot=lot,
                            delta=delta,
                            reason_code=form.cleaned_data["reason_code"] or "",
                            reason_notes=form.cleaned_data["reason_notes"] or "",
                        )
                    self.message_user(request, "Ajustement de stock enregistre.")
                    return redirect("admin:wms_productlot_change", lot.id)
                except StockError:
                    form.add_error(
                        "quantity_delta",
                        "Stock insuffisant pour appliquer cette correction.",
                    )
        else:
            form = AdjustStockForm()
        return self._render_form(request, form, "Ajuster stock")

    def transfer_view(self, request):
        if request.method == "POST":
            form = TransferStockForm(request.POST)
            if form.is_valid():
                lot = form.cleaned_data["product_lot"]
                to_location = form.cleaned_data["to_location"]
                try:
                    with transaction.atomic():
                        transfer_stock(
                            user=request.user,
                            lot=lot,
                            to_location=to_location,
                        )
                    self.message_user(request, "Transfert de stock enregistre.")
                    return redirect("admin:wms_productlot_change", lot.id)
                except StockError:
                    form.add_error("to_location", "Le lot est deja a cet emplacement.")
        else:
            form = TransferStockForm()
        return self._render_form(request, form, "Transferer stock")

    def pack_view(self, request):
        if request.method == "POST":
            form = PackCartonForm(request.POST)
            if form.is_valid():
                with transaction.atomic():
                    product = form.cleaned_data["product"]
                    quantity = form.cleaned_data["quantity"]
                    carton = form.cleaned_data["carton"]
                    carton_code = form.cleaned_data["carton_code"]
                    shipment = form.cleaned_data["shipment"]
                    current_location = form.cleaned_data["current_location"]
                    try:
                        carton = pack_carton(
                            user=request.user,
                            product=product,
                            quantity=quantity,
                            carton=carton,
                            carton_code=carton_code,
                            shipment=shipment,
                            current_location=current_location,
                        )
                    except StockError as exc:
                        message = str(exc)
                        if "Carton deja lie" in message:
                            form.add_error("shipment", message)
                        elif "Stock insuffisant" in message:
                            form.add_error("quantity", message)
                        elif "carton expedie" in message.lower():
                            form.add_error("carton", message)
                        elif "expedition expediee" in message.lower():
                            form.add_error("shipment", message)
                        else:
                            form.add_error(None, message)
                        return self._render_form(request, form, "Preparer carton")

                self.message_user(request, "Carton prepare avec succes.")
                return redirect("admin:wms_carton_change", carton.id)
        else:
            form = PackCartonForm()
        return self._render_form(request, form, "Preparer carton")

    def _render_form(self, request, form, title):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "form": form,
            "title": title,
        }
        return render(request, "admin/wms/stockmovement/form.html", context)


@admin.register(models.Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("doc_type", "shipment", "generated_at")
    list_filter = ("doc_type",)
    search_fields = ("shipment__reference",)
