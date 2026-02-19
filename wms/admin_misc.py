from django.contrib import admin
from django.utils import timezone

from . import models


@admin.register(models.ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")
    search_fields = ("name",)
    list_select_related = ("parent",)


@admin.register(models.ProductTag)
class ProductTagAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(models.AssociationProfile)
class AssociationProfileAdmin(admin.ModelAdmin):
    list_display = ("contact", "user", "created_at")
    search_fields = ("contact__name", "user__username", "user__email")


@admin.register(models.AssociationRecipient)
class AssociationRecipientAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "association_contact",
        "destination",
        "city",
        "country",
        "notify_deliveries",
        "is_delivery_contact",
        "is_active",
    )
    list_filter = (
        "is_active",
        "notify_deliveries",
        "is_delivery_contact",
        "country",
        "destination",
    )
    search_fields = (
        "name",
        "structure_name",
        "contact_last_name",
        "contact_first_name",
        "association_contact__name",
        "city",
    )

    def display_name(self, obj):
        return obj.get_display_name()

    display_name.short_description = "Destinataire"


class _OrderDocumentStatusMixin:
    actions = ("mark_approved", "mark_rejected")

    def mark_approved(self, request, queryset):
        updated = queryset.update(
            status=models.DocumentReviewStatus.APPROVED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f"{updated} document(s) approuvé(s).")

    mark_approved.short_description = "Marquer comme approuvé"

    def mark_rejected(self, request, queryset):
        updated = queryset.update(
            status=models.DocumentReviewStatus.REJECTED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f"{updated} document(s) refusé(s).")

    mark_rejected.short_description = "Marquer comme refusé"


@admin.register(models.OrderDocument)
class OrderDocumentAdmin(_OrderDocumentStatusMixin, admin.ModelAdmin):
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
