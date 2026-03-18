import csv
import io

from django.contrib.auth import get_user_model
from django.db.models import F, IntegerField, Q, Sum
from django.db.models.expressions import ExpressionWrapper
from django.http import HttpResponse
from django.utils import timezone

from contacts.models import Contact

from .models import (
    Destination,
    Location,
    Product,
    ProductCategory,
    ProductLot,
    ProductLotStatus,
    RackColor,
    RecipientBinding,
    ShipperScope,
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


def _current_window_q(prefix: str = ""):
    now = timezone.now()
    return Q(**{f"{prefix}valid_from__lte": now}) & (
        Q(**{f"{prefix}valid_to__isnull": True}) | Q(**{f"{prefix}valid_to__gt": now})
    )


def _build_contact_role_scope_maps(contact_ids):
    if not contact_ids:
        return {}, (set(), {})

    destination_ids_by_contact_id = {contact_id: set() for contact_id in contact_ids}
    global_scope_contact_ids = set()

    correspondent_rows = Destination.objects.filter(
        is_active=True,
        correspondent_contact_id__in=contact_ids,
    ).values_list("correspondent_contact_id", "id")
    for contact_id, destination_id in correspondent_rows:
        destination_ids_by_contact_id.setdefault(contact_id, set()).add(destination_id)

    shipper_scope_rows = (
        ShipperScope.objects.filter(
            role_assignment__organization_id__in=contact_ids,
            is_active=True,
        )
        .filter(_current_window_q())
        .values_list("role_assignment__organization_id", "all_destinations", "destination_id")
    )
    for contact_id, all_destinations, destination_id in shipper_scope_rows:
        if all_destinations:
            global_scope_contact_ids.add(contact_id)
            continue
        if destination_id:
            destination_ids_by_contact_id.setdefault(contact_id, set()).add(destination_id)

    recipient_binding_rows = (
        RecipientBinding.objects.filter(
            recipient_org_id__in=contact_ids,
            is_active=True,
        )
        .filter(_current_window_q())
        .values_list("recipient_org_id", "destination_id")
    )
    for contact_id, destination_id in recipient_binding_rows:
        if destination_id:
            destination_ids_by_contact_id.setdefault(contact_id, set()).add(destination_id)

    referenced_destination_ids = {
        destination_id
        for destination_ids in destination_ids_by_contact_id.values()
        for destination_id in destination_ids
    }
    destination_labels_by_id = {
        destination.id: str(destination)
        for destination in Destination.objects.filter(pk__in=referenced_destination_ids)
    }
    return (
        destination_ids_by_contact_id,
        (global_scope_contact_ids, destination_labels_by_id),
    )


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
    rack_colors = {(rack.warehouse_id, rack.zone): rack.color for rack in RackColor.objects.all()}
    available_expr = ExpressionWrapper(
        F("quantity_on_hand") - F("quantity_reserved"), output_field=IntegerField()
    )
    stock_totals = (
        ProductLot.objects.filter(status=ProductLotStatus.AVAILABLE)
        .values("product_id")
        .annotate(total=Sum(available_expr))
    )
    quantity_by_product = {row["product_id"]: max(0, row["total"] or 0) for row in stock_totals}
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
    rack_colors = {(rack.warehouse_id, rack.zone): rack.color for rack in RackColor.objects.all()}
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
        "is_active",
        "use_organization_address",
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
        "address_notes",
        "notes",
    ]
    rows = []
    contacts = list(Contact.objects.select_related("organization").prefetch_related("addresses"))
    destination_ids_by_contact_id, scope_maps = _build_contact_role_scope_maps(
        [contact.id for contact in contacts if getattr(contact, "id", None)]
    )
    global_scope_contact_ids, destination_labels_by_id = scope_maps
    for contact in contacts:
        contact_id = getattr(contact, "id", None)
        if contact_id in global_scope_contact_ids:
            destination_labels = ["GLOBAL"]
        else:
            destination_ids = sorted(
                destination_ids_by_contact_id.get(contact_id, set()),
                key=lambda destination_id: destination_labels_by_id.get(destination_id, ""),
            )
            destination_labels = [
                destination_labels_by_id[destination_id]
                for destination_id in destination_ids
                if destination_id in destination_labels_by_id
            ]
        destination = (
            destination_labels[0]
            if len(destination_labels) == 1 and destination_labels[0] != "GLOBAL"
            else ""
        )
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
                    _bool_to_csv(contact.is_active),
                    _bool_to_csv(contact.use_organization_address),
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
                    _bool_to_csv(contact.is_active),
                    _bool_to_csv(contact.use_organization_address),
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
                    address.notes or "",
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
