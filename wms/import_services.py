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
from .import_services_pallet import apply_pallet_listing_import
from .import_services_products import (
    attach_photo,
    compute_volume,
    extract_product_identity,
    find_product_matches,
    import_product_row,
    import_products_rows,
    import_products_single,
    resolve_photo_path,
)
from .import_services_tags import build_contact_tags, build_product_tags
from .import_services_users import import_users

__all__ = [
    "_row_is_empty",
    "build_category_path",
    "build_product_tags",
    "build_contact_tags",
    "extract_product_identity",
    "find_product_matches",
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
