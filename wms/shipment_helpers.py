from .contact_filters import (
    TAG_CORRESPONDENT,
    TAG_RECIPIENT,
    TAG_SHIPPER,
    contacts_with_tags,
)
from .models import Destination
from .scan_helpers import parse_int, resolve_product


def _destination_ids(contact):
    return sorted(destination.id for destination in contact.destinations.all())


def _linked_shipper_ids(contact):
    return sorted(shipper.id for shipper in contact.linked_shippers.all())


def build_destination_label(destination):
    if not destination:
        return ""
    return str(destination)


def build_shipment_contact_payload():
    destinations = Destination.objects.filter(is_active=True).select_related(
        "correspondent_contact"
    )
    shipper_contacts = (
        contacts_with_tags(TAG_SHIPPER)
        .select_related("destination")
        .prefetch_related("destinations")
    )
    recipient_contacts = (
        contacts_with_tags(TAG_RECIPIENT)
        .select_related("destination")
        .prefetch_related("addresses", "destinations", "linked_shippers")
    )
    correspondent_contacts = (
        contacts_with_tags(TAG_CORRESPONDENT)
        .select_related("destination")
        .prefetch_related("destinations")
    )

    destinations_json = [
        {
            "id": destination.id,
            "country": destination.country,
            "correspondent_contact_id": destination.correspondent_contact_id,
        }
        for destination in destinations
    ]
    shipper_contacts_json = [
        {
            "id": contact.id,
            "name": contact.name,
            "destination_id": contact.destination_id,
            "destination_ids": _destination_ids(contact),
        }
        for contact in shipper_contacts
    ]
    recipient_contacts_json = []
    for contact in recipient_contacts:
        address_source = (
            contact.get_effective_addresses()
            if hasattr(contact, "get_effective_addresses")
            else contact.addresses.all()
        )
        countries = {address.country for address in address_source if address.country}
        recipient_contacts_json.append(
            {
                "id": contact.id,
                "name": contact.name,
                "countries": sorted(countries),
                "destination_id": contact.destination_id,
                "destination_ids": _destination_ids(contact),
                "linked_shipper_ids": _linked_shipper_ids(contact),
            }
        )
    correspondent_contacts_json = [
        {
            "id": contact.id,
            "name": contact.name,
            "destination_id": contact.destination_id,
            "destination_ids": _destination_ids(contact),
        }
        for contact in correspondent_contacts
    ]
    return (
        destinations_json,
        shipper_contacts_json,
        recipient_contacts_json,
        correspondent_contacts_json,
    )


def parse_shipment_lines(*, carton_count, data, allowed_carton_ids):
    line_values = []
    line_errors = {}
    line_items = []
    for index in range(1, carton_count + 1):
        prefix = f"line_{index}_"
        carton_id = (data.get(prefix + "carton_id") or "").strip()
        product_code = (data.get(prefix + "product_code") or "").strip()
        quantity_raw = (data.get(prefix + "quantity") or "").strip()
        line_values.append(
            {
                "carton_id": carton_id,
                "product_code": product_code,
                "quantity": quantity_raw,
            }
        )
        errors = []

        if carton_id and (product_code or quantity_raw):
            errors.append("Choisissez un carton OU créez un colis depuis un produit.")
        elif carton_id:
            if carton_id not in allowed_carton_ids:
                errors.append("Carton indisponible.")
            else:
                line_items.append({"carton_id": int(carton_id)})
        elif product_code or quantity_raw:
            if not product_code:
                errors.append("Produit requis.")
            quantity = None
            if not quantity_raw:
                errors.append("Quantité requise.")
            else:
                quantity = parse_int(quantity_raw)
                if quantity is None or quantity <= 0:
                    errors.append("Quantité invalide.")
            product = resolve_product(product_code) if product_code else None
            if product_code and not product:
                errors.append("Produit introuvable.")
            if not errors and product and quantity:
                line_items.append({"product": product, "quantity": quantity})
        else:
            errors.append("Renseignez un carton ou un produit.")

        if errors:
            line_errors[str(index)] = errors
    return line_values, line_items, line_errors
