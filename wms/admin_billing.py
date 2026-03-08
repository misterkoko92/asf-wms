from django.contrib import admin

from . import models


@admin.register(models.AssociationBillingProfile)
class AssociationBillingProfileAdmin(admin.ModelAdmin):
    list_display = (
        "association_profile",
        "billing_frequency",
        "grouping_mode",
        "default_currency",
        "default_computation_profile",
    )
    list_filter = ("billing_frequency", "grouping_mode", "default_currency")
    search_fields = (
        "association_profile__contact__name",
        "association_profile__user__username",
        "billing_name_override",
    )
    autocomplete_fields = ("association_profile", "default_computation_profile")


@admin.register(models.AssociationBillingChangeRequest)
class AssociationBillingChangeRequestAdmin(admin.ModelAdmin):
    list_display = (
        "association_profile",
        "requested_frequency",
        "requested_grouping_mode",
        "status",
        "requested_at",
    )
    list_filter = ("status", "requested_frequency", "requested_grouping_mode")
    search_fields = (
        "association_profile__contact__name",
        "requested_by__username",
        "review_comment",
    )
    autocomplete_fields = ("association_profile", "requested_by", "reviewed_by")


@admin.register(models.BillingComputationProfile)
class BillingComputationProfileAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "code",
        "base_unit_source",
        "base_step_size",
        "base_step_price",
        "extra_unit_mode",
        "extra_unit_price",
        "is_active",
    )
    list_filter = (
        "is_active",
        "applies_when_receipts_linked",
        "is_default_for_shipment_only",
        "is_default_for_receipt_linked",
    )
    search_fields = ("label", "code")


@admin.register(models.BillingServiceCatalogItem)
class BillingServiceCatalogItemAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "service_type",
        "default_unit_price",
        "default_currency",
        "is_discount",
        "is_active",
    )
    list_filter = ("is_active", "is_discount", "default_currency", "service_type")
    search_fields = ("label", "description", "service_type")


@admin.register(models.BillingAssociationPriceOverride)
class BillingAssociationPriceOverrideAdmin(admin.ModelAdmin):
    list_display = (
        "association_billing_profile",
        "service_catalog_item",
        "computation_profile",
        "overridden_amount",
        "currency",
    )
    list_filter = ("currency",)
    search_fields = (
        "association_billing_profile__association_profile__contact__name",
        "service_catalog_item__label",
        "computation_profile__label",
    )
    autocomplete_fields = (
        "association_billing_profile",
        "service_catalog_item",
        "computation_profile",
    )


@admin.register(models.ShipmentUnitEquivalenceRule)
class ShipmentUnitEquivalenceRuleAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "category",
        "applies_to_hors_format",
        "units_per_item",
        "priority",
        "is_active",
    )
    list_filter = ("is_active", "applies_to_hors_format")
    search_fields = ("label", "category__name", "notes")
    autocomplete_fields = ("category",)


@admin.register(models.BillingDocument)
class BillingDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "kind",
        "status",
        "correction_state",
        "association_profile",
        "document_number",
        "currency",
        "issued_at",
    )
    list_filter = ("kind", "status", "correction_state", "currency")
    search_fields = (
        "quote_number",
        "invoice_number",
        "credit_note_number",
        "association_profile__contact__name",
        "association_profile__user__username",
    )
    autocomplete_fields = (
        "association_profile",
        "computation_profile",
        "source_quote",
        "parent_document",
    )
    readonly_fields = ("issued_at", "created_at", "updated_at")

    def document_number(self, obj):
        return obj.invoice_number or obj.quote_number or obj.credit_note_number or "-"

    document_number.short_description = "Numero"


@admin.register(models.BillingDocumentLine)
class BillingDocumentLineAdmin(admin.ModelAdmin):
    list_display = ("document", "line_number", "label", "quantity", "unit_price", "total_amount")
    search_fields = ("document__invoice_number", "document__quote_number", "label", "description")
    autocomplete_fields = ("document", "service_catalog_item")


@admin.register(models.BillingDocumentShipment)
class BillingDocumentShipmentAdmin(admin.ModelAdmin):
    list_display = ("document", "shipment")
    search_fields = ("document__invoice_number", "document__quote_number", "shipment__reference")
    autocomplete_fields = ("document", "shipment")


@admin.register(models.BillingDocumentReceipt)
class BillingDocumentReceiptAdmin(admin.ModelAdmin):
    list_display = ("document", "receipt")
    search_fields = ("document__invoice_number", "document__quote_number", "receipt__reference")
    autocomplete_fields = ("document", "receipt")


@admin.register(models.BillingPayment)
class BillingPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "document",
        "amount",
        "currency",
        "paid_on",
        "payment_method",
        "reference",
    )
    list_filter = ("currency", "payment_method", "paid_on")
    search_fields = (
        "document__invoice_number",
        "document__quote_number",
        "reference",
        "comment",
    )
    autocomplete_fields = ("document", "created_by")


@admin.register(models.BillingIssue)
class BillingIssueAdmin(admin.ModelAdmin):
    list_display = ("document", "status", "reported_by", "reported_at", "resolved_by")
    list_filter = ("status", "reported_at")
    search_fields = ("document__invoice_number", "document__quote_number", "description")
    autocomplete_fields = ("document", "reported_by", "resolved_by")


@admin.register(models.ReceiptShipmentAllocation)
class ReceiptShipmentAllocationAdmin(admin.ModelAdmin):
    list_display = ("receipt", "shipment", "allocated_received_units", "created_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("receipt__reference", "shipment__reference", "note")
    autocomplete_fields = ("receipt", "shipment", "created_by")
