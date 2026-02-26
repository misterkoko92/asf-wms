from collections import defaultdict


class KitCycleError(ValueError):
    def __init__(self, cycle_ids):
        self.cycle_ids = [int(product_id) for product_id in cycle_ids if product_id]
        cycle_path = " -> ".join(str(product_id) for product_id in self.cycle_ids)
        super().__init__(f"Cycle detecte dans la composition des kits: {cycle_path}")


def _get_kit_items(product):
    cached = getattr(product, "_prefetched_objects_cache", {}).get("kit_items")
    if cached is not None:
        return list(cached)
    return list(product.kit_items.select_related("component"))


def get_unit_component_quantities(product, *, _memo=None, _stack=None):
    if product is None or not getattr(product, "id", None):
        return {}
    memo = _memo if _memo is not None else {}
    stack = _stack if _stack is not None else []
    product_id = product.id
    cached = memo.get(product_id)
    if cached is not None:
        return cached
    if product_id in stack:
        cycle_start = stack.index(product_id)
        raise KitCycleError(stack[cycle_start:] + [product_id])

    stack.append(product_id)
    kit_items = _get_kit_items(product)
    if not kit_items:
        result = {product_id: 1}
    else:
        totals = defaultdict(int)
        for kit_item in kit_items:
            kit_quantity = int(kit_item.quantity or 0)
            if kit_quantity <= 0:
                continue
            for component_id, component_quantity in get_unit_component_quantities(
                kit_item.component,
                _memo=memo,
                _stack=stack,
            ).items():
                totals[component_id] += component_quantity * kit_quantity
        result = dict(totals)
    stack.pop()
    memo[product_id] = result
    return result


def get_component_quantities(product, *, quantity=1):
    requested_quantity = int(quantity or 0)
    if requested_quantity <= 0:
        return {}
    unit_quantities = get_unit_component_quantities(product)
    if requested_quantity == 1:
        return dict(unit_quantities)
    return {
        component_id: component_quantity * requested_quantity
        for component_id, component_quantity in unit_quantities.items()
    }
