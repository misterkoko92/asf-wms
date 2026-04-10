from .models import ProductCategory

CATEGORY_FILTER_MAX_LEVELS = 4


def build_category_path_ids(category):
    path = []
    current = category
    visited_ids = set()
    while current is not None:
        current_id = getattr(current, "id", None)
        if current_id is None or current_id in visited_ids:
            break
        visited_ids.add(current_id)
        path.append(str(current_id))
        current = getattr(current, "parent", None)
    path.reverse()
    return path[-CATEGORY_FILTER_MAX_LEVELS:]


def build_category_filter_context(*, selected_category_id):
    categories = list(
        ProductCategory.objects.select_related(
            "parent",
            "parent__parent",
            "parent__parent__parent",
        ).order_by("name", "id")
    )
    category_labels_by_id = {}
    category_paths_by_id = {}
    for category in categories:
        category_id = str(category.id)
        category_labels_by_id[category_id] = category.name
        category_paths_by_id[category_id] = build_category_path_ids(category)

    selected_category_key = str(selected_category_id or "").strip()
    selected_category_path = category_paths_by_id.get(selected_category_key, [])
    descendant_category_ids = [
        int(category_id)
        for category_id, path in category_paths_by_id.items()
        if selected_category_path and path[: len(selected_category_path)] == selected_category_path
    ]
    category_filter_max_depth = min(
        max((len(path) for path in category_paths_by_id.values()), default=0),
        CATEGORY_FILTER_MAX_LEVELS,
    )
    return {
        "categories": categories,
        "category_labels_by_id": category_labels_by_id,
        "category_paths_by_id": category_paths_by_id,
        "category_filter_max_depth": category_filter_max_depth,
        "selected_category_path": selected_category_path,
        "descendant_category_ids": descendant_category_ids,
    }
