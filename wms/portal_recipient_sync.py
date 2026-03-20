from django.db import transaction
from django.utils import timezone

from contacts.models import Contact, ContactAddress, ContactType
from wms.models import (
    AssociationRecipient,
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
    RecipientBinding,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
    ShipperScope,
)
from wms.shipment_party_registry import default_recipient_contact_for_link

PORTAL_RECIPIENT_ADDRESS_LABEL = "Portail association"
PORTAL_SHIPPER_CONTACT_FIRST_NAME = "Referent"
PORTAL_SHIPPER_CONTACT_LAST_NAME = "Portail"
PRIORITY_SHIPPER_NAME = "Aviation Sans Frontieres"


def _normalized_text(value) -> str:
    return str(value or "").strip()


def _casefold(value) -> str:
    return _normalized_text(value).casefold()


def _first_multi_value(raw_value: str, fallback: str = "") -> str:
    value = (raw_value or "").replace("\n", ";").replace(",", ";")
    for item in value.split(";"):
        normalized = item.strip()
        if normalized:
            return normalized
    return (fallback or "").strip()


def _build_contact_notes(recipient) -> str:
    notes = (recipient.notes or "").strip()
    association = f"Association: {recipient.association_contact}"
    if notes:
        return f"{association}\n{notes}"
    return association


def _recipient_structure_name(recipient) -> str:
    structure_name = _normalized_text(recipient.structure_name)
    if structure_name:
        return structure_name[:200]
    display_name = _normalized_text(recipient.get_display_name())
    if display_name:
        return display_name[:200]
    return f"Destinataire {recipient.pk}"[:200]


def _recipient_person_name(recipient, *, primary_email: str) -> str:
    contact_display = _normalized_text(recipient.get_contact_display_name())
    if contact_display:
        return contact_display[:200]
    if primary_email:
        return primary_email[:200]
    structure_name = _recipient_structure_name(recipient)
    return f"Referent {structure_name}"[:200]


def _get_synced_contact(recipient):
    if not recipient.pk or not recipient.synced_contact_id:
        return None
    return Contact.objects.filter(pk=recipient.synced_contact_id).first()


def _upsert_contact_address(*, contact, recipient, primary_phone, primary_email):
    if not recipient.address_line1:
        return
    address = (
        contact.addresses.filter(label=PORTAL_RECIPIENT_ADDRESS_LABEL).order_by("-id").first()
        or contact.addresses.filter(is_default=True).order_by("-id").first()
    )
    if address is None:
        address = ContactAddress(contact=contact)
    address.label = PORTAL_RECIPIENT_ADDRESS_LABEL
    address.address_line1 = recipient.address_line1
    address.address_line2 = recipient.address_line2
    address.postal_code = recipient.postal_code
    address.city = recipient.city
    address.country = recipient.country or "France"
    address.phone = primary_phone[:40]
    address.email = primary_email[:254]
    address.is_default = True
    address.notes = recipient.notes or ""
    address.save()


def _active_shipper_assignment_for_org(organization):
    return (
        OrganizationRoleAssignment.objects.filter(
            organization=organization,
            role=OrganizationRole.SHIPPER,
        )
        .order_by("id")
        .first()
    )


def _shipment_validation_status_for_shipper(organization) -> str:
    assignment = _active_shipper_assignment_for_org(organization)
    if assignment is not None and assignment.is_active:
        return ShipmentValidationStatus.VALIDATED
    return ShipmentValidationStatus.PENDING


def _ensure_shipper_default_contact(association_contact):
    existing = (
        association_contact.members.filter(
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        .order_by("id")
        .first()
    )
    if existing is not None:
        return existing

    portal_contact = None
    profile = association_contact.association_profiles.select_related("user").order_by("id").first()
    if profile is not None:
        portal_contact = (
            profile.portal_contacts.filter(is_active=True).order_by("position", "id").first()
        )

    first_name = _normalized_text(getattr(portal_contact, "first_name", "")) or (
        PORTAL_SHIPPER_CONTACT_FIRST_NAME
    )
    last_name = _normalized_text(getattr(portal_contact, "last_name", "")) or (
        PORTAL_SHIPPER_CONTACT_LAST_NAME
    )
    email = _normalized_text(getattr(portal_contact, "email", "")) or _normalized_text(
        association_contact.email
    )
    phone = _normalized_text(getattr(portal_contact, "phone", "")) or _normalized_text(
        association_contact.phone
    )

    return Contact.objects.create(
        contact_type=ContactType.PERSON,
        organization=association_contact,
        title=_normalized_text(getattr(portal_contact, "title", "")),
        first_name=first_name[:120],
        last_name=last_name[:120],
        name=f"{first_name} {last_name}".strip()[:200],
        email=email[:254],
        phone=phone[:40],
        use_organization_address=True,
        is_active=True,
    )


def _ensure_shipment_shipper(*, association_contact):
    default_contact = _ensure_shipper_default_contact(association_contact)
    shipper, created = ShipmentShipper.objects.get_or_create(
        organization=association_contact,
        defaults={
            "default_contact": default_contact,
            "validation_status": _shipment_validation_status_for_shipper(association_contact),
            "can_send_to_all": _casefold(association_contact.name)
            == _casefold(PRIORITY_SHIPPER_NAME),
            "is_active": True,
        },
    )
    if created:
        return shipper

    updated_fields = []
    if shipper.default_contact_id != default_contact.id:
        shipper.default_contact = default_contact
        updated_fields.append("default_contact")
    target_status = _shipment_validation_status_for_shipper(association_contact)
    if (
        shipper.validation_status == ShipmentValidationStatus.PENDING
        and target_status == ShipmentValidationStatus.VALIDATED
    ):
        shipper.validation_status = ShipmentValidationStatus.VALIDATED
        updated_fields.append("validation_status")
    target_can_send_to_all = _casefold(association_contact.name) == _casefold(PRIORITY_SHIPPER_NAME)
    if shipper.can_send_to_all != target_can_send_to_all:
        shipper.can_send_to_all = target_can_send_to_all
        updated_fields.append("can_send_to_all")
    if not shipper.is_active:
        shipper.is_active = True
        updated_fields.append("is_active")
    if updated_fields:
        shipper.save(update_fields=updated_fields)
    return shipper


def _can_reuse_synced_contact_for_destination(contact, destination):
    existing = ShipmentRecipientOrganization.objects.filter(organization=contact).first()
    if existing is None:
        return True
    return existing.destination_id == getattr(destination, "id", None)


def _find_existing_recipient_organization(recipient, *, prefer_existing_structure=True):
    synced_contact = _get_synced_contact(recipient)
    if synced_contact is not None and synced_contact.contact_type == ContactType.ORGANIZATION:
        existing = ShipmentRecipientOrganization.objects.filter(organization=synced_contact).first()
        if existing is not None and existing.destination_id == recipient.destination_id:
            return existing

    structure_name = _recipient_structure_name(recipient)
    if prefer_existing_structure and recipient.destination_id and structure_name:
        exact_matches = list(
            ShipmentRecipientOrganization.objects.select_related("organization")
            .filter(
                destination=recipient.destination,
                organization__name__iexact=structure_name,
            )
            .order_by("id")[:2]
        )
        if len(exact_matches) == 1:
            return exact_matches[0]

    if (
        synced_contact is not None
        and synced_contact.contact_type == ContactType.ORGANIZATION
        and _can_reuse_synced_contact_for_destination(synced_contact, recipient.destination)
    ):
        return (
            ShipmentRecipientOrganization.objects.select_related("organization")
            .filter(organization=synced_contact)
            .first()
        )
    return None


def _upsert_recipient_structure_contact(
    *,
    recipient,
    primary_email,
    primary_phone,
    prefer_existing_structure=True,
):
    existing_recipient_org = _find_existing_recipient_organization(
        recipient,
        prefer_existing_structure=prefer_existing_structure,
    )
    synced_contact = _get_synced_contact(recipient)
    contact = existing_recipient_org.organization if existing_recipient_org is not None else None
    if (
        contact is None
        and synced_contact is not None
        and synced_contact.contact_type == ContactType.ORGANIZATION
        and _can_reuse_synced_contact_for_destination(synced_contact, recipient.destination)
    ):
        contact = synced_contact

    if contact is None:
        contact = Contact.objects.create(
            contact_type=ContactType.ORGANIZATION,
            name=_recipient_structure_name(recipient),
            email=primary_email[:254],
            phone=primary_phone[:40],
            notes=_build_contact_notes(recipient),
            is_active=True,
        )
    else:
        contact.contact_type = ContactType.ORGANIZATION
        contact.name = _recipient_structure_name(recipient)
        contact.email = primary_email[:254]
        contact.phone = primary_phone[:40]
        contact.notes = _build_contact_notes(recipient)
        contact.is_active = True
        contact.save(
            update_fields=[
                "contact_type",
                "name",
                "email",
                "phone",
                "notes",
                "is_active",
            ]
        )

    _upsert_contact_address(
        contact=contact,
        recipient=recipient,
        primary_phone=primary_phone,
        primary_email=primary_email,
    )
    if recipient.synced_contact_id != contact.id:
        recipient.synced_contact = contact
        recipient.save(update_fields=["synced_contact"])
    return contact


def _ensure_recipient_organization(*, contact, recipient):
    recipient_organization, created = ShipmentRecipientOrganization.objects.get_or_create(
        organization=contact,
        defaults={
            "destination": recipient.destination,
            "validation_status": ShipmentValidationStatus.PENDING,
            "is_correspondent": False,
            "is_active": True,
        },
    )
    if created:
        return recipient_organization

    updated_fields = []
    if (
        recipient.destination_id
        and recipient_organization.destination_id != recipient.destination_id
        and not recipient_organization.is_active
    ):
        recipient_organization.destination = recipient.destination
        updated_fields.append("destination")
    if not recipient_organization.is_active:
        recipient_organization.is_active = True
        updated_fields.append("is_active")
    if updated_fields:
        recipient_organization.save(update_fields=updated_fields)
    return recipient_organization


def _find_matching_person_contact(*, organization, recipient, primary_email):
    people = organization.members.filter(contact_type=ContactType.PERSON).order_by("id")

    if primary_email:
        match = people.filter(email__iexact=primary_email).first()
        if match is not None:
            return match

    first_name = _normalized_text(recipient.contact_first_name)
    last_name = _normalized_text(recipient.contact_last_name)
    if first_name or last_name:
        query = people
        if first_name:
            query = query.filter(first_name__iexact=first_name)
        if last_name:
            query = query.filter(last_name__iexact=last_name)
        match = query.first()
        if match is not None:
            return match

    contact_name = _normalized_text(recipient.get_contact_display_name())
    if contact_name:
        return people.filter(name__iexact=contact_name).first()
    return None


def _upsert_recipient_person_contact(
    *, recipient_organization, recipient, primary_email, primary_phone
):
    organization = recipient_organization.organization
    person = _find_matching_person_contact(
        organization=organization,
        recipient=recipient,
        primary_email=primary_email,
    )
    if person is None:
        person = Contact(organization=organization)

    person.contact_type = ContactType.PERSON
    person.organization = organization
    person.title = _normalized_text(recipient.get_contact_title_display())
    person.first_name = _normalized_text(recipient.contact_first_name)[:120]
    person.last_name = _normalized_text(recipient.contact_last_name)[:120]
    person.name = _recipient_person_name(recipient, primary_email=primary_email)
    person.email = primary_email[:254]
    person.phone = primary_phone[:40]
    person.use_organization_address = True
    person.is_active = True
    if person.pk is None:
        person.save()
    else:
        person.save(
            update_fields=[
                "contact_type",
                "organization",
                "title",
                "first_name",
                "last_name",
                "name",
                "email",
                "phone",
                "use_organization_address",
                "is_active",
            ]
        )

    shipment_contact, created = ShipmentRecipientContact.objects.get_or_create(
        recipient_organization=recipient_organization,
        contact=person,
        defaults={"is_active": True},
    )
    if not created and not shipment_contact.is_active:
        shipment_contact.is_active = True
        shipment_contact.save(update_fields=["is_active"])
    return shipment_contact


def _matching_shipment_recipient_contact(*, recipient, recipient_organization):
    queryset = ShipmentRecipientContact.objects.filter(
        recipient_organization=recipient_organization,
    ).select_related("contact")

    primary_email = _first_multi_value(recipient.emails, recipient.email)
    if primary_email:
        shipment_contact = (
            queryset.filter(contact__email__iexact=primary_email).order_by("id").first()
        )
        if shipment_contact is not None:
            return shipment_contact

    first_name = _normalized_text(recipient.contact_first_name)
    last_name = _normalized_text(recipient.contact_last_name)
    if first_name or last_name:
        match_query = queryset
        if first_name:
            match_query = match_query.filter(contact__first_name__iexact=first_name)
        if last_name:
            match_query = match_query.filter(contact__last_name__iexact=last_name)
        shipment_contact = match_query.order_by("id").first()
        if shipment_contact is not None:
            return shipment_contact

    contact_name = _normalized_text(recipient.get_contact_display_name())
    if contact_name:
        return queryset.filter(contact__name__iexact=contact_name).order_by("id").first()
    return None


def _ensure_shipper_recipient_link(*, shipper, recipient_organization):
    link, created = ShipmentShipperRecipientLink.objects.get_or_create(
        shipper=shipper,
        recipient_organization=recipient_organization,
        defaults={"is_active": True},
    )
    if not created and not link.is_active:
        link.is_active = True
        link.save(update_fields=["is_active"])
    return link


def _ensure_authorized_recipient_contact(
    *,
    link,
    recipient_contact,
    is_active,
    set_as_default,
):
    authorized, created = ShipmentAuthorizedRecipientContact.objects.get_or_create(
        link=link,
        recipient_contact=recipient_contact,
        defaults={
            "is_active": bool(is_active),
            # Clear any existing default before promoting this authorization.
            "is_default": False,
        },
    )
    updated_fields = []
    if authorized.is_active != bool(is_active):
        authorized.is_active = bool(is_active)
        updated_fields.append("is_active")

    should_be_default = False
    if is_active:
        if set_as_default:
            should_be_default = True
        else:
            has_other_default = (
                ShipmentAuthorizedRecipientContact.objects.filter(
                    link=link,
                    is_active=True,
                    is_default=True,
                )
                .exclude(pk=authorized.pk)
                .exists()
            )
            if authorized.is_default or not has_other_default:
                should_be_default = True

    if should_be_default:
        ShipmentAuthorizedRecipientContact.objects.filter(
            link=link,
            is_default=True,
        ).exclude(pk=authorized.pk).update(is_default=False)
    if authorized.is_default != should_be_default:
        authorized.is_default = should_be_default
        updated_fields.append("is_default")
    if updated_fields:
        authorized.save(update_fields=updated_fields)

    if not ShipmentAuthorizedRecipientContact.objects.filter(
        link=link,
        is_active=True,
    ).exists():
        if link.is_active:
            link.is_active = False
            link.save(update_fields=["is_active"])
    elif not link.is_active:
        link.is_active = True
        link.save(update_fields=["is_active"])

    return authorized


def _ensure_association_shipper_scope(*, association_contact, destination):
    if association_contact is None:
        return None
    assignment, _ = OrganizationRoleAssignment.objects.get_or_create(
        organization=association_contact,
        role=OrganizationRole.SHIPPER,
        defaults={"is_active": False},
    )
    if destination is not None:
        ShipperScope.objects.update_or_create(
            role_assignment=assignment,
            destination=destination,
            defaults={
                "all_destinations": False,
                "is_active": True,
                "valid_to": None,
            },
        )
    return assignment


def _ensure_primary_recipient_role_contact(
    *, role_assignment, recipient, primary_email, primary_phone
):
    if not primary_email:
        return None

    primary_link = (
        role_assignment.role_contacts.select_related("contact")
        .filter(is_primary=True)
        .order_by("-id")
        .first()
    )
    org_contact = (
        primary_link.contact
        if primary_link is not None
        else role_assignment.organization.organization_contacts.order_by("id").first()
    )
    if org_contact is None:
        org_contact = OrganizationContact(organization=role_assignment.organization)

    org_contact.title = recipient.contact_title or ""
    org_contact.last_name = recipient.contact_last_name[:120]
    org_contact.first_name = recipient.contact_first_name[:120]
    org_contact.email = primary_email[:254]
    org_contact.phone = primary_phone[:40]
    org_contact.is_active = True
    org_contact.save()

    if primary_link is None:
        role_contact, _ = OrganizationRoleContact.objects.get_or_create(
            role_assignment=role_assignment,
            contact=org_contact,
            defaults={"is_primary": True, "is_active": True},
        )
    else:
        role_contact = primary_link

    updated_fields = []
    if not role_contact.is_primary:
        role_contact.is_primary = True
        updated_fields.append("is_primary")
    if not role_contact.is_active:
        role_contact.is_active = True
        updated_fields.append("is_active")
    if updated_fields:
        role_contact.save(update_fields=updated_fields)
    return role_contact


def _ensure_recipient_role_assignment(*, contact, recipient, primary_email, primary_phone):
    assignment, _ = OrganizationRoleAssignment.objects.get_or_create(
        organization=contact,
        role=OrganizationRole.RECIPIENT,
        defaults={"is_active": True},
    )
    _ensure_primary_recipient_role_contact(
        role_assignment=assignment,
        recipient=recipient,
        primary_email=primary_email,
        primary_phone=primary_phone,
    )
    if not assignment.is_active:
        assignment.is_active = True
        assignment.save(update_fields=["is_active"])
    return assignment


def _has_active_portal_binding(*, recipient, structure_contact):
    query = AssociationRecipient.objects.filter(
        association_contact=recipient.association_contact,
        destination=recipient.destination,
        is_active=True,
        synced_contact=structure_contact,
    )
    if recipient.pk:
        query = query.exclude(pk=recipient.pk)
    return query.exists()


def _sync_recipient_binding(*, association_contact, recipient_contact, destination, is_active):
    if association_contact is None or recipient_contact is None:
        return None

    active_bindings = RecipientBinding.objects.filter(
        shipper_org=association_contact,
        recipient_org=recipient_contact,
        is_active=True,
    )
    now = timezone.now()
    if destination is None or not is_active:
        active_bindings.update(is_active=False, valid_to=now)
        return None

    active_bindings.exclude(destination=destination).update(is_active=False, valid_to=now)
    binding = (
        RecipientBinding.objects.filter(
            shipper_org=association_contact,
            recipient_org=recipient_contact,
            destination=destination,
            is_active=True,
        )
        .order_by("-valid_from", "-id")
        .first()
    )
    if binding is not None:
        return binding
    return RecipientBinding.objects.create(
        shipper_org=association_contact,
        recipient_org=recipient_contact,
        destination=destination,
        is_active=True,
    )


def sync_association_recipient_to_contact(
    recipient,
    *,
    set_as_default=True,
    prefer_existing_structure=True,
):
    if not recipient:
        return None
    primary_email = _first_multi_value(recipient.emails, recipient.email)
    primary_phone = _first_multi_value(recipient.phones, recipient.phone)

    with transaction.atomic():
        shipper = _ensure_shipment_shipper(association_contact=recipient.association_contact)
        _ensure_association_shipper_scope(
            association_contact=recipient.association_contact,
            destination=recipient.destination,
        )

        structure_contact = _upsert_recipient_structure_contact(
            recipient=recipient,
            primary_email=primary_email,
            primary_phone=primary_phone,
            prefer_existing_structure=prefer_existing_structure,
        )
        recipient_organization = _ensure_recipient_organization(
            contact=structure_contact,
            recipient=recipient,
        )
        shipment_contact = _upsert_recipient_person_contact(
            recipient_organization=recipient_organization,
            recipient=recipient,
            primary_email=primary_email,
            primary_phone=primary_phone,
        )
        link = _ensure_shipper_recipient_link(
            shipper=shipper,
            recipient_organization=recipient_organization,
        )
        _ensure_authorized_recipient_contact(
            link=link,
            recipient_contact=shipment_contact,
            is_active=bool(recipient.is_active),
            set_as_default=set_as_default,
        )

        _ensure_recipient_role_assignment(
            contact=structure_contact,
            recipient=recipient,
            primary_email=primary_email,
            primary_phone=primary_phone,
        )
        _sync_recipient_binding(
            association_contact=recipient.association_contact,
            recipient_contact=structure_contact,
            destination=recipient.destination,
            is_active=bool(
                recipient.is_active
                or _has_active_portal_binding(
                    recipient=recipient,
                    structure_contact=structure_contact,
                )
            ),
        )
        return structure_contact


def resolve_association_recipient_party_contact(recipient):
    synced_contact = _get_synced_contact(recipient)
    if synced_contact is None:
        synced_contact = sync_association_recipient_to_contact(
            recipient,
            set_as_default=False,
        )
    if synced_contact is None:
        return None

    recipient_organization = (
        ShipmentRecipientOrganization.objects.filter(
            organization=synced_contact,
            destination=recipient.destination,
        )
        .select_related("organization")
        .first()
        or ShipmentRecipientOrganization.objects.filter(organization=synced_contact)
        .select_related("organization")
        .first()
    )
    if recipient_organization is None:
        return synced_contact

    shipment_contact = _matching_shipment_recipient_contact(
        recipient=recipient,
        recipient_organization=recipient_organization,
    )
    shipper = ShipmentShipper.objects.filter(organization=recipient.association_contact).first()
    link = None
    if shipper is not None:
        link = (
            ShipmentShipperRecipientLink.objects.filter(
                shipper=shipper,
                recipient_organization=recipient_organization,
            )
            .order_by("id")
            .first()
        )

    if shipment_contact is not None:
        if link is None:
            return shipment_contact.contact
        authorized = ShipmentAuthorizedRecipientContact.objects.filter(
            link=link,
            recipient_contact=shipment_contact,
            is_active=True,
        ).exists()
        if authorized:
            return shipment_contact.contact

    default_contact = default_recipient_contact_for_link(link) if link is not None else None
    if default_contact is not None:
        return default_contact.contact
    return synced_contact
