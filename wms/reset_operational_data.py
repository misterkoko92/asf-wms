from __future__ import annotations

from dataclasses import dataclass

from django.apps import apps
from django.db import transaction

KEEP_MODEL_LABELS = frozenset(
    {
        "auth.Group",
        "auth.Permission",
        "auth.User",
        "contenttypes.ContentType",
        "sessions.Session",
        "wms.Warehouse",
        "wms.Location",
        "wms.RackColor",
        "wms.Product",
        "wms.ProductCategory",
        "wms.ProductTag",
        "wms.ProductKitItem",
        "wms.CartonFormat",
        "wms.PrintTemplate",
        "wms.PrintPack",
        "wms.PrintPackDocument",
        "wms.PrintCellMapping",
        "wms.DocumentRequirementTemplate",
        "wms.CommunicationTemplate",
        "wms.PlanningParameterSet",
        "wms.BillingComputationProfile",
        "wms.BillingServiceCatalogItem",
        "wms.RoleEventPolicy",
        "wms.ShipmentUnitEquivalenceRule",
        "wms.WmsRuntimeSettings",
    }
)

DELETE_BATCHES = (
    (
        "audit_and_generated_history",
        (
            "admin.LogEntry",
            "wms.IntegrationEvent",
            "wms.WmsRuntimeSettingsAudit",
            "wms.UserUiPreference",
            "wms.GeneratedPrintArtifactItem",
            "wms.GeneratedPrintArtifact",
            "wms.PrintTemplateVersion",
            "wms.PrintPackDocumentVersion",
        ),
    ),
    (
        "planning_runtime",
        (
            "wms.CommunicationDraft",
            "wms.PlanningFlightSnapshot",
            "wms.PlanningShipmentSnapshot",
            "wms.PlanningVolunteerSnapshot",
            "wms.PlanningIssue",
            "wms.PlanningArtifact",
            "wms.PlanningAssignment",
            "wms.PlanningVersion",
            "wms.PlanningRun",
            "wms.Flight",
            "wms.FlightSourceBatch",
        ),
    ),
    (
        "billing_links_and_history",
        (
            "wms.BillingDocumentShipment",
            "wms.BillingDocumentReceipt",
            "wms.BillingDocumentLine",
            "wms.BillingPayment",
            "wms.BillingIssue",
            "wms.BillingDocument",
        ),
    ),
    (
        "shipment_order_receipt_runtime",
        (
            "wms.ReceiptShipmentAllocation",
            "wms.OrderReservation",
            "wms.OrderDocument",
            "wms.OrderLine",
            "wms.Document",
            "wms.ShipmentTrackingEvent",
            "wms.CartonStatusEvent",
            "wms.CartonItem",
            "wms.StockMovement",
            "wms.ProductLot",
            "wms.Carton",
            "wms.ReceiptHorsFormat",
            "wms.ReceiptLine",
            "wms.Order",
            "wms.PublicOrderLink",
            "wms.Receipt",
            "wms.Shipment",
        ),
    ),
    (
        "portal_billing_and_volunteer_runtime",
        (
            "wms.AccountDocument",
            "wms.PublicAccountRequest",
            "wms.VolunteerAccountRequest",
            "wms.AssociationPortalContact",
            "wms.AssociationRecipient",
            "wms.AssociationBillingChangeRequest",
            "wms.BillingAssociationPriceOverride",
            "wms.AssociationBillingProfile",
            "wms.AssociationProfile",
            "wms.VolunteerAvailability",
            "wms.VolunteerConstraint",
            "wms.VolunteerUnavailability",
            "wms.VolunteerProfile",
        ),
    ),
    (
        "org_roles_and_reviews",
        (
            "wms.ContactSubscription",
            "wms.ComplianceOverride",
            "wms.OrganizationRoleDocument",
            "wms.OrganizationRoleContact",
            "wms.OrganizationContact",
            "wms.RecipientBinding",
            "wms.ShipperScope",
            "wms.MigrationReviewItem",
            "wms.OrganizationRoleAssignment",
        ),
    ),
    (
        "destinations",
        (
            "wms.DestinationCorrespondentOverride",
            "wms.DestinationCorrespondentDefault",
            "wms.PlanningDestinationRule",
            "wms.Destination",
        ),
    ),
    (
        "contacts",
        (
            "contacts.ContactAddress",
            "contacts.Contact",
            "contacts.ContactTag",
        ),
    ),
    (
        "operational_sequences",
        (
            "wms.ReceiptDonorSequence",
            "wms.ReceiptSequence",
            "wms.ShipmentSequence",
        ),
    ),
    (
        "generated_state_cleanup",
        ("wms.WmsChange",),
    ),
)


@dataclass(frozen=True)
class ResetOperationalDataSummary:
    mode: str
    delete_counts_before: dict[str, int]
    delete_counts_after: dict[str, int]
    keep_counts_before: dict[str, int]
    keep_counts_after: dict[str, int]


def _all_known_model_labels() -> set[str]:
    return {f"{model._meta.app_label}.{model._meta.object_name}" for model in apps.get_models()}


def _delete_model_labels() -> tuple[str, ...]:
    labels: list[str] = []
    for _batch_name, batch_labels in DELETE_BATCHES:
        labels.extend(batch_labels)
    return tuple(labels)


def _resolve_model(label: str):
    model = apps.get_model(label)
    if model is None:  # pragma: no cover - defensive
        raise LookupError(f"Unknown model label: {label}")
    return model


def _count_labels(labels: tuple[str, ...] | frozenset[str]) -> dict[str, int]:
    counts = {}
    for label in labels:
        counts[label] = _resolve_model(label)._default_manager.count()
    return counts


def _validate_configuration():
    known_labels = _all_known_model_labels()
    delete_labels = set(_delete_model_labels())
    duplicates = [label for label in delete_labels if label in KEEP_MODEL_LABELS]
    if duplicates:
        raise ValueError(f"Models configured to both keep and delete: {sorted(duplicates)}")

    configured_labels = set(KEEP_MODEL_LABELS).union(delete_labels)
    missing_labels = sorted(known_labels - configured_labels)
    extra_labels = sorted(configured_labels - known_labels)
    if missing_labels:
        raise ValueError(f"Reset configuration missing model labels: {missing_labels}")
    if extra_labels:
        raise ValueError(f"Reset configuration references unknown model labels: {extra_labels}")


def reset_operational_data(*, apply: bool) -> ResetOperationalDataSummary:
    _validate_configuration()

    delete_labels = _delete_model_labels()
    keep_counts_before = _count_labels(KEEP_MODEL_LABELS)
    delete_counts_before = _count_labels(delete_labels)

    if not apply:
        return ResetOperationalDataSummary(
            mode="DRY RUN",
            delete_counts_before=delete_counts_before,
            delete_counts_after=delete_counts_before.copy(),
            keep_counts_before=keep_counts_before,
            keep_counts_after=keep_counts_before.copy(),
        )

    with transaction.atomic():
        for _batch_name, batch_labels in DELETE_BATCHES:
            for label in batch_labels:
                _resolve_model(label)._default_manager.all().delete()

        keep_counts_after = _count_labels(KEEP_MODEL_LABELS)
        delete_counts_after = _count_labels(delete_labels)

        for label, count in delete_counts_after.items():
            if count != 0:
                raise ValueError(f"Model {label} still has {count} row(s) after reset")
        for label, before in keep_counts_before.items():
            after = keep_counts_after[label]
            if after != before:
                raise ValueError(
                    f"Preserved model {label} changed during reset ({before} -> {after})"
                )

        return ResetOperationalDataSummary(
            mode="APPLY",
            delete_counts_before=delete_counts_before,
            delete_counts_after=delete_counts_after,
            keep_counts_before=keep_counts_before,
            keep_counts_after=keep_counts_after,
        )
