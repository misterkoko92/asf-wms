from dataclasses import dataclass
from decimal import Decimal

from .models import BillingBaseUnitSource, BillingExtraUnitMode
from .unit_equivalence import (
    ShipmentUnitInput,
    resolve_shipment_unit_count,
    resolve_unit_equivalence_rule,
)


@dataclass(frozen=True)
class BillingBreakdown:
    base_units: int
    base_block_count: int
    extra_units: int
    base_amount: Decimal
    extra_amount: Decimal
    total_amount: Decimal
    used_manual_override: bool = False


def compute_started_block_count(units: int, step_size: int) -> int:
    if units <= 0:
        return 0
    return ((units - 1) // step_size) + 1


def _resolve_base_units(*, profile, shipped_units, allocated_received_units, manual_base_units):
    used_manual_override = False
    if profile.allow_manual_override and manual_base_units is not None:
        return max(0, int(manual_base_units)), True
    if profile.base_unit_source == BillingBaseUnitSource.SHIPPED_UNITS:
        return max(0, int(shipped_units)), used_manual_override
    if profile.base_unit_source == BillingBaseUnitSource.ALLOCATED_RECEIVED_UNITS:
        return max(0, int(allocated_received_units or 0)), used_manual_override
    if profile.base_unit_source == BillingBaseUnitSource.MANUAL:
        return max(0, int(manual_base_units or 0)), manual_base_units is not None
    return 0, used_manual_override


def _resolve_extra_units(*, profile, shipped_units, allocated_received_units, manual_extra_units):
    used_manual_override = False
    if profile.allow_manual_override and manual_extra_units is not None:
        return max(0, int(manual_extra_units)), True
    if profile.extra_unit_mode == BillingExtraUnitMode.NONE:
        return 0, used_manual_override
    if profile.extra_unit_mode == BillingExtraUnitMode.SHIPPED_MINUS_ALLOCATED_RECEIVED:
        return max(0, int(shipped_units) - int(allocated_received_units or 0)), used_manual_override
    if profile.extra_unit_mode == BillingExtraUnitMode.MANUAL:
        return max(0, int(manual_extra_units or 0)), manual_extra_units is not None
    return 0, used_manual_override


def build_billing_breakdown(
    *,
    profile,
    shipped_units,
    allocated_received_units=0,
    manual_base_units=None,
    manual_extra_units=None,
) -> BillingBreakdown:
    base_units, used_manual_base = _resolve_base_units(
        profile=profile,
        shipped_units=shipped_units,
        allocated_received_units=allocated_received_units,
        manual_base_units=manual_base_units,
    )
    extra_units, used_manual_extra = _resolve_extra_units(
        profile=profile,
        shipped_units=shipped_units,
        allocated_received_units=allocated_received_units,
        manual_extra_units=manual_extra_units,
    )
    base_block_count = compute_started_block_count(base_units, int(profile.base_step_size))
    base_amount = Decimal(base_block_count) * profile.base_step_price
    extra_amount = Decimal(extra_units) * profile.extra_unit_price
    total_amount = base_amount + extra_amount
    return BillingBreakdown(
        base_units=base_units,
        base_block_count=base_block_count,
        extra_units=extra_units,
        base_amount=base_amount,
        extra_amount=extra_amount,
        total_amount=total_amount,
        used_manual_override=used_manual_base or used_manual_extra,
    )
