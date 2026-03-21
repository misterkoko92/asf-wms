from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _

from contacts.models import Contact

from .contact_labels import (
    build_contact_select_label,
    build_shipment_recipient_select_label,
)
from .models import (
    Destination,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from .scan_helpers import parse_int, resolve_product
from .shipment_party_registry import (
    eligible_shippers_for_stopover,
    stopover_correspondent_recipient_organization,
)
from .shipment_party_rules import normalize_party_contact_to_org


def _contact_organization_id(contact):
    organization = normalize_party_contact_to_org(contact)
    return organization.id if organization else None


def _is_priority_shipper_name(name):
    return (name or "").strip().casefold() == "aviation sans frontieres"


def _validated_active_shipper_queryset():
    return ShipmentShipper.objects.filter(
        is_active=True,
        validation_status=ShipmentValidationStatus.VALIDATED,
        organization__is_active=True,
        default_contact__is_active=True,
    ).select_related("organization", "default_contact", "default_contact__organization")


def _validated_active_recipient_link_queryset():
    return ShipmentShipperRecipientLink.objects.filter(
        is_active=True,
        shipper__is_active=True,
        shipper__validation_status=ShipmentValidationStatus.VALIDATED,
        shipper__organization__is_active=True,
        shipper__default_contact__is_active=True,
        recipient_organization__is_active=True,
        recipient_organization__validation_status=ShipmentValidationStatus.VALIDATED,
        recipient_organization__organization__is_active=True,
        recipient_organization__destination__is_active=True,
    ).select_related(
        "shipper",
        "shipper__organization",
        "shipper__default_contact",
        "shipper__default_contact__organization",
        "recipient_organization",
        "recipient_organization__organization",
        "recipient_organization__destination",
    )


def eligible_shipment_shipper_contacts_for_destination(destination):
    if destination is None or not destination.is_active:
        return Contact.objects.none()
    contact_ids = eligible_shippers_for_stopover(destination).values_list(
        "default_contact_id", flat=True
    )
    return Contact.objects.filter(
        id__in=contact_ids,
        is_active=True,
    ).select_related("organization")


def active_shipment_shipper_organizations():
    organization_ids = _validated_active_shipper_queryset().values_list(
        "organization_id", flat=True
    )
    return Contact.objects.filter(
        id__in=organization_ids,
        is_active=True,
    ).order_by("name")


def shipment_shipper_from_contact(contact):
    if contact is None or not getattr(contact, "pk", None) or not contact.is_active:
        return None

    queryset = _validated_active_shipper_queryset()
    shipper = queryset.filter(default_contact=contact).first()
    if shipper is not None:
        return shipper
    if getattr(contact, "contact_type", "") == "organization":
        return queryset.filter(organization=contact).first()
    return None


def eligible_shipment_recipient_links_for_shipper(*, shipper, destination):
    if shipper is None or destination is None or not destination.is_active:
        return ShipmentShipperRecipientLink.objects.none()

    shipper_is_valid = _validated_active_shipper_queryset().filter(pk=shipper.pk).exists()
    if not shipper_is_valid:
        return ShipmentShipperRecipientLink.objects.none()

    return _validated_active_recipient_link_queryset().filter(
        shipper=shipper,
        recipient_organization__destination=destination,
    )


def eligible_shipment_recipient_contacts_for_shipper(*, shipper, destination):
    link_ids = eligible_shipment_recipient_links_for_shipper(
        shipper=shipper,
        destination=destination,
    ).values_list("id", flat=True)
    if not link_ids:
        return Contact.objects.none()
    return (
        Contact.objects.filter(
            shipment_recipient_contacts__authorized_links__link_id__in=link_ids,
            shipment_recipient_contacts__authorized_links__is_active=True,
            shipment_recipient_contacts__is_active=True,
            is_active=True,
        )
        .select_related("organization")
        .distinct()
    )


def shipment_link_for_recipient_contact(*, shipper, recipient_contact, destination):
    if shipper is None or recipient_contact is None or destination is None:
        return None
    return (
        eligible_shipment_recipient_links_for_shipper(
            shipper=shipper,
            destination=destination,
        )
        .filter(
            authorized_recipient_contacts__is_active=True,
            authorized_recipient_contacts__recipient_contact__is_active=True,
            authorized_recipient_contacts__recipient_contact__contact=recipient_contact,
            authorized_recipient_contacts__recipient_contact__contact__is_active=True,
        )
        .distinct()
        .first()
    )


def default_shipment_recipient_contact_for_shipper(*, shipper, destination):
    default_contacts = []
    seen_contact_ids = set()
    for link in eligible_shipment_recipient_links_for_shipper(
        shipper=shipper, destination=destination
    ):
        default_authorization = (
            ShipmentAuthorizedRecipientContact.objects.filter(
                link=link,
                is_default=True,
                is_active=True,
                recipient_contact__is_active=True,
                recipient_contact__contact__is_active=True,
            )
            .select_related("recipient_contact__contact")
            .first()
        )
        if default_authorization is None:
            continue
        contact = default_authorization.recipient_contact.contact
        if contact.id in seen_contact_ids:
            continue
        seen_contact_ids.add(contact.id)
        default_contacts.append(contact)
    if len(default_contacts) == 1:
        return default_contacts[0]
    return None


def shipment_correspondent_contact_for_destination(destination):
    if destination is None or not destination.is_active:
        return None

    recipient_organization = stopover_correspondent_recipient_organization(destination)
    if recipient_organization is None:
        return None

    correspondent_contact = getattr(destination, "correspondent_contact", None)
    if correspondent_contact is None and getattr(destination, "correspondent_contact_id", None):
        correspondent_contact = (
            Contact.objects.filter(pk=destination.correspondent_contact_id)
            .select_related("organization")
            .first()
        )
    if correspondent_contact is None or not correspondent_contact.is_active:
        return None

    correspondent_organization = normalize_party_contact_to_org(correspondent_contact)
    if correspondent_organization is None:
        return None
    if correspondent_organization.id != recipient_organization.organization_id:
        return None
    return correspondent_contact


def build_destination_label(destination):
    if not destination:
        return ""
    return str(destination)


def build_shipment_contact_payload():
    destinations = list(
        Destination.objects.filter(is_active=True)
        .select_related("correspondent_contact")
        .order_by("city", "iata_code", "id")
    )
    active_destination_ids = [destination.id for destination in destinations]
    shippers = list(_validated_active_shipper_queryset())
    recipient_links = list(
        _validated_active_recipient_link_queryset().prefetch_related(
            "authorized_recipient_contacts__recipient_contact__contact",
            "authorized_recipient_contacts__recipient_contact__recipient_organization__organization__addresses",
        )
    )

    destinations_json = [
        {
            "id": destination.id,
            "label": build_destination_label(destination),
            "city": destination.city,
            "iata_code": destination.iata_code,
            "country": destination.country,
            "correspondent_contact_id": (
                shipment_correspondent_contact_for_destination(destination).id
                if shipment_correspondent_contact_for_destination(destination)
                else None
            ),
        }
        for destination in destinations
    ]
    shipper_contacts_json = []
    for shipper in shippers:
        contact = shipper.default_contact
        if contact is None:
            continue
        if shipper.can_send_to_all:
            allowed_destination_ids = list(active_destination_ids)
        else:
            allowed_destination_ids = sorted(
                {
                    link.recipient_organization.destination_id
                    for link in recipient_links
                    if link.shipper_id == shipper.id
                }
            )
        shipper_contacts_json.append(
            {
                "id": contact.id,
                "name": build_contact_select_label(contact),
                "is_priority_shipper": _is_priority_shipper_name(shipper.organization.name),
                "organization_id": shipper.organization_id,
                "default_destination_id": (
                    allowed_destination_ids[0] if len(allowed_destination_ids) == 1 else None
                ),
                "allowed_destination_ids": allowed_destination_ids,
                "scope_destination_ids": allowed_destination_ids,
            }
        )

    recipient_entries_by_contact_id = {}
    for link in recipient_links:
        authorized_links = getattr(link, "authorized_recipient_contacts", None)
        if authorized_links is None:
            continue
        for authorization in authorized_links.all():
            if not authorization.is_active:
                continue
            recipient_contact = authorization.recipient_contact
            if recipient_contact is None or not recipient_contact.is_active:
                continue
            contact = getattr(recipient_contact, "contact", None)
            if contact is None or not contact.is_active:
                continue
            organization = getattr(recipient_contact.recipient_organization, "organization", None)
            address_source = (
                organization.get_effective_addresses()
                if organization is not None and hasattr(organization, "get_effective_addresses")
                else organization.addresses.all()
                if organization is not None
                else []
            )
            countries = {
                address.country for address in address_source if getattr(address, "country", "")
            }
            entry = recipient_entries_by_contact_id.setdefault(
                contact.id,
                {
                    "id": contact.id,
                    "name": build_shipment_recipient_select_label(
                        contact,
                        destination=link.recipient_organization.destination,
                    ),
                    "organization_id": recipient_contact.recipient_organization.organization_id,
                    "countries": set(countries),
                    "allowed_destination_ids": set(),
                    "bound_shipper_ids": set(),
                    "binding_pairs": set(),
                },
            )
            entry["countries"].update(countries)
            entry["allowed_destination_ids"].add(link.recipient_organization.destination_id)
            entry["bound_shipper_ids"].add(link.shipper.organization_id)
            entry["binding_pairs"].add(
                (link.shipper.organization_id, link.recipient_organization.destination_id)
            )

    recipient_contacts_json = []
    for entry in recipient_entries_by_contact_id.values():
        destination_ids = sorted(entry["allowed_destination_ids"])
        recipient_contacts_json.append(
            {
                "id": entry["id"],
                "name": entry["name"],
                "organization_id": entry["organization_id"],
                "countries": sorted(entry["countries"]),
                "default_destination_id": (
                    destination_ids[0] if len(destination_ids) == 1 else None
                ),
                "allowed_destination_ids": destination_ids,
                "bound_shipper_ids": sorted(entry["bound_shipper_ids"]),
                "binding_pairs": [
                    {"shipper_id": shipper_id, "destination_id": destination_id}
                    for shipper_id, destination_id in sorted(entry["binding_pairs"])
                ],
            }
        )

    correspondent_destination_ids_by_contact = {}
    correspondent_recipient_labels_by_contact = {}
    correspondent_contacts_by_id = {}
    for destination in destinations:
        correspondent_contact = shipment_correspondent_contact_for_destination(destination)
        if correspondent_contact is None:
            continue
        correspondent_destination_ids_by_contact.setdefault(correspondent_contact.id, set()).add(
            destination.id
        )
        correspondent_recipient_labels_by_contact.setdefault(
            correspondent_contact.id,
            {},
        )[str(destination.id)] = build_shipment_recipient_select_label(
            correspondent_contact,
            destination=destination,
        )
        correspondent_contacts_by_id[correspondent_contact.id] = correspondent_contact

    correspondent_contacts_json = [
        {
            "id": contact.id,
            "name": contact.name,
            "default_destination_id": (
                sorted(correspondent_destination_ids_by_contact.get(contact.id, []))[0]
                if len(correspondent_destination_ids_by_contact.get(contact.id, [])) == 1
                else None
            ),
            "covered_destination_ids": sorted(
                correspondent_destination_ids_by_contact.get(contact.id, set())
            ),
            "recipient_labels_by_destination_id": dict(
                sorted(
                    correspondent_recipient_labels_by_contact.get(contact.id, {}).items(),
                    key=lambda item: int(item[0]),
                )
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
