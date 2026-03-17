import re
from io import BytesIO

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponseBase
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from contacts.models import Contact

from . import (
    admin_billing,  # noqa: F401
    admin_misc,  # noqa: F401
    models,
)
from .admin_account_request_approval import (
    approve_account_request,
    build_account_access_lines,
    build_portal_urls,
    describe_account_request_skip_reason,
)
from .admin_badges import render_admin_status_badge
from .admin_carton_handlers import (
    sync_carton_shipment_stock_movements,
    unpack_cartons_batch,
)
from .admin_organization_roles_review import get_organization_roles_review_urls
from .admin_stockmovement_views import (
    build_stockmovement_form_response,
    handle_adjust_view,
    handle_pack_view,
    handle_receive_view,
    handle_transfer_view,
)
from .emailing import enqueue_email_safe
from .forms import AdjustStockForm, PackCartonForm, ReceiveStockForm, TransferStockForm
from .helper_install import build_helper_install_context
from .local_document_helper import (
    LOCAL_DOCUMENT_HELPER_ORIGIN,
    build_local_helper_document_response,
    build_local_helper_job_response,
    get_local_helper_document_index,
    is_local_helper_job_request,
)
from .print_pack_engine import (
    PrintPackEngineError,
    generate_pack,
    render_pack_xlsx_documents,
)
from .print_pack_graph import GraphPdfConversionError
from .print_pack_routing import resolve_carton_packing_pack, resolve_pack_request
from .print_pack_xlsx import build_xlsx_fallback_response
from .product_label_printing import (
    render_product_labels_response,
    render_product_qr_labels_response,
)
from .services import (
    StockError,
    adjust_stock,
    create_shipment_for_order,
    pack_carton,
    prepare_order,
    receive_receipt_line,
    receive_stock,
    reserve_stock_for_order,
    transfer_stock,
    unpack_carton,
)
from .shipment_view_helpers import render_carton_document, render_shipment_document
from .volunteer_access import build_volunteer_urls, send_volunteer_access_email
from .volunteer_account_request_handlers import (
    approve_volunteer_account_request,
    describe_volunteer_account_request_skip_reason,
)


def _artifact_pdf_response(artifact):
    filename = (artifact.pdf_file.name or "").split("/")[-1] or "document.pdf"
    with artifact.pdf_file.open("rb") as pdf_stream:
        response = FileResponse(BytesIO(pdf_stream.read()), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


def _is_xlsx_fallback_enabled():
    return bool(getattr(settings, "PRINT_PACK_XLSX_FALLBACK_ENABLED", False))


def _generate_pack_xlsx_response(*, pack_code, shipment=None, carton=None, variant=None):
    documents = render_pack_xlsx_documents(
        pack_code=pack_code,
        shipment=shipment,
        carton=carton,
        variant=variant,
    )
    return build_xlsx_fallback_response(documents=documents, pack_code=pack_code)


def _try_generate_pack_artifact(*, fallback_renderer, **kwargs):
    try:
        return generate_pack(**kwargs)
    except GraphPdfConversionError:
        if _is_xlsx_fallback_enabled():
            return _generate_pack_xlsx_response(
                pack_code=kwargs.get("pack_code"),
                shipment=kwargs.get("shipment"),
                carton=kwargs.get("carton"),
                variant=kwargs.get("variant"),
            )
        return fallback_renderer()
    except PrintPackEngineError:
        return fallback_renderer()


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
    search_fields = ("sku", "name", "barcode", "ean", "brand")
    filter_horizontal = ("tags",)
    list_select_related = ("category", "default_location")
    readonly_fields = ("sku", "photo_preview", "qr_code_preview", "pu_ttc")
    fields = (
        "sku",
        "name",
        "brand",
        "color",
        "photo",
        "category",
        "tags",
        "barcode",
        "ean",
        "pu_ht",
        "tva",
        "pu_ttc",
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
        "print_product_qr_labels",
    )

    def qr_code_preview(self, obj):
        if obj.qr_code_image:
            return format_html(
                '<img src="{}" style="height: 120px; border: 1px solid #ccc;" />',
                obj.qr_code_image.url,
            )
        return "-"

    qr_code_preview.short_description = gettext_lazy("QR code")

    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="height: 120px; border: 1px solid #ccc;" />',
                obj.photo.url,
            )
        return "-"

    photo_preview.short_description = gettext_lazy("Photo")

    def archive_products(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, _("%(count)s produit(s) archives.") % {"count": updated})

    archive_products.short_description = gettext_lazy("Archiver les produits")

    def unarchive_products(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, _("%(count)s produit(s) réactivés.") % {"count": updated})

    unarchive_products.short_description = gettext_lazy("Réactiver les produits")

    def generate_qr_codes(self, request, queryset):
        count = 0
        for product in queryset:
            if not product.qr_code_image:
                product.generate_qr_code()
                product.save(update_fields=["qr_code_image"])
                count += 1
        self.message_user(request, _("%(count)s QR code(s) générés.") % {"count": count})

    generate_qr_codes.short_description = gettext_lazy("Générer les QR codes")

    def print_product_labels(self, request, queryset):
        if not queryset.exists():
            self.message_user(request, _("Aucun produit sélectionné."), level=messages.WARNING)
            return None
        return render_product_labels_response(request, queryset)

    print_product_labels.short_description = gettext_lazy("Imprimer étiquettes produit")

    def print_product_qr_labels(self, request, queryset):
        if not queryset.exists():
            self.message_user(request, _("Aucun produit sélectionné."), level=messages.WARNING)
            return None
        return render_product_qr_labels_response(request, queryset)

    print_product_qr_labels.short_description = gettext_lazy("Imprimer QR produits")


@admin.register(models.PublicOrderLink)
class PublicOrderLinkAdmin(admin.ModelAdmin):
    list_display = ("label", "token", "is_active", "expires_at", "created_at")
    list_filter = ("is_active",)
    search_fields = ("label", "token")


@admin.register(models.PublicAccountRequest)
class PublicAccountRequestAdmin(admin.ModelAdmin):
    list_display = (
        "account_type",
        "association_name",
        "requested_username",
        "email",
        "status_badge",
        "created_at",
        "reviewed_at",
    )
    list_filter = ("account_type", "status")
    search_fields = ("association_name", "requested_username", "email")
    actions = ("approve_requests", "reject_requests")

    @staticmethod
    def _build_portal_urls(*, request, user):
        return build_portal_urls(request=request, user=user)

    def _approve_request(self, request, account_request):
        return approve_account_request(
            request=request,
            account_request=account_request,
            enqueue_email=enqueue_email_safe,
            portal_url_builder=self._build_portal_urls,
        )

    def approve_requests(self, request, queryset):
        approved = 0
        skipped = 0
        for account_request in queryset.select_related("contact"):
            if account_request.status == models.PublicAccountRequestStatus.APPROVED:
                user_exists = (
                    get_user_model().objects.filter(email__iexact=account_request.email).exists()
                )
                if user_exists:
                    skipped += 1
                    continue
            ok, _reason = self._approve_request(request, account_request)
            if ok:
                approved += 1
            else:
                skipped += 1

        if approved:
            self.message_user(
                request,
                _("%(count)s demande(s) approuvée(s).") % {"count": approved},
            )
        if skipped:
            self.message_user(
                request,
                _("%(count)s demande(s) ignorée(s) (déjà approuvées ou identifiant réservé).")
                % {"count": skipped},
                level=messages.WARNING,
            )

    approve_requests.short_description = gettext_lazy("Approuver les demandes")

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change and obj.pk:
            previous_status = (
                self.model.objects.filter(pk=obj.pk).values_list("status", flat=True).first()
            )
        super().save_model(request, obj, form, change)
        if obj.status != models.PublicAccountRequestStatus.APPROVED:
            return
        user_exists = get_user_model().objects.filter(email__iexact=obj.email).exists()
        if previous_status == models.PublicAccountRequestStatus.APPROVED and user_exists:
            return
        ok, reason = self._approve_request(request, obj)
        if ok:
            self.message_user(
                request,
                _("Compte créé automatiquement après validation."),
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                _("Validation ignorée (%(reason)s).")
                % {"reason": describe_account_request_skip_reason(reason)},
                level=messages.WARNING,
            )

    def account_access_info(self, obj):
        lines, message = build_account_access_lines(
            account_request=obj,
            site_base_url=getattr(settings, "SITE_BASE_URL", ""),
        )
        if message:
            return message
        return format_html_join("<br>", "{}", ((line,) for line in lines))

    account_access_info.short_description = gettext_lazy("Accès portail")

    def status_badge(self, obj):
        return render_admin_status_badge(
            status_value=obj.status,
            label=obj.get_status_display(),
            domain="account_request",
        )

    status_badge.short_description = "status"
    status_badge.admin_order_field = "status"

    readonly_fields = ("created_at", "reviewed_at", "account_access_info")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "account_type",
                    "association_name",
                    "requested_username",
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
            gettext_lazy("Adresse"),
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
            gettext_lazy("Validation"),
            {"fields": ("created_at", "reviewed_at", "reviewed_by", "account_access_info")},
        ),
    )

    def reject_requests(self, request, queryset):
        updated = queryset.update(
            status=models.PublicAccountRequestStatus.REJECTED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(
            request,
            _("%(count)s demande(s) refusée(s).") % {"count": updated},
        )

    reject_requests.short_description = gettext_lazy("Refuser les demandes")


class _DocumentStatusMixin:
    actions = ("mark_approved", "mark_rejected")

    def mark_approved(self, request, queryset):
        updated = queryset.update(
            status=models.DocumentReviewStatus.APPROVED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(
            request,
            _("%(count)s document(s) approuvé(s).") % {"count": updated},
        )

    mark_approved.short_description = gettext_lazy("Marquer comme approuvé")

    def mark_rejected(self, request, queryset):
        updated = queryset.update(
            status=models.DocumentReviewStatus.REJECTED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(
            request,
            _("%(count)s document(s) refusé(s).") % {"count": updated},
        )

    mark_rejected.short_description = gettext_lazy("Marquer comme refusé")


@admin.register(models.AccountDocument)
class AccountDocumentAdmin(_DocumentStatusMixin, admin.ModelAdmin):
    list_display = ("doc_type", "association_contact", "status_badge", "uploaded_at")
    list_filter = ("status", "doc_type")
    search_fields = ("association_contact__name",)

    def status_badge(self, obj):
        return render_admin_status_badge(
            status_value=obj.status,
            label=obj.get_status_display(),
            domain="document_review",
        )

    status_badge.short_description = "status"
    status_badge.admin_order_field = "status"


class RackColorAdminForm(forms.ModelForm):
    zone = forms.ChoiceField(label=gettext_lazy("Rack"), required=True)
    color_picker = forms.CharField(
        label=gettext_lazy("Palette"),
        required=False,
        widget=forms.TextInput(attrs={"type": "color"}),
    )

    class Meta:
        model = models.RackColor
        fields = ("warehouse", "zone", "color", "color_picker")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["color"].help_text = _("Format attendu: #RRGGBB (ex: #1C8BC0).")
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
        zones = list(zones_qs.order_by("zone").values_list("zone", flat=True).distinct())
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
        raise forms.ValidationError(_("Couleur requise."))

    def clean(self):
        cleaned_data = super().clean()
        warehouse = cleaned_data.get("warehouse")
        zone = cleaned_data.get("zone")
        if warehouse and zone:
            exists = models.Location.objects.filter(warehouse=warehouse, zone=zone).exists()
            if not exists:
                self.add_error("zone", _("Rack inexistant pour cet entrepôt."))
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

    rack.short_description = gettext_lazy("Rack")

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
        "status_badge",
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

    def status_badge(self, obj):
        return render_admin_status_badge(
            status_value=obj.status,
            label=obj.get_status_display(),
            domain="receipt",
        )

    status_badge.short_description = "status"
    status_badge.admin_order_field = "status"

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
            self.message_user(
                request,
                _("%(count)s ligne(s) réceptionnée(s).") % {"count": processed},
            )
        for error in errors:
            self.message_user(request, error, level=messages.ERROR)

    receive_lines.short_description = gettext_lazy("Réceptionner les lignes")


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
            self.message_user(
                request,
                _("%(count)s ligne(s) réceptionnée(s).") % {"count": processed},
            )
        for error in errors:
            self.message_user(request, error, level=messages.ERROR)

    receive_selected_lines.short_description = gettext_lazy("Réceptionner les lignes sélectionnées")
    list_select_related = ("receipt", "receipt__warehouse", "product", "location", "received_lot")


@admin.register(models.ProductLot)
class ProductLotAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "lot_code",
        "status_badge",
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

    quantity_available.short_description = gettext_lazy("Disponible")

    def status_badge(self, obj):
        return render_admin_status_badge(
            status_value=obj.status,
            label=obj.get_status_display(),
            domain="product_lot",
        )

    status_badge.short_description = "status"
    status_badge.admin_order_field = "status"

    def release_quarantine(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(
                request,
                _("Seuls les admins peuvent libérer la quarantaine."),
                level=messages.ERROR,
            )
            return
        quarantined = queryset.filter(status=models.ProductLotStatus.QUARANTINED)
        updated = quarantined.update(
            status=models.ProductLotStatus.AVAILABLE,
            released_by=request.user,
            released_at=timezone.now(),
        )
        self.message_user(
            request,
            _("%(count)s lot(s) libéré(s) de quarantaine.") % {"count": updated},
        )

    release_quarantine.short_description = gettext_lazy("Libérer la quarantaine")


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
        "status_badge",
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

    shipment_reference.short_description = gettext_lazy("Expédition")

    def status_badge(self, obj):
        return render_admin_status_badge(
            status_value=obj.status,
            label=obj.get_status_display(),
            domain="order",
        )

    status_badge.short_description = "status"
    status_badge.admin_order_field = "status"

    def create_shipment(self, request, queryset):
        created = 0
        for order in queryset:
            if order.shipment_id:
                continue
            create_shipment_for_order(order=order)
            created += 1
        if created:
            self.message_user(
                request,
                _("%(count)s expédition(s) créée(s).") % {"count": created},
            )

    create_shipment.short_description = gettext_lazy("Créer une expédition")

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
            self.message_user(
                request,
                _("%(count)s commande(s) réservée(s).") % {"count": processed},
            )
        for error in errors:
            self.message_user(request, error, level=messages.ERROR)

    reserve_order.short_description = gettext_lazy("Réserver le stock")

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
            self.message_user(
                request,
                _("%(count)s commande(s) préparée(s).") % {"count": processed},
            )
        for error in errors:
            self.message_user(request, error, level=messages.ERROR)

    prepare_order_action.short_description = gettext_lazy("Préparer les commandes")


@admin.register(models.Carton)
class CartonAdmin(admin.ModelAdmin):
    list_display = ("code", "status_badge", "shipment", "current_location", "created_at")
    list_filter = ("status", "current_location__warehouse")
    search_fields = ("code", "shipment__reference")
    list_select_related = ("shipment", "current_location")
    inlines = (CartonItemInline,)
    actions = ("unpack_cartons",)

    def status_badge(self, obj):
        return render_admin_status_badge(
            status_value=obj.status,
            label=obj.get_status_display(),
            domain="carton",
        )

    status_badge.short_description = "status"
    status_badge.admin_order_field = "status"

    def save_model(self, request, obj, form, change):
        original = None
        if change:
            original = models.Carton.objects.filter(pk=obj.pk).first()
        super().save_model(request, obj, form, change)
        sync_carton_shipment_stock_movements(
            obj=obj,
            original=original,
            stock_movement_model=models.StockMovement,
            movement_type_out=models.MovementType.OUT,
            created_by=request.user,
        )

    def unpack_cartons(self, request, queryset):
        unpacked, skipped = unpack_cartons_batch(
            queryset=queryset,
            user=request.user,
            unpack_carton_fn=unpack_carton,
            stock_error_cls=StockError,
            transaction_module=transaction,
        )
        if unpacked:
            self.message_user(
                request,
                _("%(count)s carton(s) déconditionné(s).") % {"count": unpacked},
            )
        if skipped:
            self.message_user(
                request,
                _("%(count)s carton(s) ignorés (déjà expédiés ou vides).") % {"count": skipped},
                level=messages.WARNING,
            )

    unpack_cartons.short_description = gettext_lazy("Déconditionner les cartons")


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
            kwargs["queryset"] = Contact.objects.filter(is_active=True).order_by("name", "id")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(models.Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    change_form_template = "admin/wms/shipment/change_form.html"
    readonly_fields = ("reference", "created_at", "qr_code_preview")
    fields = (
        "reference",
        "status",
        "is_disputed",
        "disputed_at",
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
    list_display = (
        "reference",
        "status_badge",
        "is_disputed",
        "shipper_name",
        "recipient_name",
        "created_at",
    )
    list_filter = ("status", "is_disputed", "destination_country")
    search_fields = ("reference", "shipper_name", "recipient_name")
    inlines = (CartonInline, DocumentInline, ShipmentTrackingEventInline)

    def qr_code_preview(self, obj):
        if obj.qr_code_image:
            return format_html(
                '<img src="{}" style="height: 120px; border: 1px solid #ccc;" />',
                obj.qr_code_image.url,
            )
        return "-"

    qr_code_preview.short_description = gettext_lazy("QR code")

    def status_badge(self, obj):
        label = obj.get_status_display()
        if obj.is_disputed:
            label = f"Litige - {label}"
        return render_admin_status_badge(
            status_value=obj.status,
            label=label,
            domain="shipment",
            is_disputed=obj.is_disputed,
        )

    status_badge.short_description = "status"
    status_badge.admin_order_field = "status"

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

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        response_context = {
            **context,
            "helper_install": build_helper_install_context(
                install_url=reverse("scan:scan_local_document_helper_installer"),
                app_label="asf-wms",
                request=request,
            ),
            "local_document_helper_origin": LOCAL_DOCUMENT_HELPER_ORIGIN,
        }
        return super().render_change_form(
            request,
            response_context,
            add=add,
            change=change,
            form_url=form_url,
            obj=obj,
        )

    def print_document(self, request, shipment_id, doc_type):
        shipment = self.get_object(request, shipment_id)
        if shipment is None:
            raise Http404("Shipment not found")
        pack_route = resolve_pack_request(doc_type)
        if pack_route:
            render_documents = lambda: render_pack_xlsx_documents(
                pack_code=pack_route.pack_code,
                shipment=shipment,
                carton=None,
                variant=pack_route.variant,
            )
            if get_local_helper_document_index(request) is not None:
                return build_local_helper_document_response(
                    request,
                    render_documents=render_documents,
                )
            if is_local_helper_job_request(request):
                return build_local_helper_job_response(
                    request,
                    pack_code=pack_route.pack_code,
                    render_documents=render_documents,
                    shipment=shipment,
                )
            artifact = _try_generate_pack_artifact(
                pack_code=pack_route.pack_code,
                shipment=shipment,
                user=getattr(request, "user", None),
                variant=pack_route.variant,
                fallback_renderer=lambda: render_shipment_document(
                    request,
                    shipment,
                    doc_type,
                ),
            )
            if isinstance(artifact, HttpResponseBase) or not hasattr(artifact, "pdf_file"):
                return artifact
            return _artifact_pdf_response(artifact)
        return render_shipment_document(request, shipment, doc_type)

    def print_carton_packing_list(self, request, shipment_id, carton_id):
        shipment = self.get_object(request, shipment_id)
        if shipment is None:
            raise Http404("Shipment not found")
        carton = shipment.carton_set.filter(pk=carton_id).first()
        if carton is None:
            raise Http404("Carton not found for shipment")
        pack_route = resolve_carton_packing_pack()
        render_documents = lambda: render_pack_xlsx_documents(
            pack_code=pack_route.pack_code,
            shipment=shipment,
            carton=carton,
            variant=pack_route.variant,
        )
        if get_local_helper_document_index(request) is not None:
            return build_local_helper_document_response(
                request,
                render_documents=render_documents,
            )
        if is_local_helper_job_request(request):
            return build_local_helper_job_response(
                request,
                pack_code=pack_route.pack_code,
                render_documents=render_documents,
                shipment=shipment,
                carton=carton,
            )
        artifact = _try_generate_pack_artifact(
            pack_code=pack_route.pack_code,
            shipment=shipment,
            carton=carton,
            user=getattr(request, "user", None),
            variant=pack_route.variant,
            fallback_renderer=lambda: render_carton_document(
                request,
                shipment,
                carton,
            ),
        )
        if isinstance(artifact, HttpResponseBase) or not hasattr(artifact, "pdf_file"):
            return artifact
        return _artifact_pdf_response(artifact)


class PrintCellMappingInline(admin.TabularInline):
    model = models.PrintCellMapping
    extra = 0


@admin.register(models.PrintPack)
class PrintPackAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "active",
        "default_page_format",
        "fallback_page_format",
        "updated_at",
    )
    list_filter = ("active", "default_page_format", "fallback_page_format")
    search_fields = ("code", "name")
    ordering = ("code",)


@admin.register(models.PrintPackDocument)
class PrintPackDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "pack",
        "doc_type",
        "variant",
        "sequence",
        "enabled",
    )
    list_filter = ("pack", "enabled")
    search_fields = ("doc_type", "variant", "pack__code", "pack__name")
    ordering = ("pack__code", "sequence", "id")
    inlines = (PrintCellMappingInline,)


@admin.register(models.PrintCellMapping)
class PrintCellMappingAdmin(admin.ModelAdmin):
    list_display = (
        "pack_document",
        "worksheet_name",
        "cell_ref",
        "source_key",
        "transform",
        "required",
        "sequence",
    )
    list_filter = ("required", "pack_document__pack")
    search_fields = ("worksheet_name", "cell_ref", "source_key")
    ordering = ("pack_document__id", "sequence", "id")


@admin.register(models.GeneratedPrintArtifact)
class GeneratedPrintArtifactAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "pack_code",
        "status_badge",
        "shipment",
        "carton",
        "sync_attempts",
        "created_at",
    )
    list_filter = ("status", "pack_code")
    search_fields = ("pack_code", "shipment__reference", "onedrive_path")
    ordering = ("-created_at",)
    readonly_fields = (
        "shipment",
        "carton",
        "pack_code",
        "status",
        "pdf_file",
        "checksum",
        "created_by",
        "created_at",
        "onedrive_path",
        "sync_attempts",
        "last_sync_error",
    )

    def status_badge(self, obj):
        return render_admin_status_badge(
            status_value=obj.status,
            label=obj.get_status_display(),
            domain="artifact",
        )

    status_badge.short_description = "status"
    status_badge.admin_order_field = "status"

    def has_add_permission(self, request):
        return False


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
        return handle_receive_view(
            request=request,
            form_class=ReceiveStockForm,
            render_form=self._render_form,
            receive_stock_fn=receive_stock,
            redirect_fn=redirect,
            transaction_module=transaction,
            message_user=self.message_user,
        )

    def adjust_view(self, request):
        return handle_adjust_view(
            request=request,
            form_class=AdjustStockForm,
            render_form=self._render_form,
            adjust_stock_fn=adjust_stock,
            stock_error_cls=StockError,
            redirect_fn=redirect,
            transaction_module=transaction,
            message_user=self.message_user,
        )

    def transfer_view(self, request):
        return handle_transfer_view(
            request=request,
            form_class=TransferStockForm,
            render_form=self._render_form,
            transfer_stock_fn=transfer_stock,
            stock_error_cls=StockError,
            redirect_fn=redirect,
            transaction_module=transaction,
            message_user=self.message_user,
        )

    def pack_view(self, request):
        return handle_pack_view(
            request=request,
            form_class=PackCartonForm,
            render_form=self._render_form,
            pack_carton_fn=pack_carton,
            stock_error_cls=StockError,
            redirect_fn=redirect,
            transaction_module=transaction,
            message_user=self.message_user,
        )

    def _render_form(self, request, form, title):
        return build_stockmovement_form_response(
            request=request,
            admin_site=self.admin_site,
            model_meta=self.model._meta,
            form=form,
            title=title,
            render_fn=render,
        )


@admin.register(models.VolunteerProfile)
class VolunteerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "volunteer_id",
        "user",
        "phone",
        "city",
        "is_active",
        "must_change_password",
    )
    list_filter = ("is_active", "must_change_password", "country")
    search_fields = ("user__username", "user__email", "phone", "city", "volunteer_id")
    list_select_related = ("user", "contact")
    actions = ("mark_password_change_required", "send_access_email")

    def mark_password_change_required(self, request, queryset):
        updated = queryset.update(must_change_password=True)
        self.message_user(
            request,
            _("%(count)s acces benevole(s) marque(s) pour changement de mot de passe.")
            % {"count": updated},
        )

    mark_password_change_required.short_description = gettext_lazy(
        "Forcer le changement de mot de passe"
    )

    def send_access_email(self, request, queryset):
        sent = 0
        for profile in queryset.select_related("user"):
            profile.must_change_password = True
            profile.save(update_fields=["must_change_password"])
            if send_volunteer_access_email(request=request, user=profile.user):
                sent += 1
        self.message_user(
            request,
            _("%(count)s email(s) d'acces benevole envoyes.") % {"count": sent},
        )

    send_access_email.short_description = gettext_lazy("Envoyer ou reinitialiser l'acces benevole")


@admin.register(models.VolunteerAccountRequest)
class VolunteerAccountRequestAdmin(admin.ModelAdmin):
    list_display = (
        "first_name",
        "last_name",
        "email",
        "status_badge",
        "created_at",
        "reviewed_at",
    )
    list_filter = ("status", "country")
    search_fields = ("first_name", "last_name", "email", "phone", "city")
    readonly_fields = ("created_at", "reviewed_at", "reviewed_by")
    actions = ("approve_requests", "reject_requests")

    @staticmethod
    def _build_volunteer_urls(*, request, user):
        return build_volunteer_urls(request=request, user=user)

    def _approve_request(self, request, account_request):
        return approve_volunteer_account_request(
            request=request,
            account_request=account_request,
            enqueue_email=enqueue_email_safe,
            url_builder=self._build_volunteer_urls,
        )

    def approve_requests(self, request, queryset):
        approved = 0
        skipped = 0
        for account_request in queryset:
            if account_request.status == models.VolunteerAccountRequestStatus.APPROVED:
                user_exists = (
                    get_user_model().objects.filter(email__iexact=account_request.email).exists()
                )
                if user_exists:
                    skipped += 1
                    continue
            ok, _reason = self._approve_request(request, account_request)
            if ok:
                approved += 1
            else:
                skipped += 1
        if approved:
            self.message_user(
                request,
                _("%(count)s demande(s) benevole approuvee(s).") % {"count": approved},
            )
        if skipped:
            self.message_user(
                request,
                _("%(count)s demande(s) benevole ignoree(s).") % {"count": skipped},
                level=messages.WARNING,
            )

    approve_requests.short_description = gettext_lazy("Approuver les demandes benevole")

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change and obj.pk:
            previous_status = (
                self.model.objects.filter(pk=obj.pk).values_list("status", flat=True).first()
            )
        super().save_model(request, obj, form, change)
        if obj.status != models.VolunteerAccountRequestStatus.APPROVED:
            return
        user_exists = get_user_model().objects.filter(email__iexact=obj.email).exists()
        if previous_status == models.VolunteerAccountRequestStatus.APPROVED and user_exists:
            return
        ok, reason = self._approve_request(request, obj)
        if ok:
            self.message_user(
                request,
                _("Compte benevole cree automatiquement apres validation."),
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                _("Validation benevole ignoree (%(reason)s).")
                % {"reason": describe_volunteer_account_request_skip_reason(reason)},
                level=messages.WARNING,
            )

    def reject_requests(self, request, queryset):
        updated = queryset.update(
            status=models.VolunteerAccountRequestStatus.REJECTED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(
            request,
            _("%(count)s demande(s) benevole refusee(s).") % {"count": updated},
        )

    reject_requests.short_description = gettext_lazy("Refuser les demandes benevole")

    def status_badge(self, obj):
        return render_admin_status_badge(
            status_value=obj.status,
            label=obj.get_status_display(),
            domain="account_request",
        )

    status_badge.short_description = "status"
    status_badge.admin_order_field = "status"


@admin.register(models.VolunteerConstraint)
class VolunteerConstraintAdmin(admin.ModelAdmin):
    list_display = (
        "volunteer",
        "max_days_per_week",
        "max_expeditions_per_week",
        "max_expeditions_per_day",
        "max_colis_vol",
        "max_wait_hours",
        "updated_at",
    )
    list_select_related = ("volunteer", "volunteer__user")
    search_fields = ("volunteer__user__username", "volunteer__user__email", "volunteer__phone")


@admin.register(models.VolunteerAvailability)
class VolunteerAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("volunteer", "date", "start_time", "end_time", "updated_at")
    list_filter = ("date",)
    list_select_related = ("volunteer", "volunteer__user")
    search_fields = ("volunteer__user__username", "volunteer__user__email")


@admin.register(models.VolunteerUnavailability)
class VolunteerUnavailabilityAdmin(admin.ModelAdmin):
    list_display = ("volunteer", "date", "updated_at")
    list_filter = ("date",)
    list_select_related = ("volunteer", "volunteer__user")
    search_fields = ("volunteer__user__username", "volunteer__user__email")


@admin.register(models.PlanningParameterSet)
class PlanningParameterSetAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "is_current", "effective_from", "updated_at")
    list_filter = ("status", "is_current")
    search_fields = ("name", "notes")
    list_select_related = ("created_by",)


@admin.register(models.PlanningDestinationRule)
class PlanningDestinationRuleAdmin(admin.ModelAdmin):
    list_display = (
        "parameter_set",
        "destination",
        "label",
        "weekly_frequency",
        "max_cartons_per_flight",
        "priority",
        "is_active",
    )
    list_filter = ("is_active", "parameter_set")
    list_select_related = ("parameter_set", "destination")
    search_fields = ("label", "destination__city", "destination__iata_code")


@admin.register(models.FlightSourceBatch)
class FlightSourceBatchAdmin(admin.ModelAdmin):
    list_display = ("source", "status", "period_start", "period_end", "imported_at")
    list_filter = ("source", "status")
    search_fields = ("file_name", "checksum", "notes")


@admin.register(models.Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = (
        "flight_number",
        "departure_date",
        "origin_iata",
        "destination_iata",
        "capacity_units",
        "batch",
    )
    list_filter = ("departure_date", "batch__source")
    list_select_related = ("batch", "destination")
    search_fields = ("flight_number", "origin_iata", "destination_iata")


@admin.register(models.PlanningRun)
class PlanningRunAdmin(admin.ModelAdmin):
    list_display = ("week_start", "week_end", "status", "flight_mode", "created_by", "updated_at")
    list_filter = ("status", "flight_mode")
    list_select_related = ("created_by", "flight_batch", "parameter_set")
    search_fields = ("log_excerpt",)


@admin.register(models.PlanningIssue)
class PlanningIssueAdmin(admin.ModelAdmin):
    list_display = ("run", "severity", "code", "source_model", "source_pk", "created_at")
    list_filter = ("severity", "code")
    list_select_related = ("run",)
    search_fields = ("message", "code", "source_model")


@admin.register(models.PlanningShipmentSnapshot)
class PlanningShipmentSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "run",
        "shipment_reference",
        "shipper_name",
        "destination_iata",
        "priority",
        "equivalent_units",
    )
    list_filter = ("run",)
    list_select_related = ("run", "shipment")
    search_fields = ("shipment_reference", "shipper_name", "destination_iata")


@admin.register(models.PlanningVolunteerSnapshot)
class PlanningVolunteerSnapshotAdmin(admin.ModelAdmin):
    list_display = ("run", "volunteer_label", "max_colis_vol", "created_at")
    list_filter = ("run",)
    list_select_related = ("run", "volunteer")
    search_fields = ("volunteer_label",)


@admin.register(models.PlanningFlightSnapshot)
class PlanningFlightSnapshotAdmin(admin.ModelAdmin):
    list_display = ("run", "flight_number", "departure_date", "destination_iata", "capacity_units")
    list_filter = ("run", "departure_date")
    list_select_related = ("run", "flight")
    search_fields = ("flight_number", "destination_iata")


@admin.register(models.PlanningVersion)
class PlanningVersionAdmin(admin.ModelAdmin):
    list_display = ("run", "number", "status", "based_on", "created_by", "published_at")
    list_filter = ("status",)
    list_select_related = ("run", "based_on", "created_by")
    search_fields = ("change_reason",)


@admin.register(models.PlanningAssignment)
class PlanningAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "version",
        "shipment_snapshot",
        "volunteer_snapshot",
        "flight_snapshot",
        "source",
        "sequence",
    )
    list_filter = ("source", "status")
    list_select_related = (
        "version",
        "shipment_snapshot",
        "volunteer_snapshot",
        "flight_snapshot",
    )


@admin.register(models.PlanningArtifact)
class PlanningArtifactAdmin(admin.ModelAdmin):
    list_display = ("version", "artifact_type", "label", "generated_at")
    list_filter = ("artifact_type",)
    list_select_related = ("version",)
    search_fields = ("label", "file_path")


@admin.register(models.CommunicationTemplate)
class CommunicationTemplateAdmin(admin.ModelAdmin):
    list_display = ("label", "channel", "scope", "is_active", "updated_at")
    list_filter = ("channel", "is_active")
    search_fields = ("label", "scope", "subject", "body")


@admin.register(models.CommunicationDraft)
class CommunicationDraftAdmin(admin.ModelAdmin):
    list_display = ("version", "channel", "recipient_label", "status", "edited_at")
    list_filter = ("channel", "status")
    list_select_related = ("version", "template", "edited_by")
    search_fields = ("recipient_label", "recipient_contact", "subject", "body")


def _install_organization_roles_review_admin_url():
    if getattr(admin.site, "_wms_org_roles_review_url_installed", False):
        return

    original_get_urls = admin.site.get_urls

    def _get_urls():
        return get_organization_roles_review_urls(admin_site=admin.site) + original_get_urls()

    admin.site.get_urls = _get_urls
    admin.site._wms_org_roles_review_url_installed = True


_install_organization_roles_review_admin_url()
