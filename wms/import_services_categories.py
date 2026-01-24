import re

from .import_services_common import _row_is_empty
from .import_utils import get_value, parse_str
from .models import ProductCategory
from .text_utils import normalize_category_name

def build_category_path(parts):
    parent = None
    for name in parts:
        if not name:
            continue
        normalized = normalize_category_name(name, is_root=parent is None)
        category, _ = ProductCategory.objects.get_or_create(
            name=normalized, parent=parent
        )
        parent = category
    return parent


def import_categories(rows):
    created = 0
    updated = 0
    errors = []
    for index, row in enumerate(rows, start=2):
        if _row_is_empty(row):
            continue
        try:
            path = parse_str(get_value(row, "path", "chemin"))
            if path:
                parts = [p.strip() for p in re.split(r"[>/]", path) if p.strip()]
                if not parts:
                    raise ValueError("Chemin categorie vide.")
                build_category_path(parts)
                created += 1
                continue
            name = parse_str(get_value(row, "name", "categorie", "category"))
            parent_name = parse_str(get_value(row, "parent", "parent_name"))
            if not name:
                raise ValueError("Nom categorie requis.")
            name = normalize_category_name(name, is_root=parent_name is None)
            parent = None
            if parent_name:
                parent_name = normalize_category_name(parent_name, is_root=True)
                parent, _ = ProductCategory.objects.get_or_create(
                    name=parent_name, parent=None
                )
            ProductCategory.objects.get_or_create(name=name, parent=parent)
            created += 1
        except ValueError as exc:
            errors.append(f"Ligne {index}: {exc}")
    return created, updated, errors
