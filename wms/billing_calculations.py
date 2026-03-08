from dataclasses import dataclass
from decimal import Decimal

from .models import BillingBaseUnitSource, BillingExtraUnitMode


@dataclass(frozen=True)
class ShipmentUnitInput:
    product: object | None
    quantity: int
    is_hors_format: bool = False


@dataclass(frozen=True)
class BillingBreakdown:
    base_units: int
    base_block_count: int
    extra_units: int
    base_amount: Decimal
    extra_amount: Decimal
    total_amount: Decimal
    used_manual_override: bool = False


def _category_lineage(category):
    lineage = []
    current = category
    while current is not None:
        lineage.append(current)
        current = current.parent
    return list(reversed(lineage))


def _rule_specificity(rule) -> tuple[int, int, int]:
    category_depth = len(_category_lineage(rule.category)) if rule.category_id else 0
    hors_format_bonus = 1 if rule.applies_to_hors_format else 0
    return (hors_format_bonus, category_depth, -rule.priority)


def resolve_unit_equivalence_rule(*, product=None, rules=(), is_hors_format=False):
    category = getattr(product, "category", None)
    lineage = _category_lineage(category) if category is not None else []
    lineage_ids = {item.id for item in lineage}
    candidates = []
    for rule in rules:
        if not getattr(rule, "is_active", True):
            continue
        if getattr(rule, "applies_to_hors_format", False) and not is_hors_format:
            continue
        if getattr(rule, "category_id", None) and rule.category_id not in lineage_ids:
            continue
        candidates.append(rule)
    if not candidates:
        return None
    return max(candidates, key=_rule_specificity)


def resolve_shipment_unit_count(*, items, rules=(), default_units_per_item=1) -> int:
    total_units = 0
    for item in items:
        rule = resolve_unit_equivalence_rule(
            product=item.product,
            rules=rules,
            is_hors_format=item.is_hors_format,
        )
        units_per_item = getattr(rule, "units_per_item", default_units_per_item)
        total_units += int(item.quantity) * int(units_per_item)
    return total_units


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
