from __future__ import annotations

from django.db import transaction
from django.utils.translation import gettext as _

from contacts.models import Contact, ContactType

from .forms_scan_admin_contacts_cockpit import (
    ShipmentAuthorizedRecipientDefaultForm,
    ShipmentRecipientOrganizationActionForm,
    ShipmentRecipientOrganizationMergeForm,
)
from .models import (
    Destination,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
)

ACTION_SET_DEFAULT_AUTHORIZED_RECIPIENT_CONTACT = "set_default_authorized_recipient_contact"
ACTION_SET_STOPOVER_CORRESPONDENT_RECIPIENT_ORGANIZATION = (
    "set_stopover_correspondent_recipient_organization"
)
ACTION_MERGE_SHIPMENT_RECIPIENT_ORGANIZATIONS = "merge_shipment_recipient_organizations"


def parse_cockpit_filters(*, role: str = "", shipper_org_id: str = "") -> dict:
    return {}


def set_default_authorized_recipient_contact(*, data) -> tuple[bool, str]:
    form = ShipmentAuthorizedRecipientDefaultForm(data)
    if not form.is_valid():
        return False, _("Donnees de referent autorise invalides.")

    link = (
        ShipmentShipperRecipientLink.objects.select_related("recipient_organization")
        .filter(pk=form.cleaned_data["link_id"])
        .first()
    )
    if link is None:
        return False, _("Lien expediteur destinataire introuvable.")

    authorization = (
        ShipmentAuthorizedRecipientContact.objects.select_related("recipient_contact")
        .filter(
            link=link,
            recipient_contact_id=form.cleaned_data["recipient_contact_id"],
        )
        .first()
    )
    if authorization is None:
        return False, _("Referent autorise introuvable.")
    if authorization.recipient_contact.recipient_organization_id != link.recipient_organization_id:
        return False, _("Le referent autorise doit appartenir a la structure liee.")

    with transaction.atomic():
        ShipmentAuthorizedRecipientContact.objects.filter(
            link=link,
            is_default=True,
        ).exclude(pk=authorization.pk).update(is_default=False)
        if not authorization.is_active:
            authorization.is_active = True
        authorization.is_default = True
        authorization.save(update_fields=["is_active", "is_default"])

    return True, _("Referent destinataire par defaut mis a jour.")


def set_stopover_correspondent_recipient_organization(*, data) -> tuple[bool, str]:
    form = ShipmentRecipientOrganizationActionForm(data)
    if not form.is_valid():
        return False, _("Donnees de correspondant invalides.")

    recipient_organization = (
        ShipmentRecipientOrganization.objects.select_related("destination", "organization")
        .filter(pk=form.cleaned_data["recipient_organization_id"])
        .first()
    )
    if recipient_organization is None:
        return False, _("Structure destinataire introuvable.")
    if not recipient_organization.is_active:
        return False, _("La structure destinataire doit etre active.")

    destination = recipient_organization.destination
    replacement_contact = (
        ShipmentRecipientContact.objects.filter(
            recipient_organization=recipient_organization,
            is_active=True,
            contact__is_active=True,
        )
        .select_related("contact")
        .order_by("id")
        .first()
    )

    with transaction.atomic():
        ShipmentRecipientOrganization.objects.filter(
            destination=destination,
            is_correspondent=True,
        ).exclude(pk=recipient_organization.pk).update(is_correspondent=False)
        if not recipient_organization.is_correspondent:
            recipient_organization.is_correspondent = True
            recipient_organization.save(update_fields=["is_correspondent"])

        destination.correspondent_contact = (
            replacement_contact.contact
            if replacement_contact is not None
            else recipient_organization.organization
        )
        destination.save(update_fields=["correspondent_contact"])

    return True, _("Correspondant d'escale mis a jour.")


def merge_shipment_recipient_organizations(*, data) -> tuple[bool, str]:
    form = ShipmentRecipientOrganizationMergeForm(data)
    if not form.is_valid():
        return False, _("Donnees de fusion invalides.")

    source = (
        ShipmentRecipientOrganization.objects.select_related("organization", "destination")
        .filter(pk=form.cleaned_data["source_recipient_organization_id"])
        .first()
    )
    target = (
        ShipmentRecipientOrganization.objects.select_related("organization", "destination")
        .filter(pk=form.cleaned_data["target_recipient_organization_id"])
        .first()
    )
    if source is None or target is None:
        return False, _("Structure destinataire introuvable.")
    if source.pk == target.pk:
        return False, _("La source et la cible doivent etre distinctes.")
    if source.destination_id != target.destination_id:
        return False, _("La fusion doit rester sur la meme escale.")

    duplicate_contact_ids_to_delete = []
    duplicate_link_ids_to_delete = []

    with transaction.atomic():
        contact_map = {}
        source_recipient_contacts = list(
            ShipmentRecipientContact.objects.select_related("contact")
            .filter(recipient_organization=source)
            .order_by("id")
        )
        for source_recipient_contact in source_recipient_contacts:
            person = source_recipient_contact.contact
            if person.organization_id != target.organization_id:
                person.organization = target.organization
                person.save(update_fields=["organization"])

            target_recipient_contact = (
                ShipmentRecipientContact.objects.filter(
                    recipient_organization=target,
                    contact=person,
                )
                .exclude(pk=source_recipient_contact.pk)
                .first()
            )
            if target_recipient_contact is None:
                source_recipient_contact.recipient_organization = target
                source_recipient_contact.save(update_fields=["recipient_organization"])
                target_recipient_contact = source_recipient_contact
            else:
                if source_recipient_contact.is_active and not target_recipient_contact.is_active:
                    target_recipient_contact.is_active = True
                    target_recipient_contact.save(update_fields=["is_active"])
                duplicate_contact_ids_to_delete.append(source_recipient_contact.pk)
            contact_map[source_recipient_contact.pk] = target_recipient_contact

        link_map = {}
        target_link_default_exists = {}
        source_links = list(
            ShipmentShipperRecipientLink.objects.filter(recipient_organization=source).order_by(
                "id"
            )
        )
        for source_link in source_links:
            target_link = (
                ShipmentShipperRecipientLink.objects.filter(
                    shipper=source_link.shipper,
                    recipient_organization=target,
                )
                .exclude(pk=source_link.pk)
                .first()
            )
            if target_link is None:
                source_link.recipient_organization = target
                source_link.save(update_fields=["recipient_organization"])
                target_link = source_link
            else:
                if source_link.is_active and not target_link.is_active:
                    target_link.is_active = True
                    target_link.save(update_fields=["is_active"])
                duplicate_link_ids_to_delete.append(source_link.pk)
            link_map[source_link.pk] = target_link
            target_link_default_exists[target_link.pk] = (
                ShipmentAuthorizedRecipientContact.objects.filter(
                    link=target_link,
                    is_default=True,
                    is_active=True,
                ).exists()
            )

        source_authorizations = list(
            ShipmentAuthorizedRecipientContact.objects.select_related("recipient_contact")
            .filter(link_id__in=link_map.keys())
            .order_by("id")
        )
        for authorization in source_authorizations:
            target_link = link_map[authorization.link_id]
            target_recipient_contact = contact_map[authorization.recipient_contact_id]
            desired_default = (
                authorization.is_default
                and authorization.is_active
                and not target_link_default_exists.get(target_link.pk, False)
            )

            target_authorization = (
                ShipmentAuthorizedRecipientContact.objects.filter(
                    link=target_link,
                    recipient_contact=target_recipient_contact,
                )
                .exclude(pk=authorization.pk)
                .first()
            )
            if target_authorization is None:
                update_fields = []
                if authorization.link_id != target_link.pk:
                    authorization.link = target_link
                    update_fields.append("link")
                if authorization.recipient_contact_id != target_recipient_contact.pk:
                    authorization.recipient_contact = target_recipient_contact
                    update_fields.append("recipient_contact")
                if authorization.is_default != desired_default:
                    authorization.is_default = desired_default
                    update_fields.append("is_default")
                if update_fields:
                    authorization.save(update_fields=update_fields)
                if desired_default:
                    target_link_default_exists[target_link.pk] = True
                continue

            updated_fields = []
            if authorization.is_active and not target_authorization.is_active:
                target_authorization.is_active = True
                updated_fields.append("is_active")
            if desired_default and not target_authorization.is_default:
                ShipmentAuthorizedRecipientContact.objects.filter(
                    link=target_link,
                    is_default=True,
                ).exclude(pk=target_authorization.pk).update(is_default=False)
                target_authorization.is_default = True
                updated_fields.append("is_default")
                target_link_default_exists[target_link.pk] = True
            if updated_fields:
                target_authorization.save(update_fields=updated_fields)
            authorization.delete()

        if duplicate_link_ids_to_delete:
            ShipmentShipperRecipientLink.objects.filter(
                id__in=duplicate_link_ids_to_delete
            ).delete()
        if duplicate_contact_ids_to_delete:
            ShipmentRecipientContact.objects.filter(id__in=duplicate_contact_ids_to_delete).delete()

        if source.is_correspondent and not target.is_correspondent:
            ShipmentRecipientOrganization.objects.filter(
                destination=target.destination,
                is_correspondent=True,
            ).exclude(pk=target.pk).update(is_correspondent=False)
            target.is_correspondent = True
            target.save(update_fields=["is_correspondent"])

        source.is_active = False
        source.is_correspondent = False
        source.save(update_fields=["is_active", "is_correspondent"])
        source.organization.is_active = False
        source.organization.save(update_fields=["is_active"])

    return True, _("Structures destinataires fusionnees.")


def _build_shipment_party_shippers():
    shippers = list(
        ShipmentShipper.objects.select_related("organization", "default_contact")
        .filter(organization__is_active=True)
        .order_by("organization__name", "id")
    )
    for shipper in shippers:
        shipper.active_link_count = shipper.recipient_links.filter(
            is_active=True,
            recipient_organization__is_active=True,
            recipient_organization__organization__is_active=True,
        ).count()
    return shippers


def _build_shipment_party_recipient_organizations():
    recipient_organizations = list(
        ShipmentRecipientOrganization.objects.select_related("organization", "destination")
        .filter(
            organization__is_active=True,
            destination__is_active=True,
        )
        .order_by("destination__city", "organization__name", "id")
    )
    for recipient_organization in recipient_organizations:
        recipient_organization.active_recipient_contact_count = (
            recipient_organization.recipient_contacts.filter(
                is_active=True,
                contact__is_active=True,
            ).count()
        )
        recipient_organization.active_link_count = recipient_organization.shipper_links.filter(
            is_active=True,
            shipper__organization__is_active=True,
        ).count()
    return recipient_organizations


def _build_shipment_party_links():
    links = list(
        ShipmentShipperRecipientLink.objects.select_related(
            "shipper",
            "shipper__organization",
            "recipient_organization",
            "recipient_organization__organization",
            "recipient_organization__destination",
        )
        .prefetch_related(
            "authorized_recipient_contacts__recipient_contact__contact",
        )
        .filter(
            shipper__organization__is_active=True,
            recipient_organization__organization__is_active=True,
            recipient_organization__destination__is_active=True,
        )
        .order_by(
            "shipper__organization__name",
            "recipient_organization__organization__name",
            "id",
        )
    )
    for link in links:
        default_authorization = next(
            (
                authorization
                for authorization in link.authorized_recipient_contacts.all()
                if authorization.is_active
                and authorization.is_default
                and authorization.recipient_contact.is_active
                and authorization.recipient_contact.contact.is_active
            ),
            None,
        )
        link.default_authorized_contact = (
            default_authorization.recipient_contact.contact
            if default_authorization is not None
            else None
        )
        link.active_authorized_contact_count = sum(
            1
            for authorization in link.authorized_recipient_contacts.all()
            if authorization.is_active
            and authorization.recipient_contact.is_active
            and authorization.recipient_contact.contact.is_active
        )
    return links


def _build_shipment_party_correspondents(recipient_organizations):
    return [
        recipient_organization
        for recipient_organization in recipient_organizations
        if recipient_organization.is_active and recipient_organization.is_correspondent
    ]


def _build_shipment_party_authorization_options(links):
    options = []
    for link in links:
        for authorization in link.authorized_recipient_contacts.all():
            if not authorization.is_active:
                continue
            recipient_contact = authorization.recipient_contact
            contact = recipient_contact.contact
            if not recipient_contact.is_active or not contact.is_active:
                continue
            options.append(
                {
                    "link_id": link.id,
                    "recipient_contact_id": recipient_contact.id,
                    "label": _("%(shipper)s -> %(recipient)s / %(contact)s")
                    % {
                        "shipper": link.shipper.organization.name,
                        "recipient": link.recipient_organization.organization.name,
                        "contact": contact,
                    },
                    "is_default": authorization.is_default,
                }
            )
    return options


def build_cockpit_context(*, query: str, filters: dict) -> dict:
    shipment_shippers = _build_shipment_party_shippers()
    shipment_recipient_organizations = _build_shipment_party_recipient_organizations()
    shipment_links = _build_shipment_party_links()
    return {
        "cockpit_mode": "shipment_parties",
        "cockpit_filters": {},
        "cockpit_shipment_shippers": shipment_shippers,
        "cockpit_shipment_recipient_organizations": shipment_recipient_organizations,
        "cockpit_shipment_links": shipment_links,
        "cockpit_shipment_correspondents": _build_shipment_party_correspondents(
            shipment_recipient_organizations
        ),
        "cockpit_shipment_authorization_options": _build_shipment_party_authorization_options(
            shipment_links
        ),
        "cockpit_destinations": list(
            Destination.objects.filter(is_active=True).order_by("city", "iata_code", "id")
        ),
        "cockpit_organizations": list(
            Contact.objects.filter(
                contact_type=ContactType.ORGANIZATION,
                is_active=True,
            ).order_by("name", "id")
        ),
    }
