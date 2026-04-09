from django.contrib import admin
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from . import models
from .admin_badges import render_admin_status_badge


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

    display_name.short_description = gettext_lazy("Destinataire")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.PortalAccessGrant)
class PortalAccessGrantAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "role",
        "shipper",
        "recipient_organization",
        "is_active",
        "created_at",
        "reviewed_at",
    )
    list_filter = ("role", "is_active")
    search_fields = (
        "user__username",
        "user__email",
        "shipper__organization__name",
        "recipient_organization__organization__name",
        "recipient_organization__destination__city",
    )
    autocomplete_fields = (
        "user",
        "recipient_organization",
        "created_by",
        "reviewed_by",
    )
    readonly_fields = ("created_at",)
    list_select_related = (
        "user",
        "shipper__organization",
        "recipient_organization__organization",
        "recipient_organization__destination",
        "created_by",
        "reviewed_by",
    )
    fields = (
        "user",
        "role",
        "shipper",
        "recipient_organization",
        "is_active",
        "created_by",
        "created_at",
        "reviewed_by",
        "reviewed_at",
    )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly_fields.extend(
                [
                    "user",
                    "role",
                    "shipper",
                    "recipient_organization",
                    "created_by",
                ]
            )
        return tuple(readonly_fields)


@admin.register(models.ShipmentRecipientOrganization)
class ShipmentRecipientOrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "destination",
        "validation_status",
        "is_correspondent",
        "is_active",
        "active_recipient_contact_count",
        "active_shipper_link_count",
        "active_portal_grant_count",
    )
    list_filter = ("validation_status", "is_correspondent", "is_active", "destination")
    search_fields = (
        "organization__name",
        "destination__city",
        "destination__iata_code",
    )
    autocomplete_fields = ("organization", "destination")
    list_select_related = ("organization", "destination")
    readonly_fields = (
        "active_recipient_contact_count",
        "active_shipper_link_count",
        "active_portal_grant_count",
    )
    fields = (
        "organization",
        "destination",
        "validation_status",
        "is_correspondent",
        "is_active",
        "active_recipient_contact_count",
        "active_shipper_link_count",
        "active_portal_grant_count",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("organization", "destination").annotate(
            active_recipient_contact_count_value=Count(
                "recipient_contacts",
                filter=Q(recipient_contacts__is_active=True),
                distinct=True,
            ),
            active_shipper_link_count_value=Count(
                "shipper_links",
                filter=Q(shipper_links__is_active=True),
                distinct=True,
            ),
            active_portal_grant_count_value=Count(
                "portal_access_grants",
                filter=Q(portal_access_grants__is_active=True),
                distinct=True,
            ),
        )

    @admin.display(description=gettext_lazy("Référents actifs"))
    def active_recipient_contact_count(self, obj):
        return getattr(obj, "active_recipient_contact_count_value", 0)

    @admin.display(description=gettext_lazy("Liens expéditeur actifs"))
    def active_shipper_link_count(self, obj):
        return getattr(obj, "active_shipper_link_count_value", 0)

    @admin.display(description=gettext_lazy("Accès portail actifs"))
    def active_portal_grant_count(self, obj):
        return getattr(obj, "active_portal_grant_count_value", 0)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly_fields.extend(["organization", "destination"])
        return tuple(readonly_fields)


@admin.register(models.RecipientProductPreference)
class RecipientProductPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "recipient_organization",
        "target_label",
        "status",
        "quantity_target",
        "period_unit",
        "source",
        "updated_at",
    )
    list_filter = ("status", "period_unit", "source")
    search_fields = (
        "recipient_organization__organization__name",
        "recipient_organization__destination__city",
        "product__name",
        "category__name",
    )
    autocomplete_fields = (
        "recipient_organization",
        "product",
        "category",
        "created_by",
        "updated_by",
    )
    list_select_related = (
        "recipient_organization__organization",
        "recipient_organization__destination",
        "product",
        "category",
        "created_by",
        "updated_by",
    )
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "recipient_organization",
        "product",
        "category",
        "status",
        "quantity_target",
        "period_unit",
        "notes",
        "source",
        "created_by",
        "created_at",
        "updated_by",
        "updated_at",
    )

    @admin.display(description=gettext_lazy("Cible"))
    def target_label(self, obj):
        if obj.product_id:
            return obj.product.name
        if obj.category_id:
            return obj.category.name
        return "-"

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly_fields.extend(["recipient_organization", "product", "category"])
        return tuple(readonly_fields)


@admin.register(models.RecipientStructureDocument)
class RecipientStructureDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "contact",
        "doc_type",
        "status",
        "scan_status",
        "uploaded_at",
        "reviewed_at",
    )
    list_filter = ("doc_type", "status", "scan_status")
    search_fields = (
        "contact__name",
        "uploaded_by__username",
        "uploaded_by__email",
        "reviewed_by__username",
        "reviewed_by__email",
    )
    autocomplete_fields = ("contact", "uploaded_by", "reviewed_by")
    list_select_related = ("contact", "uploaded_by", "reviewed_by")
    readonly_fields = ("uploaded_at", "scan_updated_at")
    fields = (
        "contact",
        "doc_type",
        "status",
        "file",
        "scan_status",
        "scan_message",
        "scan_updated_at",
        "uploaded_by",
        "uploaded_at",
        "reviewed_by",
        "reviewed_at",
    )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly_fields.extend(["contact", "doc_type", "uploaded_by"])
        return tuple(readonly_fields)


class _OrderDocumentStatusMixin:
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


@admin.register(models.OrderDocument)
class OrderDocumentAdmin(_OrderDocumentStatusMixin, admin.ModelAdmin):
    list_display = ("doc_type", "order", "status_badge", "uploaded_at")
    list_filter = ("status", "doc_type")
    search_fields = ("order__reference",)

    def status_badge(self, obj):
        return render_admin_status_badge(
            status_value=obj.status,
            label=obj.get_status_display(),
            domain="document_review",
        )

    status_badge.short_description = "status"
    status_badge.admin_order_field = "status"


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
        "status_badge",
    )
    list_filter = ("direction", "status", "source", "event_type")
    search_fields = ("source", "target", "event_type", "external_id")
    readonly_fields = ("created_at", "processed_at")

    def status_badge(self, obj):
        return render_admin_status_badge(
            status_value=obj.status,
            label=obj.get_status_display(),
            domain="integration",
        )

    status_badge.short_description = "status"
    status_badge.admin_order_field = "status"
