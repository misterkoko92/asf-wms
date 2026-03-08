from dataclasses import dataclass


@dataclass(frozen=True)
class ShipmentUnitInput:
    product: object | None
    quantity: int
    is_hors_format: bool = False


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
