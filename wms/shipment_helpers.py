from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _

from .contact_labels import build_contact_select_label
from .models import (
    Destination,
    OrganizationRole,
    RecipientBinding,
    ShipperScope,
)
from .scan_helpers import parse_int, resolve_product
from .shipment_party_rules import (
    active_recipient_contacts,
    active_shipper_contacts,
    normalize_party_contact_to_org,
)


def _contact_organization_id(contact):
    organization = normalize_party_contact_to_org(contact)
    return organization.id if organization else None


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


def _build_shipper_destination_ids_by_org(*, destination_ids):
    rows = (
        ShipperScope.objects.filter(
            role_assignment__role=OrganizationRole.SHIPPER,
            role_assignment__is_active=True,
            role_assignment__organization__is_active=True,
            is_active=True,
        )
        .filter(_current_window_q())
        .values_list(
            "role_assignment__organization_id",
            "all_destinations",
            "destination_id",
        )
    )

    allowed_destination_ids_by_org = {}
    for organization_id, all_destinations, destination_id in rows:
        allowed_destination_ids_by_org.setdefault(organization_id, set())
        if all_destinations:
            allowed_destination_ids_by_org[organization_id].update(destination_ids)
            continue
        if destination_id:
            allowed_destination_ids_by_org[organization_id].add(destination_id)

    return {
        organization_id: sorted(allowed_destination_ids)
        for organization_id, allowed_destination_ids in allowed_destination_ids_by_org.items()
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
    shipper_contacts = active_shipper_contacts().select_related("organization")
    recipient_contacts = (
        active_recipient_contacts().select_related("organization").prefetch_related("addresses")
    )
    shipper_scope_destination_ids_by_org = _build_shipper_scope_destination_ids_by_org()
    shipper_destination_ids_by_org = _build_shipper_destination_ids_by_org(
        destination_ids=[destination.id for destination in destinations]
    )
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
            "organization_id": _contact_organization_id(contact) or contact.id,
            "destination_id": (
                allowed_destination_ids[0] if len(allowed_destination_ids) == 1 else None
            ),
            "destination_ids": allowed_destination_ids,
            "scoped_destination_ids": shipper_scope_destination_ids_by_org.get(
                _contact_organization_id(contact) or contact.id,
                [],
            ),
        }
        for contact in shipper_contacts
        for allowed_destination_ids in [
            shipper_destination_ids_by_org.get(_contact_organization_id(contact) or contact.id, [])
        ]
    ]
    recipient_contacts_json = []
    for contact in recipient_contacts:
        address_source = (
            contact.get_effective_addresses()
            if hasattr(contact, "get_effective_addresses")
            else contact.addresses.all()
        )
        countries = {address.country for address in address_source if address.country}
        organization_id = _contact_organization_id(contact) or contact.id
        binding_pairs = recipient_binding_pairs_by_org.get(organization_id, [])
        destination_ids = sorted(
            {pair["destination_id"] for pair in binding_pairs if pair["destination_id"] is not None}
        )
        linked_shipper_ids = sorted(
            {pair["shipper_id"] for pair in binding_pairs if pair["shipper_id"] is not None}
        )
        recipient_contacts_json.append(
            {
                "id": contact.id,
                "name": build_contact_select_label(contact),
                "organization_id": organization_id,
                "countries": sorted(countries),
                "destination_id": destination_ids[0] if len(destination_ids) == 1 else None,
                "destination_ids": destination_ids,
                "linked_shipper_ids": linked_shipper_ids,
                "binding_pairs": binding_pairs,
            }
        )
    correspondent_destination_ids_by_contact = {}
    for destination in destinations:
        if not destination.correspondent_contact_id:
            continue
        correspondent_destination_ids_by_contact.setdefault(
            destination.correspondent_contact_id, set()
        ).add(destination.id)
    destination_correspondents = [
        destination.correspondent_contact
        for destination in destinations
        if destination.correspondent_contact_id
    ]
    correspondent_contacts_by_id = {
        contact.id: contact for contact in destination_correspondents if contact
    }
    correspondent_contacts_json = [
        {
            "id": contact.id,
            "name": contact.name,
            "destination_id": (
                sorted(correspondent_destination_ids_by_contact.get(contact.id, []))[0]
                if len(correspondent_destination_ids_by_contact.get(contact.id, [])) == 1
                else None
            ),
            "destination_ids": sorted(
                correspondent_destination_ids_by_contact.get(contact.id, set())
            ),
        }
        for contact in correspondent_contacts_by_id.values()
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
        expires_on_raw = (data.get(prefix + "expires_on") or "").strip()
        preassigned_destination_confirmed = (
            data.get(prefix + "preassigned_destination_confirmed") or ""
        ).strip() == "1"
        line_values.append(
            {
                "carton_id": carton_id,
                "product_code": product_code,
                "quantity": quantity_raw,
                "expires_on": expires_on_raw,
            }
        )
        errors = []

        if carton_id and (product_code or quantity_raw or expires_on_raw):
            errors.append(_("Choisissez un carton OU créez un colis depuis un produit."))
        elif carton_id:
            if carton_id not in allowed_carton_ids:
                errors.append(_("Carton indisponible."))
            else:
                line_items.append(
                    {
                        "carton_id": int(carton_id),
                        "preassigned_destination_confirmed": preassigned_destination_confirmed,
                    }
                )
        elif product_code or quantity_raw or expires_on_raw:
            if not product_code:
                errors.append(_("Produit requis."))
            quantity = None
            expires_on = None
            if not quantity_raw:
                errors.append(_("Quantité requise."))
            else:
                quantity = parse_int(quantity_raw)
                if quantity is None or quantity <= 0:
                    errors.append(_("Quantité invalide."))
            if expires_on_raw:
                expires_on = parse_date(expires_on_raw)
                if expires_on is None:
                    errors.append(_("Date de péremption invalide."))
            product = resolve_product(product_code) if product_code else None
            if product_code and not product:
                errors.append(_("Produit introuvable."))
            if not errors and product and quantity:
                line_items.append(
                    {"product": product, "quantity": quantity, "expires_on": expires_on}
                )
        else:
            errors.append(_("Renseignez un carton ou un produit."))

        if errors:
            line_errors[str(index)] = errors
    return line_values, line_items, line_errors
