from django.db.models import Q
from django.utils import timezone

from contacts.destination_scope import (
    contact_destination_ids,
    contact_primary_destination_id,
)
from contacts.models import ContactType

from .contact_filters import (
    TAG_CORRESPONDENT,
    TAG_RECIPIENT,
    TAG_SHIPPER,
    contacts_with_tags,
    filter_structure_contacts,
)
from .contact_labels import build_contact_select_label
from .models import (
    Destination,
    OrganizationRole,
    RecipientBinding,
    ShipperScope,
)
from .scan_helpers import parse_int, resolve_product


def _destination_ids(contact):
    return contact_destination_ids(contact)


def _primary_destination_id(contact):
    return contact_primary_destination_id(contact)


def _linked_shipper_ids(contact):
    return sorted(shipper.id for shipper in contact.linked_shippers.all())


def _contact_organization_id(contact):
    if contact.contact_type == ContactType.ORGANIZATION:
        return contact.id
    return contact.organization_id


def _current_window_q(prefix=""):
    now = timezone.now()
    return Q(**{f"{prefix}valid_from__lte": now}) & (
        Q(**{f"{prefix}valid_to__isnull": True}) | Q(**{f"{prefix}valid_to__gt": now})
    )


def _build_shipper_scope_destination_ids_by_org():
    rows = (
        ShipperScope.objects.filter(
            role_assignment__role=OrganizationRole.SHIPPER,
            role_assignment__is_active=True,
            role_assignment__organization__is_active=True,
            is_active=True,
            all_destinations=False,
        )
        .filter(_current_window_q())
        .values_list(
            "role_assignment__organization_id",
            "destination_id",
        )
    )

    scoped_destination_ids_by_org = {}
    for organization_id, destination_id in rows:
        scoped_destination_ids_by_org.setdefault(organization_id, set()).add(destination_id)
    return {
        organization_id: sorted(destination_ids)
        for organization_id, destination_ids in scoped_destination_ids_by_org.items()
    }


def _build_recipient_binding_pairs_by_org():
    rows = (
        RecipientBinding.objects.filter(
            is_active=True,
            shipper_org__is_active=True,
            recipient_org__is_active=True,
        )
        .filter(_current_window_q())
        .values_list(
            "recipient_org_id",
            "shipper_org_id",
            "destination_id",
        )
    )

    binding_pairs_by_org = {}
    for recipient_org_id, shipper_org_id, destination_id in rows:
        binding_pairs_by_org.setdefault(recipient_org_id, set()).add(
            (shipper_org_id, destination_id)
        )

    return {
        recipient_org_id: [
            {
                "shipper_id": shipper_org_id,
                "destination_id": destination_id,
            }
            for shipper_org_id, destination_id in sorted(binding_pairs)
        ]
        for recipient_org_id, binding_pairs in binding_pairs_by_org.items()
    }


def build_destination_label(destination):
    if not destination:
        return ""
    return str(destination)


def build_shipment_contact_payload():
    destinations = Destination.objects.filter(is_active=True).select_related(
        "correspondent_contact"
    )
    shipper_contacts = (
        filter_structure_contacts(contacts_with_tags(TAG_SHIPPER))
        .select_related("organization")
        .prefetch_related("destinations")
    )
    recipient_contacts = (
        filter_structure_contacts(contacts_with_tags(TAG_RECIPIENT))
        .select_related("organization")
        .prefetch_related("addresses", "destinations", "linked_shippers")
    )
    correspondent_contacts = contacts_with_tags(TAG_CORRESPONDENT).prefetch_related("destinations")
    shipper_scope_destination_ids_by_org = _build_shipper_scope_destination_ids_by_org()
    recipient_binding_pairs_by_org = _build_recipient_binding_pairs_by_org()

    destinations_json = [
        {
            "id": destination.id,
            "label": build_destination_label(destination),
            "city": destination.city,
            "iata_code": destination.iata_code,
            "country": destination.country,
            "correspondent_contact_id": destination.correspondent_contact_id,
        }
        for destination in destinations
    ]
    shipper_contacts_json = [
        {
            "id": contact.id,
            "name": build_contact_select_label(contact),
            "destination_id": _primary_destination_id(contact),
            "destination_ids": _destination_ids(contact),
            "scoped_destination_ids": shipper_scope_destination_ids_by_org.get(
                _contact_organization_id(contact) or contact.id,
                [],
            ),
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
                "name": build_contact_select_label(contact),
                "countries": sorted(countries),
                "destination_id": _primary_destination_id(contact),
                "destination_ids": _destination_ids(contact),
                "linked_shipper_ids": _linked_shipper_ids(contact),
                "binding_pairs": recipient_binding_pairs_by_org.get(
                    _contact_organization_id(contact) or contact.id,
                    [],
                ),
            }
        )
    correspondent_contacts_json = [
        {
            "id": contact.id,
            "name": contact.name,
            "destination_id": _primary_destination_id(contact),
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
