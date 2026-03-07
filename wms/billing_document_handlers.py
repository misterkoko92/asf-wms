from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from .billing_calculations import build_billing_breakdown
from .models import (
    BillingComputationProfile,
    BillingDocument,
    BillingDocumentKind,
    BillingDocumentLine,
    BillingDocumentReceipt,
    BillingDocumentShipment,
    BillingDocumentStatus,
    Shipment,
    ShipmentStatus,
)


@dataclass(frozen=True)
class BillingEditorCandidateRow:
    shipment_id: int
    reference: str
    billing_date: object
    carton_count: int
    allocated_received_units: int


def resolve_shipment_billing_date(shipment):
    if shipment.ready_at is not None:
        return shipment.ready_at.date()
    return shipment.created_at.date()


def _period_includes(period, billing_date):
    if period is None:
        return True
    period_start, period_end = period
    if period_start and billing_date < period_start:
        return False
    if period_end and billing_date > period_end:
        return False
    return True


def _carton_count_for_shipment(shipment):
    return shipment.carton_set.count()


def _allocated_units_for_shipment(shipment):
    return sum(
        allocation.allocated_received_units for allocation in shipment.receipt_allocations.all()
    )


def _resolve_document_computation_profile(*, association_profile):
    billing_profile = association_profile.billing_profile
    if billing_profile.default_computation_profile_id:
        return billing_profile.default_computation_profile
    return (
        BillingComputationProfile.objects.filter(is_active=True, is_default_for_shipment_only=True)
        .order_by("label", "code")
        .first()
    )


def build_editor_candidates(*, association_profile, kind, period=None):
    queryset = (
        Shipment.objects.filter(
            shipper_contact_ref=association_profile.contact,
            status=ShipmentStatus.SHIPPED,
            archived_at__isnull=True,
        )
        .prefetch_related("receipt_allocations")
        .order_by("-ready_at", "-created_at", "-id")
    )
    if kind == BillingDocumentKind.INVOICE:
        queryset = queryset.exclude(
            billing_document_links__document__kind=BillingDocumentKind.INVOICE,
            billing_document_links__document__status=BillingDocumentStatus.ISSUED,
        )
    rows = []
    for shipment in queryset.distinct():
        billing_date = resolve_shipment_billing_date(shipment)
        if not _period_includes(period, billing_date):
            continue
        rows.append(
            BillingEditorCandidateRow(
                shipment_id=shipment.id,
                reference=shipment.reference,
                billing_date=billing_date,
                carton_count=_carton_count_for_shipment(shipment),
                allocated_received_units=_allocated_units_for_shipment(shipment),
            )
        )
    return rows


def _create_document_line(*, document, line_number, shipment, computation_profile):
    carton_count = _carton_count_for_shipment(shipment)
    allocated_received_units = _allocated_units_for_shipment(shipment)
    total_amount = Decimal("0.00")
    if computation_profile is not None:
        breakdown = build_billing_breakdown(
            profile=computation_profile,
            shipped_units=carton_count,
            allocated_received_units=allocated_received_units,
        )
        total_amount = breakdown.total_amount
    return BillingDocumentLine.objects.create(
        document=document,
        line_number=line_number,
        label=f"Expedition {shipment.reference}",
        description=(
            f"Date expedition: {resolve_shipment_billing_date(shipment)} | "
            f"Colis: {carton_count} | Reference: {shipment.reference}"
        ),
        quantity=Decimal("1.00"),
        unit_price=total_amount,
        total_amount=total_amount,
        is_manual=False,
    )


def create_billing_draft(
    *,
    association_profile,
    kind,
    shipment_ids,
    created_by=None,
    manual_lines=None,
):
    selected_shipments = list(
        Shipment.objects.filter(
            pk__in=shipment_ids, shipper_contact_ref=association_profile.contact
        )
        .prefetch_related("receipt_allocations")
        .order_by("id")
    )
    if not selected_shipments:
        raise ValueError("At least one shipment must be selected to build a billing draft.")

    computation_profile = _resolve_document_computation_profile(
        association_profile=association_profile
    )
    billing_profile = association_profile.billing_profile

    with transaction.atomic():
        document = BillingDocument.objects.create(
            association_profile=association_profile,
            kind=kind,
            status=BillingDocumentStatus.DRAFT,
            computation_profile=computation_profile,
            currency=billing_profile.default_currency,
        )
        line_number = 1
        receipt_ids = set()
        for shipment in selected_shipments:
            BillingDocumentShipment.objects.create(document=document, shipment=shipment)
            for allocation in shipment.receipt_allocations.all():
                receipt_ids.add(allocation.receipt_id)
            _create_document_line(
                document=document,
                line_number=line_number,
                shipment=shipment,
                computation_profile=computation_profile,
            )
            line_number += 1

        for receipt_id in sorted(receipt_ids):
            BillingDocumentReceipt.objects.create(document=document, receipt_id=receipt_id)

        for manual_line in manual_lines or []:
            label = (manual_line.get("label") or "").strip()
            if not label:
                continue
            amount = Decimal(str(manual_line.get("amount") or "0"))
            BillingDocumentLine.objects.create(
                document=document,
                line_number=line_number,
                label=label,
                description=(manual_line.get("description") or "").strip(),
                quantity=Decimal("1.00"),
                unit_price=amount,
                total_amount=amount,
                is_manual=True,
            )
            line_number += 1

    return (
        BillingDocument.objects.select_related(
            "association_profile__contact", "computation_profile"
        )
        .prefetch_related("shipment_links__shipment", "receipt_links__receipt", "lines")
        .get(pk=document.pk)
    )
