def category_levels(category, *, max_levels=4):
    if not category:
        return [""] * max_levels
    parts = []
    current = category
    while current:
        parts.append(current.name)
        current = current.parent
    parts.reverse()
    parts = parts[:max_levels]
    while len(parts) < max_levels:
        parts.append("")
    return parts


def build_product_display(product):
    category_parts = category_levels(product.category)
    tags = " | ".join(product.tags.values_list("name", flat=True))
    location = product.default_location
    return {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "brand": product.brand,
        "color": product.color,
        "category_l1": category_parts[0],
        "category_l2": category_parts[1],
        "category_l3": category_parts[2],
        "category_l4": category_parts[3],
        "barcode": product.barcode,
        "ean": product.ean,
        "tags": tags,
        "pu_ht": product.pu_ht or "",
        "tva": product.tva or "",
        "length_cm": product.length_cm or "",
        "width_cm": product.width_cm or "",
        "height_cm": product.height_cm or "",
        "weight_g": product.weight_g or "",
        "volume_cm3": product.volume_cm3 or "",
        "storage_conditions": product.storage_conditions or "",
        "perishable": "Oui" if product.perishable else "Non",
        "quarantine_default": "Oui" if product.quarantine_default else "Non",
        "notes": product.notes or "",
        "warehouse": location.warehouse.name if location else "",
        "zone": location.zone if location else "",
        "aisle": location.aisle if location else "",
        "shelf": location.shelf if location else "",
    }
