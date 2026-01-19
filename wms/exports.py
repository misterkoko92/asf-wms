import csv
import io

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.db.models import F, IntegerField, Sum
from django.db.models.expressions import ExpressionWrapper

from contacts.models import Contact

from .models import (
    Location,
    Product,
    ProductCategory,
    ProductLot,
    ProductLotStatus,
    RackColor,
    Warehouse,
)
from .product_display import category_levels


def _bool_to_csv(value):
    if value is None:
        return ""
    return "true" if value else "false"


def _build_csv_response(filename, header, rows):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(header)
    writer.writerows(rows)
    content = "\ufeff" + output.getvalue()
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_products_csv():
    header = [
        "sku",
        "nom",
        "marque",
        "couleur",
        "category_l1",
        "category_l2",
        "category_l3",
        "category_l4",
        "tags",
        "entrepot",
        "rack",
        "etagere",
        "bac",
        "rack_color",
        "barcode",
        "ean",
        "pu_ht",
        "tva",
        "pu_ttc",
        "length_cm",
        "width_cm",
        "height_cm",
        "weight_g",
        "volume_cm3",
        "quantity",
        "storage_conditions",
        "perishable",
        "quarantine_default",
        "notes",
        "photo",
    ]
    rack_colors = {
        (rack.warehouse_id, rack.zone): rack.color for rack in RackColor.objects.all()
    }
    available_expr = ExpressionWrapper(
        F("quantity_on_hand") - F("quantity_reserved"), output_field=IntegerField()
    )
    stock_totals = (
        ProductLot.objects.filter(status=ProductLotStatus.AVAILABLE)
        .values("product_id")
        .annotate(total=Sum(available_expr))
    )
    quantity_by_product = {
        row["product_id"]: max(0, row["total"] or 0) for row in stock_totals
    }
    rows = []
    products = (
        Product.objects.select_related(
            "category", "default_location", "default_location__warehouse"
        )
        .prefetch_related("tags")
        .all()
    )
    for product in products:
        cat_l1, cat_l2, cat_l3, cat_l4 = category_levels(product.category)
        tags = "|".join(sorted(tag.name for tag in product.tags.all()))
        location = product.default_location
        warehouse = location.warehouse.name if location else ""
        zone = location.zone if location else ""
        aisle = location.aisle if location else ""
        shelf = location.shelf if location else ""
        rack_color = ""
        if location:
            rack_color = rack_colors.get((location.warehouse_id, location.zone), "")
        quantity = quantity_by_product.get(product.id) or 0
        rows.append(
            [
                product.sku or "",
                product.name or "",
                product.brand or "",
                product.color or "",
                cat_l1,
                cat_l2,
                cat_l3,
                cat_l4,
                tags,
                warehouse,
                zone,
                aisle,
                shelf,
                rack_color,
                product.barcode or "",
                product.ean or "",
                product.pu_ht or "",
                product.tva or "",
                product.pu_ttc or "",
                product.length_cm or "",
                product.width_cm or "",
                product.height_cm or "",
                product.weight_g or "",
                product.volume_cm3 or "",
                quantity if quantity > 0 else "",
                product.storage_conditions or "",
                _bool_to_csv(product.perishable),
                _bool_to_csv(product.quarantine_default),
                product.notes or "",
                product.photo.name if product.photo else "",
            ]
        )
    return _build_csv_response("products_export.csv", header, rows)


def export_locations_csv():
    header = ["entrepot", "rack", "etagere", "bac", "notes", "rack_color"]
    rack_colors = {
        (rack.warehouse_id, rack.zone): rack.color for rack in RackColor.objects.all()
    }
    rows = []
    locations = Location.objects.select_related("warehouse").all()
    for location in locations:
        rack_color = rack_colors.get((location.warehouse_id, location.zone), "")
        rows.append(
            [
                location.warehouse.name,
                location.zone,
                location.aisle,
                location.shelf,
                location.notes or "",
                rack_color,
            ]
        )
    return _build_csv_response("locations_export.csv", header, rows)


def export_categories_csv():
    header = ["name", "parent"]
    rows = []
    for category in ProductCategory.objects.select_related("parent").all():
        rows.append([category.name, category.parent.name if category.parent else ""])
    return _build_csv_response("categories_export.csv", header, rows)


def export_warehouses_csv():
    header = ["name", "code"]
    rows = []
    for warehouse in Warehouse.objects.all():
        rows.append([warehouse.name, warehouse.code or ""])
    return _build_csv_response("warehouses_export.csv", header, rows)


def export_contacts_csv():
    header = [
        "contact_type",
        "title",
        "first_name",
        "last_name",
        "name",
        "organization",
        "role",
        "email",
        "email2",
        "phone",
        "phone2",
        "use_organization_address",
        "tags",
        "destination",
        "siret",
        "vat_number",
        "legal_registration_number",
        "asf_id",
        "address_label",
        "address_line1",
        "address_line2",
        "postal_code",
        "city",
        "region",
        "country",
        "address_phone",
        "address_email",
        "address_is_default",
        "notes",
    ]
    rows = []
    contacts = Contact.objects.select_related("organization", "destination").prefetch_related(
        "tags", "addresses"
    )
    for contact in contacts:
        tags = "|".join(sorted(tag.name for tag in contact.tags.all()))
        destination = str(contact.destination) if contact.destination else ""
        address_source = (
            contact.get_effective_addresses()
            if hasattr(contact, "get_effective_addresses")
            else contact.addresses.all()
        )
        addresses = list(address_source)
        if not addresses:
            rows.append(
                [
                    contact.contact_type,
                    contact.title or "",
                    contact.first_name or "",
                    contact.last_name or "",
                    contact.name,
                    contact.organization.name if contact.organization else "",
                    contact.role or "",
                    contact.email or "",
                    contact.email2 or "",
                    contact.phone or "",
                    contact.phone2 or "",
                    _bool_to_csv(contact.use_organization_address),
                    tags,
                    destination,
                    contact.siret or "",
                    contact.vat_number or "",
                    contact.legal_registration_number or "",
                    contact.asf_id or "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    contact.notes or "",
                ]
            )
            continue
        for address in addresses:
            rows.append(
                [
                    contact.contact_type,
                    contact.title or "",
                    contact.first_name or "",
                    contact.last_name or "",
                    contact.name,
                    contact.organization.name if contact.organization else "",
                    contact.role or "",
                    contact.email or "",
                    contact.email2 or "",
                    contact.phone or "",
                    contact.phone2 or "",
                    _bool_to_csv(contact.use_organization_address),
                    tags,
                    destination,
                    contact.siret or "",
                    contact.vat_number or "",
                    contact.legal_registration_number or "",
                    contact.asf_id or "",
                    address.label or "",
                    address.address_line1 or "",
                    address.address_line2 or "",
                    address.postal_code or "",
                    address.city or "",
                    address.region or "",
                    address.country or "",
                    address.phone or "",
                    address.email or "",
                    _bool_to_csv(address.is_default),
                    contact.notes or "",
                ]
            )
    return _build_csv_response("contacts_export.csv", header, rows)


def export_users_csv():
    header = [
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_superuser",
        "is_active",
        "password",
    ]
    rows = []
    User = get_user_model()
    for user in User.objects.all():
        rows.append(
            [
                user.username,
                user.email or "",
                user.first_name or "",
                user.last_name or "",
                _bool_to_csv(user.is_staff),
                _bool_to_csv(user.is_superuser),
                _bool_to_csv(user.is_active),
                "",
            ]
        )
    return _build_csv_response("users_export.csv", header, rows)


EXPORT_HANDLERS = {
    "products": export_products_csv,
    "locations": export_locations_csv,
    "categories": export_categories_csv,
    "warehouses": export_warehouses_csv,
    "contacts": export_contacts_csv,
    "users": export_users_csv,
}
