from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .billing_calculations import build_billing_breakdown
from .models import (
    BillingComputationProfile,
    BillingDocument,
    BillingDocumentKind,
    BillingDocumentLine,
    BillingDocumentReceipt,
    BillingDocumentShipment,
    BillingDocumentStatus,
    BillingPayment,
    BillingPaymentMethod,
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
    currency=None,
    exchange_rate=None,
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
            currency=(currency or billing_profile.default_currency or "EUR").upper(),
            exchange_rate=exchange_rate,
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
        .prefetch_related("shipment_links__shipment", "receipt_links__receipt", "lines", "payments")
        .get(pk=document.pk)
    )


def _managed_document_queryset():
    return BillingDocument.objects.select_related(
        "association_profile__contact",
        "association_profile__billing_profile",
        "computation_profile",
        "parent_document",
    ).prefetch_related(
        "shipment_links__shipment",
        "receipt_links__receipt",
        "lines",
        "payments",
        "child_documents",
    )


def recompute_invoice_status(*, document):
    document = _managed_document_queryset().get(pk=document.pk)
    if document.kind != BillingDocumentKind.INVOICE:
        return document
    if document.status in {
        BillingDocumentStatus.DRAFT,
        BillingDocumentStatus.CANCELLED,
        BillingDocumentStatus.CANCELLED_OR_CORRECTED,
    }:
        return document

    paid_amount = sum((payment.amount for payment in document.payments.all()), Decimal("0.00"))
    total_amount = document.lines_total_amount()
    if paid_amount <= 0 or total_amount <= 0:
        new_status = BillingDocumentStatus.ISSUED
    elif paid_amount < total_amount:
        new_status = BillingDocumentStatus.PARTIALLY_PAID
    else:
        new_status = BillingDocumentStatus.PAID

    if document.status != new_status:
        BillingDocument.objects.filter(pk=document.pk).update(
            status=new_status,
            updated_at=timezone.now(),
        )
        document.status = new_status
    return document


def record_billing_payment(
    *,
    document,
    amount,
    payment_method=BillingPaymentMethod.BANK_TRANSFER,
    paid_on=None,
    reference="",
    comment="",
    created_by=None,
    currency=None,
    proof_attachment=None,
):
    document = _managed_document_queryset().get(pk=document.pk)
    if document.kind != BillingDocumentKind.INVOICE:
        raise ValueError("Payments can only be recorded on invoices.")
    if document.status == BillingDocumentStatus.DRAFT:
        raise ValueError("Issued invoices are required before recording payments.")

    BillingPayment.objects.create(
        document=document,
        amount=Decimal(str(amount)),
        currency=(currency or document.currency or "EUR").upper(),
        paid_on=paid_on or timezone.localdate(),
        payment_method=payment_method,
        reference=(reference or "").strip(),
        comment=(comment or "").strip(),
        proof_attachment=proof_attachment,
        created_by=created_by,
    )
    return recompute_invoice_status(document=document)


def _clone_document_links(*, source_document, target_document):
    for shipment_link in source_document.shipment_links.all():
        BillingDocumentShipment.objects.create(
            document=target_document,
            shipment=shipment_link.shipment,
        )
    for receipt_link in source_document.receipt_links.all():
        BillingDocumentReceipt.objects.create(
            document=target_document,
            receipt=receipt_link.receipt,
        )


def _clone_document_lines(*, source_document, target_document, negate_amounts):
    for line in source_document.lines.order_by("line_number"):
        multiplier = Decimal("-1.00") if negate_amounts else Decimal("1.00")
        BillingDocumentLine.objects.create(
            document=target_document,
            line_number=line.line_number,
            label=line.label,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price * multiplier,
            total_amount=line.total_amount * multiplier,
            service_catalog_item=line.service_catalog_item,
            is_manual=line.is_manual,
        )


def create_credit_note_for_invoice(*, document, credit_note_number=None, created_by=None):
    del created_by
    document = _managed_document_queryset().get(pk=document.pk)
    if document.kind != BillingDocumentKind.INVOICE:
        raise ValueError("Credit notes can only be created from invoices.")

    with transaction.atomic():
        credit_note = BillingDocument.objects.create(
            association_profile=document.association_profile,
            kind=BillingDocumentKind.CREDIT_NOTE,
            status=BillingDocumentStatus.ISSUED,
            parent_document=document,
            computation_profile=document.computation_profile,
            currency=document.currency,
            exchange_rate=document.exchange_rate,
            credit_note_number=(credit_note_number or "").strip() or None,
            issued_at=timezone.now(),
        )
        _clone_document_links(source_document=document, target_document=credit_note)
        _clone_document_lines(
            source_document=document,
            target_document=credit_note,
            negate_amounts=True,
        )
        credit_note.issued_snapshot = build_issued_document_snapshot(document=credit_note)
        credit_note.save(update_fields=["issued_snapshot", "updated_at"])
        BillingDocument.objects.filter(pk=document.pk).update(
            status=BillingDocumentStatus.CANCELLED_OR_CORRECTED,
            updated_at=timezone.now(),
        )

    return _managed_document_queryset().get(pk=credit_note.pk)


def create_replacement_invoice_from_invoice(*, document, created_by=None):
    del created_by
    document = _managed_document_queryset().get(pk=document.pk)
    if document.kind != BillingDocumentKind.INVOICE:
        raise ValueError("Replacement invoices can only be created from invoices.")

    with transaction.atomic():
        replacement_invoice = BillingDocument.objects.create(
            association_profile=document.association_profile,
            kind=BillingDocumentKind.INVOICE,
            status=BillingDocumentStatus.DRAFT,
            parent_document=document,
            computation_profile=document.computation_profile,
            currency=document.currency,
            exchange_rate=document.exchange_rate,
        )
        _clone_document_links(source_document=document, target_document=replacement_invoice)
        _clone_document_lines(
            source_document=document,
            target_document=replacement_invoice,
            negate_amounts=False,
        )

    return _managed_document_queryset().get(pk=replacement_invoice.pk)


def _formatted_decimal(value):
    if value is None:
        return None
    return format(value, "f")


def _resolved_document_number(document):
    return (
        document.invoice_number
        or document.quote_number
        or document.credit_note_number
        or f"BILL-{document.pk}"
    )


def _resolved_billing_name(document):
    billing_profile = document.association_profile.billing_profile
    return (
        billing_profile.billing_name_override or ""
    ).strip() or document.association_profile.contact.name


def _resolved_billing_address(document):
    billing_profile = document.association_profile.billing_profile
    override = (billing_profile.billing_address_override or "").strip()
    if override:
        return override
    address = document.association_profile.contact.get_effective_address()
    if address is None:
        return ""
    city_line = " ".join(part for part in [address.postal_code, address.city] if part).strip()
    return "\n".join(
        part
        for part in [
            address.address_line1,
            address.address_line2,
            city_line,
            address.region,
            address.country,
        ]
        if part
    )


def build_billing_document_shipment_rows(*, document):
    shipment_rows = []
    shipment_links = document.shipment_links.select_related("shipment").order_by("shipment__id")
    for shipment_link in shipment_links:
        shipment = shipment_link.shipment
        shipment_date = resolve_shipment_billing_date(shipment)
        carton_count = _carton_count_for_shipment(shipment)
        shipment_rows.append(
            {
                "reference": shipment.reference,
                "shipment_date": shipment_date.isoformat(),
                "carton_count": carton_count,
                "comment": (
                    f"Expedition {shipment.reference} | "
                    f"Date expedition: {shipment_date.isoformat()} | "
                    f"Colis: {carton_count}"
                ),
            }
        )
    return shipment_rows


def build_issued_document_snapshot(*, document):
    lines = list(document.lines.order_by("line_number"))
    total_amount = sum((line.total_amount for line in lines), Decimal("0.00"))
    return {
        "kind": document.kind,
        "number": _resolved_document_number(document),
        "billing_name": _resolved_billing_name(document),
        "billing_address": _resolved_billing_address(document),
        "currency": document.currency,
        "exchange_rate": _formatted_decimal(document.exchange_rate),
        "total_amount": _formatted_decimal(total_amount),
        "lines": [
            {
                "line_number": line.line_number,
                "label": line.label,
                "description": line.description,
                "quantity": _formatted_decimal(line.quantity),
                "unit_price": _formatted_decimal(line.unit_price),
                "total_amount": _formatted_decimal(line.total_amount),
            }
            for line in lines
        ],
        "shipments": build_billing_document_shipment_rows(document=document),
    }


def issue_billing_document(*, document, invoice_number=None):
    document = (
        BillingDocument.objects.select_related(
            "association_profile__contact",
            "association_profile__billing_profile",
            "computation_profile",
        )
        .prefetch_related("lines")
        .get(pk=document.pk)
    )
    if document.kind == BillingDocumentKind.INVOICE:
        resolved_invoice_number = (
            invoice_number if invoice_number is not None else document.invoice_number
        )
        resolved_invoice_number = (resolved_invoice_number or "").strip()
        if not resolved_invoice_number:
            raise ValueError("Invoice number is required before issue.")
        document.invoice_number = resolved_invoice_number

    document.issued_snapshot = build_issued_document_snapshot(document=document)
    document.status = BillingDocumentStatus.ISSUED
    if document.issued_at is None:
        document.issued_at = timezone.now()
    document.save()
    return (
        BillingDocument.objects.select_related(
            "association_profile__contact",
            "association_profile__billing_profile",
            "computation_profile",
        )
        .prefetch_related("shipment_links__shipment", "receipt_links__receipt", "lines")
        .get(pk=document.pk)
    )


def build_billing_document_render_payload(*, document):
    snapshot = document.issued_snapshot or {}
    lines = snapshot.get("lines")
    if not lines:
        lines = [
            {
                "line_number": line.line_number,
                "label": line.label,
                "description": line.description,
                "quantity": _formatted_decimal(line.quantity),
                "unit_price": _formatted_decimal(line.unit_price),
                "total_amount": _formatted_decimal(line.total_amount),
            }
            for line in document.lines.order_by("line_number")
        ]
    total_amount = snapshot.get("total_amount")
    if total_amount is None:
        total_amount = _formatted_decimal(
            sum((line.total_amount for line in document.lines.all()), Decimal("0.00"))
        )
    return {
        "kind": document.kind,
        "status": document.status,
        "number": snapshot.get("number") or _resolved_document_number(document),
        "billing_name": snapshot.get("billing_name") or _resolved_billing_name(document),
        "billing_address": snapshot.get("billing_address") or _resolved_billing_address(document),
        "currency": snapshot.get("currency") or document.currency,
        "exchange_rate": snapshot.get("exchange_rate")
        or _formatted_decimal(document.exchange_rate),
        "total_amount": total_amount,
        "lines": lines,
        "shipments": snapshot.get("shipments")
        or build_billing_document_shipment_rows(document=document),
    }
