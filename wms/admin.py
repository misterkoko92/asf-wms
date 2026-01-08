import re

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import path, reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.html import format_html, format_html_join
from django.utils.http import urlsafe_base64_encode

from contacts.models import Contact, ContactAddress, ContactTag

from . import models
from .contact_filters import (
    TAG_CORRESPONDENT,
    TAG_RECIPIENT,
    TAG_SHIPPER,
    contacts_with_tags,
)
from .emailing import send_email_safe
from .forms import AdjustStockForm, PackCartonForm, ReceiveStockForm, TransferStockForm
from .print_context import (
    build_carton_document_context,
    build_product_label_context,
    build_shipment_document_context,
)
from .print_layouts import DEFAULT_LAYOUTS
from .print_renderer import get_template_layout, render_layout_from_layout
from .print_utils import build_label_pages
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

TEMP_PORTAL_PASSWORD = "TempPWD!"


@admin.register(models.ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")
    search_fields = ("name",)
    list_select_related = ("parent",)


@admin.register(models.ProductTag)
class ProductTagAdmin(admin.ModelAdmin):
    search_fields = ("name",)


class ProductKitItemInline(admin.TabularInline):
    model = models.ProductKitItem
    extra = 0
    autocomplete_fields = ("component",)
    fields = ("component", "quantity")
    fk_name = "kit"


@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "brand",
        "color",
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
    readonly_fields = ("sku", "photo_preview", "qr_code_preview")
    fields = (
        "sku",
        "name",
        "brand",
        "color",
        "photo",
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
        "photo_preview",
        "qr_code_preview",
        "qr_code_image",
        "notes",
    )
    inlines = (ProductKitItemInline,)
    actions = (
        "archive_products",
        "unarchive_products",
        "generate_qr_codes",
        "print_product_labels",
    )

    def qr_code_preview(self, obj):
        if obj.qr_code_image:
            return format_html(
                '<img src="{}" style="height: 120px; border: 1px solid #ccc;" />',
                obj.qr_code_image.url,
            )
        return "-"

    qr_code_preview.short_description = "QR code"

    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="height: 120px; border: 1px solid #ccc;" />',
                obj.photo.url,
            )
        return "-"

    photo_preview.short_description = "Photo"

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

    def print_product_labels(self, request, queryset):
        products = (
            queryset.select_related("default_location", "default_location__warehouse")
            .order_by("name")
            .all()
        )
        if not products:
            self.message_user(request, "Aucun produit selectionne.", level=messages.WARNING)
            return None
        warehouse_ids = set()
        for product in products:
            if product.default_location_id:
                warehouse_ids.add(product.default_location.warehouse_id)
        rack_color_map = {}
        if warehouse_ids:
            rack_colors = models.RackColor.objects.filter(warehouse_id__in=warehouse_ids)
            rack_color_map = {
                (color.warehouse_id, color.zone.lower()): color.color
                for color in rack_colors
            }
        layout_override = get_template_layout("product_label")
        layout = layout_override or DEFAULT_LAYOUTS.get("product_label", {"blocks": []})
        contexts = []
        for product in products:
            rack_color = None
            location = product.default_location
            if location:
                rack_color = rack_color_map.get(
                    (location.warehouse_id, location.zone.lower())
                )
            contexts.append(build_product_label_context(product, rack_color=rack_color))
        pages, page_style = build_label_pages(
            layout,
            contexts,
            block_type="product_label",
            labels_per_page=4,
        )
        return render(
            request,
            "print/product_labels.html",
            {"pages": pages, "page_style": page_style},
        )

    print_product_labels.short_description = "Imprimer etiquettes produit"


@admin.register(models.PublicOrderLink)
class PublicOrderLinkAdmin(admin.ModelAdmin):
    list_display = ("label", "token", "is_active", "expires_at", "created_at")
    list_filter = ("is_active",)
    search_fields = ("label", "token")


@admin.register(models.PublicAccountRequest)
class PublicAccountRequestAdmin(admin.ModelAdmin):
    list_display = (
        "association_name",
        "email",
        "status",
        "created_at",
        "reviewed_at",
    )
    list_filter = ("status",)
    search_fields = ("association_name", "email")
    actions = ("approve_requests", "reject_requests")

    def _approve_request(self, request, account_request):
        User = get_user_model()
        user = User.objects.filter(email__iexact=account_request.email).first()
        if user and (user.is_staff or user.is_superuser):
            return False, "email reserve"

        with transaction.atomic():
            contact = account_request.contact
            if not contact:
                contact = Contact.objects.create(
                    name=account_request.association_name,
                    email=account_request.email,
                    phone=account_request.phone,
                    is_active=True,
                )
                account_request.contact = contact
            tag, _ = ContactTag.objects.get_or_create(name=TAG_SHIPPER[0])
            contact.tags.add(tag)

            contact_updates = []
            if account_request.email and contact.email != account_request.email:
                contact.email = account_request.email
                contact_updates.append("email")
            if account_request.phone and contact.phone != account_request.phone:
                contact.phone = account_request.phone
                contact_updates.append("phone")
            if contact_updates:
                contact.save(update_fields=contact_updates)

            address = (
                contact.get_effective_address()
                if hasattr(contact, "get_effective_address")
                else contact.addresses.filter(is_default=True).first()
                or contact.addresses.first()
            )
            if not address:
                ContactAddress.objects.create(
                    contact=contact,
                    address_line1=account_request.address_line1,
                    address_line2=account_request.address_line2,
                    postal_code=account_request.postal_code,
                    city=account_request.city,
                    country=account_request.country or "France",
                    phone=account_request.phone,
                    email=account_request.email,
                    is_default=True,
                )

            if not user:
                user = User.objects.create_user(
                    username=account_request.email,
                    email=account_request.email,
                )
            user.set_password(TEMP_PORTAL_PASSWORD)
            user.save(update_fields=["password"])

            profile, created = models.AssociationProfile.objects.get_or_create(
                user=user, defaults={"contact": contact}
            )
            if not created and profile.contact_id != contact.id:
                profile.contact = contact
            profile.must_change_password = True
            profile.save(update_fields=["contact", "must_change_password"])

            models.AccountDocument.objects.filter(
                account_request=account_request,
                association_contact__isnull=True,
            ).update(association_contact=contact)

            account_request.status = models.PublicAccountRequestStatus.APPROVED
            account_request.reviewed_at = timezone.now()
            account_request.reviewed_by = request.user
            account_request.save(
                update_fields=["status", "reviewed_at", "reviewed_by", "contact"]
            )

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        set_password_url = request.build_absolute_uri(
            reverse("portal:portal_set_password", args=[uid, token])
        )
        login_url = request.build_absolute_uri(reverse("portal:portal_login"))
        message = render_to_string(
            "emails/account_request_approved.txt",
            {
                "association_name": contact.name,
                "email": account_request.email,
                "set_password_url": set_password_url,
                "login_url": login_url,
                "temp_password": TEMP_PORTAL_PASSWORD,
            },
        )
        send_email_safe(
            subject="ASF WMS - Compte valide",
            message=message,
            recipient=[account_request.email],
        )
        return True, ""

    def approve_requests(self, request, queryset):
        approved = 0
        skipped = 0
        for account_request in queryset.select_related("contact"):
            if account_request.status == models.PublicAccountRequestStatus.APPROVED:
                user_exists = (
                    get_user_model()
                    .objects.filter(email__iexact=account_request.email)
                    .exists()
                )
                if user_exists:
                    skipped += 1
                    continue
            ok, _ = self._approve_request(request, account_request)
            if ok:
                approved += 1
            else:
                skipped += 1

        if approved:
            self.message_user(request, f"{approved} demande(s) approuvee(s).")
        if skipped:
            self.message_user(
                request,
                f"{skipped} demande(s) ignoree(s) (deja approuvees ou email reserve).",
                level=messages.WARNING,
            )

    approve_requests.short_description = "Approuver les demandes"

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change and obj.pk:
            previous_status = (
                self.model.objects.filter(pk=obj.pk)
                .values_list("status", flat=True)
                .first()
            )
        super().save_model(request, obj, form, change)
        if obj.status != models.PublicAccountRequestStatus.APPROVED:
            return
        user_exists = (
            get_user_model().objects.filter(email__iexact=obj.email).exists()
        )
        if previous_status == models.PublicAccountRequestStatus.APPROVED and user_exists:
            return
        ok, reason = self._approve_request(request, obj)
        if ok:
            self.message_user(
                request,
                "Compte cree automatiquement apres validation.",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                f"Validation ignoree ({reason}).",
                level=messages.WARNING,
            )

    def account_access_info(self, obj):
        if not obj or obj.status != models.PublicAccountRequestStatus.APPROVED:
            return "Disponible apres validation."
        User = get_user_model()
        user = User.objects.filter(email__iexact=obj.email).first()
        if not user:
            return "Utilisateur introuvable."
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        base_url = settings.SITE_BASE_URL.rstrip("/") if settings.SITE_BASE_URL else ""
        login_url = f"{base_url}{reverse('portal:portal_login')}"
        set_password_url = f"{base_url}{reverse('portal:portal_set_password', args=[uid, token])}"
        lines = [
            f"Email: {obj.email or '-'}",
            f"Mot de passe temporaire: {TEMP_PORTAL_PASSWORD}",
            f"Login: {login_url}",
            f"Lien definir mot de passe: {set_password_url}",
        ]
        if not base_url:
            lines.append("SITE_BASE_URL non configuree, utiliser l'URL du site.")
        return format_html_join("<br>", "{}", ((line,) for line in lines))

    account_access_info.short_description = "Acces portail"

    readonly_fields = ("created_at", "reviewed_at", "account_access_info")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "association_name",
                    "email",
                    "phone",
                    "status",
                    "link",
                    "contact",
                    "notes",
                )
            },
        ),
        (
            "Adresse",
            {
                "fields": (
                    "address_line1",
                    "address_line2",
                    "postal_code",
                    "city",
                    "country",
                )
            },
        ),
        (
            "Validation",
            {"fields": ("created_at", "reviewed_at", "reviewed_by", "account_access_info")},
        ),
    )

    def reject_requests(self, request, queryset):
        updated = queryset.update(
            status=models.PublicAccountRequestStatus.REJECTED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f"{updated} demande(s) refusee(s).")

    reject_requests.short_description = "Refuser les demandes"


@admin.register(models.AssociationProfile)
class AssociationProfileAdmin(admin.ModelAdmin):
    list_display = ("contact", "user", "created_at")
    search_fields = ("contact__name", "user__username", "user__email")


@admin.register(models.AssociationRecipient)
class AssociationRecipientAdmin(admin.ModelAdmin):
    list_display = ("name", "association_contact", "city", "country", "is_active")
    list_filter = ("is_active", "country")
    search_fields = ("name", "association_contact__name", "city")


class _DocumentStatusMixin:
    actions = ("mark_approved", "mark_rejected")

    def mark_approved(self, request, queryset):
        updated = queryset.update(
            status=models.DocumentReviewStatus.APPROVED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f"{updated} document(s) approuve(s).")

    mark_approved.short_description = "Marquer comme approuve"

    def mark_rejected(self, request, queryset):
        updated = queryset.update(
            status=models.DocumentReviewStatus.REJECTED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f"{updated} document(s) refuse(s).")

    mark_rejected.short_description = "Marquer comme refuse"


@admin.register(models.AccountDocument)
class AccountDocumentAdmin(_DocumentStatusMixin, admin.ModelAdmin):
    list_display = ("doc_type", "association_contact", "status", "uploaded_at")
    list_filter = ("status", "doc_type")
    search_fields = ("association_contact__name",)


@admin.register(models.OrderDocument)
class OrderDocumentAdmin(_DocumentStatusMixin, admin.ModelAdmin):
    list_display = ("doc_type", "order", "status", "uploaded_at")
    list_filter = ("status", "doc_type")
    search_fields = ("order__reference",)


@admin.register(models.Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(models.Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "zone", "aisle", "shelf")
    list_filter = ("warehouse",)
    search_fields = ("warehouse__name", "zone", "aisle", "shelf")


class RackColorAdminForm(forms.ModelForm):
    zone = forms.ChoiceField(label="Rack", required=True)
    color_picker = forms.CharField(
        label="Palette",
        required=False,
        widget=forms.TextInput(attrs={"type": "color"}),
    )

    class Meta:
        model = models.RackColor
        fields = ("warehouse", "zone", "color", "color_picker")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["color"].help_text = "Format attendu: #RRGGBB (ex: #1C8BC0)."
        self.fields["color"].widget.attrs.setdefault("placeholder", "#1C8BC0")
        warehouse_id = None
        if self.data.get("warehouse"):
            try:
                warehouse_id = int(self.data.get("warehouse"))
            except (TypeError, ValueError):
                warehouse_id = None
        elif self.instance and self.instance.warehouse_id:
            warehouse_id = self.instance.warehouse_id

        zones_qs = models.Location.objects.all()
        if warehouse_id:
            zones_qs = zones_qs.filter(warehouse_id=warehouse_id)
        zones = list(
            zones_qs.order_by("zone").values_list("zone", flat=True).distinct()
        )
        current_zone = self.instance.zone if self.instance else None
        if current_zone and current_zone not in zones:
            zones.insert(0, current_zone)
        self.fields["zone"].choices = [("", "---")] + [(z, z) for z in zones]

        current_color = (self.initial.get("color") or "").strip()
        if not current_color and self.instance:
            current_color = (self.instance.color or "").strip()
        if re.fullmatch(r"#[0-9a-fA-F]{6}", current_color):
            self.fields["color_picker"].initial = current_color

    def clean_color(self):
        color = (self.cleaned_data.get("color") or "").strip()
        picker = (self.cleaned_data.get("color_picker") or "").strip()
        if color:
            return color
        if picker:
            return picker
        raise forms.ValidationError("Couleur requise.")

    def clean(self):
        cleaned_data = super().clean()
        warehouse = cleaned_data.get("warehouse")
        zone = cleaned_data.get("zone")
        if warehouse and zone:
            exists = models.Location.objects.filter(
                warehouse=warehouse, zone=zone
            ).exists()
            if not exists:
                self.add_error("zone", "Rack inexistant pour cet entrepot.")
        return cleaned_data


@admin.register(models.RackColor)
class RackColorAdmin(admin.ModelAdmin):
    form = RackColorAdminForm
    list_display = ("warehouse", "rack", "color")
    list_filter = ("warehouse",)
    search_fields = ("warehouse__name", "zone", "color")
    fields = ("warehouse", "zone", "color", "color_picker")

    def rack(self, obj):
        return obj.zone

    rack.short_description = "Rack"

    class Media:
        js = ("wms/rack_color_admin.js",)


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


class ShipmentTrackingEventInline(admin.TabularInline):
    model = models.ShipmentTrackingEvent
    extra = 0
    can_delete = False
    readonly_fields = (
        "status",
        "actor_name",
        "actor_structure",
        "comments",
        "created_by",
        "created_at",
    )
    fields = readonly_fields

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
    readonly_fields = ("reference", "qr_code_preview")
    fields = (
        "reference",
        "status",
        "shipper_name",
        "shipper_contact",
        "recipient_name",
        "recipient_contact",
        "correspondent_name",
        "destination",
        "destination_address",
        "destination_country",
        "requested_delivery_date",
        "created_at",
        "ready_at",
        "created_by",
        "qr_code_preview",
        "qr_code_image",
        "notes",
    )
    list_display = ("reference", "status", "shipper_name", "recipient_name", "created_at")
    list_filter = ("status", "destination_country")
    search_fields = ("reference", "shipper_name", "recipient_name")
    inlines = (CartonInline, DocumentInline, ShipmentTrackingEventInline)

    def qr_code_preview(self, obj):
        if obj.qr_code_image:
            return format_html(
                '<img src="{}" style="height: 120px; border: 1px solid #ccc;" />',
                obj.qr_code_image.url,
            )
        return "-"

    qr_code_preview.short_description = "QR code"

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
        context = build_shipment_document_context(shipment, doc_type)
        layout_override = get_template_layout(doc_type)
        if layout_override:
            blocks = render_layout_from_layout(layout_override, context)
            return render(request, "print/dynamic_document.html", {"blocks": blocks})
        return render(request, template, context)

    def print_carton_packing_list(self, request, shipment_id, carton_id):
        shipment = self.get_object(request, shipment_id)
        if shipment is None:
            raise Http404("Shipment not found")
        carton = shipment.carton_set.filter(pk=carton_id).first()
        if carton is None:
            raise Http404("Carton not found for shipment")
        context = build_carton_document_context(shipment, carton)
        layout_override = get_template_layout("packing_list_carton")
        if layout_override:
            blocks = render_layout_from_layout(layout_override, context)
            return render(request, "print/dynamic_document.html", {"blocks": blocks})
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


@admin.register(models.IntegrationEvent)
class IntegrationEventAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "direction",
        "source",
        "target",
        "event_type",
        "status",
    )
    list_filter = ("direction", "status", "source", "event_type")
    search_fields = ("source", "target", "event_type", "external_id")
    readonly_fields = ("created_at", "processed_at")
