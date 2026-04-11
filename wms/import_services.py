"""Import services facade for legacy imports."""

from .import_services_categories import build_category_path, import_categories
from .import_services_common import _row_is_empty
from .import_services_contacts import import_contacts
from .import_services_destinations import _get_or_create_destination
from .import_services_locations import (
    get_or_create_location,
    import_locations,
    import_warehouses,
    resolve_listing_location,
)
from .import_services_pallet import apply_pallet_listing_import as _apply_pallet_listing_import
from .import_services_products import (
    DEFAULT_QUANTITY_MODE,
    QUANTITY_MODE_MOVEMENT,
    QUANTITY_MODE_OVERWRITE,
    attach_photo,
    compute_volume,
    extract_product_identity,
    find_product_matches,
    import_product_row,
    import_products_rows,
    import_products_single,
    normalize_quantity_mode,
    resolve_photo_path,
)
from .import_services_tags import build_product_tags
from .import_services_users import import_users


def apply_pallet_listing_import(*args, **kwargs):
    """Legacy facade kept at a 4-value tuple contract.

    New listing flows that need incomplete-product ids must import
    ``wms.import_services_pallet.apply_pallet_listing_import`` directly.
    """

    created, skipped, errors, receipt, _incomplete_product_ids = _apply_pallet_listing_import(
        *args,
        **kwargs,
    )
    return created, skipped, errors, receipt


__all__ = [
    "_row_is_empty",
    "build_category_path",
    "build_product_tags",
    "extract_product_identity",
    "find_product_matches",
    "DEFAULT_QUANTITY_MODE",
    "QUANTITY_MODE_MOVEMENT",
    "QUANTITY_MODE_OVERWRITE",
    "normalize_quantity_mode",
    "resolve_photo_path",
    "attach_photo",
    "compute_volume",
    "get_or_create_location",
    "resolve_listing_location",
    "import_product_row",
    "import_products_rows",
    "import_products_single",
    "apply_pallet_listing_import",
    "import_locations",
    "import_categories",
    "import_warehouses",
    "import_contacts",
    "import_users",
    "_get_or_create_destination",
]
