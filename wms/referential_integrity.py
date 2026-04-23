from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from django.db.models import F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from contacts.models import ContactType
from wms.models import (
    AccountDocument,
    AssociationRecipient,
    Carton,
    CartonItem,
    CartonSourceKind,
    CartonStatus,
    Document,
    DocumentScanStatus,
    OrderDocument,
    OrderLine,
    ProductLot,
    ProductLotStatus,
    RecipientStructureDocument,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingAccessGrant,
)


@dataclass(frozen=True)
class ReferentialIntegrityIssue:
    code: str
    model: str
    object_id: str
    message: str

    def format(self) -> str:
        return f"[{self.code}] {self.model}#{self.object_id}: {self.message}"


def _choice_values(choices: Iterable[tuple[str, str]]) -> list[str]:
    return [value for value, _label in choices]


def _issue(code: str, model: str, object_id, message: str) -> ReferentialIntegrityIssue:
    return ReferentialIntegrityIssue(
        code=code,
        model=model,
        object_id=str(object_id),
        message=message,
    )


def find_referential_integrity_issues() -> list[ReferentialIntegrityIssue]:
    issues: list[ReferentialIntegrityIssue] = []
    issues.extend(_shipment_issues())
    issues.extend(_carton_issues())
    issues.extend(_stock_and_reservation_issues())
    issues.extend(_tracking_grant_issues())
    issues.extend(_document_scan_issues())
    issues.extend(_association_recipient_issues())
    return issues


def _shipment_issues() -> list[ReferentialIntegrityIssue]:
    issues: list[ReferentialIntegrityIssue] = []
    allowed_statuses = _choice_values(ShipmentStatus.choices)
    for shipment_id, reference, status in (
        Shipment.objects.exclude(status__in=allowed_statuses)
        .order_by("id")
        .values_list("id", "reference", "status")
    ):
        label = reference or shipment_id
        issues.append(
            _issue(
                "shipment.invalid_status",
                "Shipment",
                label,
                f"status '{status}' is not a declared ShipmentStatus.",
            )
        )

    operational_shipments = Shipment.objects.exclude(status=ShipmentStatus.DRAFT)
    for shipment_id, reference in (
        operational_shipments.filter(destination__isnull=True)
        .order_by("id")
        .values_list("id", "reference")
    ):
        issues.append(
            _issue(
                "shipment.missing_destination",
                "Shipment",
                reference or shipment_id,
                "non-draft shipment has no destination.",
            )
        )
    for field_name, code in (
        ("shipper_contact_ref", "shipment.inactive_shipper_contact"),
        ("recipient_contact_ref", "shipment.inactive_recipient_contact"),
        ("correspondent_contact_ref", "shipment.inactive_correspondent_contact"),
    ):
        filter_kwargs = {f"{field_name}__is_active": False}
        for shipment_id, reference in (
            operational_shipments.filter(**filter_kwargs)
            .order_by("id")
            .values_list("id", "reference")
        ):
            issues.append(
                _issue(
                    code,
                    "Shipment",
                    reference or shipment_id,
                    f"non-draft shipment references inactive {field_name}.",
                )
            )
    return issues


def _carton_issues() -> list[ReferentialIntegrityIssue]:
    issues: list[ReferentialIntegrityIssue] = []
    allowed_statuses = _choice_values(CartonStatus.choices)
    for carton_id, code, status in (
        Carton.objects.exclude(status__in=allowed_statuses)
        .order_by("id")
        .values_list("id", "code", "status")
    ):
        issues.append(
            _issue(
                "carton.invalid_status",
                "Carton",
                code or carton_id,
                f"status '{status}' is not a declared CartonStatus.",
            )
        )

    assigned_statuses = [CartonStatus.ASSIGNED, CartonStatus.LABELED, CartonStatus.SHIPPED]
    for carton_id, code, status in (
        Carton.objects.filter(status__in=assigned_statuses, shipment__isnull=True)
        .order_by("id")
        .values_list("id", "code", "status")
    ):
        issues.append(
            _issue(
                "carton.shipped_without_shipment",
                "Carton",
                code or carton_id,
                f"carton status '{status}' requires a shipment.",
            )
        )

    for carton_id, code in (
        Carton.objects.filter(
            source_kind=CartonSourceKind.SHIPPER_RECEIVED,
            source_receipt__isnull=True,
        )
        .order_by("id")
        .values_list("id", "code")
    ):
        issues.append(
            _issue(
                "carton.shipper_received_without_receipt",
                "Carton",
                code or carton_id,
                "shipper-received carton has no source receipt.",
            )
        )

    for item_id, quantity in (
        CartonItem.objects.filter(quantity__lte=0).order_by("id").values_list("id", "quantity")
    ):
        issues.append(
            _issue(
                "carton_item.non_positive_quantity",
                "CartonItem",
                item_id,
                f"carton item quantity must be positive, got {quantity}.",
            )
        )
    return issues


def _stock_and_reservation_issues() -> list[ReferentialIntegrityIssue]:
    issues: list[ReferentialIntegrityIssue] = []
    allowed_statuses = _choice_values(ProductLotStatus.choices)
    for lot_id, status in (
        ProductLot.objects.exclude(status__in=allowed_statuses)
        .order_by("id")
        .values_list("id", "status")
    ):
        issues.append(
            _issue(
                "stock.invalid_lot_status",
                "ProductLot",
                lot_id,
                f"status '{status}' is not a declared ProductLotStatus.",
            )
        )
    for lot_id, on_hand in (
        ProductLot.objects.filter(quantity_on_hand__lt=0)
        .order_by("id")
        .values_list("id", "quantity_on_hand")
    ):
        issues.append(
            _issue(
                "stock.negative_on_hand",
                "ProductLot",
                lot_id,
                f"quantity_on_hand must be >= 0, got {on_hand}.",
            )
        )
    for lot_id, reserved in (
        ProductLot.objects.filter(quantity_reserved__lt=0)
        .order_by("id")
        .values_list("id", "quantity_reserved")
    ):
        issues.append(
            _issue(
                "stock.negative_reserved",
                "ProductLot",
                lot_id,
                f"quantity_reserved must be >= 0, got {reserved}.",
            )
        )
    for lot_id, on_hand, reserved in (
        ProductLot.objects.filter(quantity_reserved__gt=F("quantity_on_hand"))
        .order_by("id")
        .values_list("id", "quantity_on_hand", "quantity_reserved")
    ):
        issues.append(
            _issue(
                "stock.reserved_gt_on_hand",
                "ProductLot",
                lot_id,
                f"reserved quantity {reserved} exceeds on-hand quantity {on_hand}.",
            )
        )

    for line_id, quantity, reserved in (
        OrderLine.objects.filter(reserved_quantity__gt=F("quantity"))
        .order_by("id")
        .values_list("id", "quantity", "reserved_quantity")
    ):
        issues.append(
            _issue(
                "order_line.reserved_gt_quantity",
                "OrderLine",
                line_id,
                f"reserved quantity {reserved} exceeds ordered quantity {quantity}.",
            )
        )
    for line_id, quantity, prepared in (
        OrderLine.objects.filter(prepared_quantity__gt=F("quantity"))
        .order_by("id")
        .values_list("id", "quantity", "prepared_quantity")
    ):
        issues.append(
            _issue(
                "order_line.prepared_gt_quantity",
                "OrderLine",
                line_id,
                f"prepared quantity {prepared} exceeds ordered quantity {quantity}.",
            )
        )
    for line in (
        OrderLine.objects.annotate(
            reservation_total=Coalesce(Sum("reservations__quantity"), Value(0))
        )
        .filter(reservation_total__gt=F("quantity"))
        .order_by("id")
    ):
        issues.append(
            _issue(
                "order_line.reservation_total_gt_quantity",
                "OrderLine",
                line.id,
                "reservation rows exceed ordered quantity "
                f"({line.reservation_total} > {line.quantity}).",
            )
        )
    return issues


def _tracking_grant_issues() -> list[ReferentialIntegrityIssue]:
    issues: list[ReferentialIntegrityIssue] = []
    active_grants = ShipmentTrackingAccessGrant.objects.filter(is_active=True)
    for grant_id, username in (
        active_grants.filter(user__is_active=False)
        .order_by("id")
        .values_list("id", "user__username")
    ):
        issues.append(
            _issue(
                "tracking_grant.inactive_user",
                "ShipmentTrackingAccessGrant",
                grant_id,
                f"active grant points to inactive user '{username}'.",
            )
        )
    for grant_id, contact_name in (
        active_grants.filter(contact__isnull=False, contact__is_active=False)
        .order_by("id")
        .values_list("id", "contact__name")
    ):
        issues.append(
            _issue(
                "tracking_grant.inactive_contact",
                "ShipmentTrackingAccessGrant",
                grant_id,
                f"active grant points to inactive contact '{contact_name}'.",
            )
        )
    for grant_id, volunteer_user in (
        active_grants.filter(volunteer_profile__isnull=False, volunteer_profile__is_active=False)
        .order_by("id")
        .values_list("id", "volunteer_profile__user__username")
    ):
        issues.append(
            _issue(
                "tracking_grant.inactive_volunteer",
                "ShipmentTrackingAccessGrant",
                grant_id,
                f"active grant points to inactive volunteer '{volunteer_user}'.",
            )
        )
    for grant_id, expires_at in (
        active_grants.filter(expires_at__isnull=False, expires_at__lte=timezone.now())
        .order_by("id")
        .values_list("id", "expires_at")
    ):
        issues.append(
            _issue(
                "tracking_grant.expired_active_grant",
                "ShipmentTrackingAccessGrant",
                grant_id,
                f"active grant expired at {expires_at}.",
            )
        )
    return issues


def _document_scan_issues() -> list[ReferentialIntegrityIssue]:
    issues: list[ReferentialIntegrityIssue] = []
    allowed_statuses = _choice_values(DocumentScanStatus.choices)
    for model in (Document, AccountDocument, RecipientStructureDocument, OrderDocument):
        for object_id, scan_status in (
            model.objects.exclude(scan_status__in=allowed_statuses)
            .order_by("id")
            .values_list("id", "scan_status")
        ):
            issues.append(
                _issue(
                    "document.invalid_scan_status",
                    model.__name__,
                    object_id,
                    f"scan_status '{scan_status}' is not a declared DocumentScanStatus.",
                )
            )
    return issues


def _association_recipient_issues() -> list[ReferentialIntegrityIssue]:
    issues: list[ReferentialIntegrityIssue] = []
    for recipient_id, name, contact_name in (
        AssociationRecipient.objects.filter(
            is_active=True,
            synced_contact__isnull=False,
            synced_contact__is_active=False,
        )
        .order_by("id")
        .values_list("id", "name", "synced_contact__name")
    ):
        issues.append(
            _issue(
                "association_recipient.inactive_synced_contact",
                "AssociationRecipient",
                recipient_id,
                f"active recipient '{name}' syncs to inactive contact '{contact_name}'.",
            )
        )

    for recipient_id, name, synced_contact_id in (
        AssociationRecipient.objects.filter(
            is_active=True,
            synced_contact__isnull=False,
        )
        .exclude(synced_contact__contact_type=ContactType.ORGANIZATION)
        .order_by("id")
        .values_list("id", "name", "synced_contact_id")
    ):
        issues.append(
            _issue(
                "association_recipient.synced_contact_not_organization",
                "AssociationRecipient",
                recipient_id,
                f"active recipient '{name}' syncs to non-organization contact #{synced_contact_id}.",
            )
        )
    return issues


def issue_count_by_code(issues: Iterable[ReferentialIntegrityIssue]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.code] = counts.get(issue.code, 0) + 1
    return dict(sorted(counts.items()))
