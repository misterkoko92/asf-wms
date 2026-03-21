from __future__ import annotations

from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from contacts.capabilities import ContactCapabilityType
from contacts.models import Contact, ContactType

from .admin_contacts_contact_service import (
    build_contact_duplicate_candidates,
    deactivate_contact,
    save_contact_from_form,
)
from .admin_contacts_destination_service import (
    build_destination_duplicate_candidates,
    save_destination_from_form,
)
from .admin_contacts_merge_service import merge_contacts
from .forms_admin_contacts_contact import ContactCrudForm
from .forms_admin_contacts_destination import DestinationCrudForm
from .models import (
    Destination,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
)

ACTION_SAVE_DESTINATION = "save_destination"
ACTION_SAVE_CONTACT = "save_contact"
ACTION_DEACTIVATE_CONTACT = "deactivate_contact"
ACTION_MERGE_CONTACT = "merge_contact"


@dataclass
class AdminContactsCrudOutcome:
    should_redirect: bool = True
    message_level: str | None = None
    message: str | None = None
    destination_form: DestinationCrudForm | None = None
    contact_form: ContactCrudForm | None = None
    destination_duplicate_candidates: list[Destination] = field(default_factory=list)
    contact_duplicate_candidates: list[Contact] = field(default_factory=list)
    contact_form_mode: str = "create"
    editing_contact: Contact | None = None


def _contact_capabilities(contact: Contact) -> set[str]:
    return {
        capability.capability
        for capability in contact.capabilities.filter(is_active=True).only("capability")
    }


def _infer_contact_business_type(contact: Contact) -> str:
    capabilities = _contact_capabilities(contact)
    runtime_contact = contact
    if contact.contact_type == ContactType.PERSON and contact.organization_id:
        runtime_contact = contact.organization

    if ShipmentShipper.objects.filter(organization=runtime_contact, is_active=True).exists():
        return "shipper"

    recipient_orgs = ShipmentRecipientOrganization.objects.filter(
        organization=runtime_contact,
        is_active=True,
    )
    if recipient_orgs.filter(is_correspondent=True).exists():
        return "correspondent"
    if recipient_orgs.exists():
        return "recipient"
    if ContactCapabilityType.DONOR in capabilities:
        return "donor"
    if ContactCapabilityType.TRANSPORTER in capabilities:
        return "transporter"
    if ContactCapabilityType.VOLUNTEER in capabilities:
        return "volunteer"
    if contact.contact_type == ContactType.PERSON:
        return "volunteer"
    return "donor"


def _contact_initial_from_instance(contact: Contact) -> dict[str, object]:
    business_type = _infer_contact_business_type(contact)
    organization = contact.organization if contact.contact_type == ContactType.PERSON else contact
    referent = contact if contact.contact_type == ContactType.PERSON else None
    destination = None
    allowed_shipper_ids: list[int] = []
    can_send_to_all = False

    shipper = ShipmentShipper.objects.filter(organization=organization, is_active=True).first()
    if shipper is not None:
        referent = shipper.default_contact or referent
        can_send_to_all = shipper.can_send_to_all

    recipient_org = (
        ShipmentRecipientOrganization.objects.filter(
            organization=organization,
            is_active=True,
        )
        .order_by("-is_correspondent", "destination__city", "id")
        .first()
    )
    if recipient_org is not None:
        destination = recipient_org.destination
        if referent is None:
            recipient_contact = (
                ShipmentRecipientContact.objects.filter(
                    recipient_organization=recipient_org,
                    is_active=True,
                )
                .select_related("contact")
                .order_by("id")
                .first()
            )
            if recipient_contact is not None:
                referent = recipient_contact.contact
        allowed_shipper_ids = list(
            recipient_org.shipper_links.filter(is_active=True)
            .values_list("shipper__organization_id", flat=True)
            .distinct()
        )

    address_owner = contact
    address = address_owner.get_effective_address()
    initial = {
        "business_type": business_type,
        "entity_type": contact.contact_type,
        "organization_name": organization.name if organization else "",
        "title": contact.title
        if contact.contact_type == ContactType.PERSON
        else getattr(referent, "title", ""),
        "first_name": contact.first_name
        if contact.contact_type == ContactType.PERSON
        else getattr(referent, "first_name", ""),
        "last_name": contact.last_name
        if contact.contact_type == ContactType.PERSON
        else getattr(referent, "last_name", ""),
        "asf_id": contact.asf_id or "",
        "email": contact.email
        if contact.contact_type == ContactType.PERSON
        else getattr(referent, "email", contact.email),
        "email2": contact.email2
        if contact.contact_type == ContactType.PERSON
        else getattr(referent, "email2", contact.email2),
        "phone": contact.phone
        if contact.contact_type == ContactType.PERSON
        else getattr(referent, "phone", contact.phone),
        "phone2": contact.phone2
        if contact.contact_type == ContactType.PERSON
        else getattr(referent, "phone2", contact.phone2),
        "role": contact.role
        if contact.contact_type == ContactType.PERSON
        else getattr(referent, "role", contact.role),
        "siret": contact.siret,
        "vat_number": contact.vat_number,
        "legal_registration_number": contact.legal_registration_number,
        "address_line1": getattr(address, "address_line1", ""),
        "address_line2": getattr(address, "address_line2", ""),
        "postal_code": getattr(address, "postal_code", ""),
        "city": getattr(address, "city", ""),
        "region": getattr(address, "region", ""),
        "country": getattr(address, "country", ""),
        "notes": contact.notes,
        "destination_id": getattr(destination, "id", None),
        "allowed_shipper_ids": allowed_shipper_ids,
        "can_send_to_all": can_send_to_all,
        "use_organization_address": contact.use_organization_address,
        "is_active": contact.is_active,
    }
    if contact.contact_type == ContactType.PERSON and contact.organization_id:
        initial["organization_name"] = contact.organization.name
    return initial


def build_admin_contacts_forms(*, edit_contact_id=None, destination_form=None, contact_form=None):
    editing_contact = None
    contact_form_mode = "create"

    if destination_form is None:
        destination_form = DestinationCrudForm(initial={"is_active": True})

    if edit_contact_id:
        editing_contact = (
            Contact.objects.filter(pk=edit_contact_id).select_related("organization").first()
        )
        if editing_contact is not None and contact_form is None:
            contact_form = ContactCrudForm(initial=_contact_initial_from_instance(editing_contact))
            contact_form_mode = "edit"

    if contact_form is None:
        contact_form = ContactCrudForm(initial={"is_active": True})

    return {
        "destination_form": destination_form,
        "contact_form": contact_form,
        "destination_duplicate_candidates": [],
        "contact_duplicate_candidates": [],
        "contact_form_mode": contact_form_mode,
        "editing_contact": editing_contact,
    }


def _rebind_with_duplicate_review(form_class, data, *, count: int):
    mutable_data = data.copy()
    mutable_data["duplicate_candidates_count"] = str(count)
    form = form_class(mutable_data)
    form.is_valid()
    return form


def _attach_validation_error(form, error: ValidationError):
    if hasattr(error, "message_dict"):
        for field_name, messages in error.message_dict.items():
            for message in messages:
                form.add_error(field_name, message)
        return
    for message in error.messages:
        form.add_error(None, message)


def handle_destination_submission(post_data) -> AdminContactsCrudOutcome:
    form = DestinationCrudForm(post_data)
    if not form.is_valid():
        return AdminContactsCrudOutcome(
            should_redirect=False,
            destination_form=form,
        )

    cleaned_data = form.cleaned_data
    duplicate_action = (cleaned_data.get("duplicate_action") or "").strip()
    candidates = []
    if not duplicate_action:
        candidates = build_destination_duplicate_candidates(cleaned_data)
        if candidates:
            return AdminContactsCrudOutcome(
                should_redirect=False,
                destination_form=_rebind_with_duplicate_review(
                    DestinationCrudForm,
                    post_data,
                    count=len(candidates),
                ),
                destination_duplicate_candidates=candidates,
            )

    try:
        save_destination_from_form(cleaned_data)
    except ValidationError as error:
        _attach_validation_error(form, error)
        return AdminContactsCrudOutcome(
            should_redirect=False,
            destination_form=form,
            destination_duplicate_candidates=candidates,
        )

    return AdminContactsCrudOutcome(
        should_redirect=True,
        message_level="success",
        message=_("Destination enregistrée."),
    )


def handle_contact_submission(post_data) -> AdminContactsCrudOutcome:
    editing_contact = None
    editing_contact_id = (post_data.get("editing_contact_id") or "").strip()
    if editing_contact_id.isdigit():
        editing_contact = (
            Contact.objects.filter(pk=int(editing_contact_id))
            .select_related("organization")
            .first()
        )

    form = ContactCrudForm(post_data)
    if not form.is_valid():
        return AdminContactsCrudOutcome(
            should_redirect=False,
            contact_form=form,
            contact_form_mode="edit" if editing_contact is not None else "create",
            editing_contact=editing_contact,
        )

    cleaned_data = form.cleaned_data
    duplicate_action = (cleaned_data.get("duplicate_action") or "").strip()
    candidates = []
    if not duplicate_action:
        candidates = build_contact_duplicate_candidates(
            cleaned_data,
            exclude_contact_id=getattr(editing_contact, "id", None),
        )
        if candidates:
            return AdminContactsCrudOutcome(
                should_redirect=False,
                contact_form=_rebind_with_duplicate_review(
                    ContactCrudForm,
                    post_data,
                    count=len(candidates),
                ),
                contact_duplicate_candidates=candidates,
                contact_form_mode="edit" if editing_contact is not None else "create",
                editing_contact=editing_contact,
            )

    try:
        save_contact_from_form(cleaned_data, editing_contact=editing_contact)
    except ValidationError as error:
        _attach_validation_error(form, error)
        return AdminContactsCrudOutcome(
            should_redirect=False,
            contact_form=form,
            contact_duplicate_candidates=candidates,
            contact_form_mode="edit" if editing_contact is not None else "create",
            editing_contact=editing_contact,
        )

    return AdminContactsCrudOutcome(
        should_redirect=True,
        message_level="success",
        message=_("Contact enregistré."),
    )


def handle_contact_deactivation(post_data) -> AdminContactsCrudOutcome:
    contact_id = (post_data.get("contact_id") or "").strip()
    if not contact_id.isdigit():
        return AdminContactsCrudOutcome(
            should_redirect=True,
            message_level="error",
            message=_("Contact introuvable."),
        )
    try:
        contact = deactivate_contact(int(contact_id))
    except ValidationError as error:
        return AdminContactsCrudOutcome(
            should_redirect=True,
            message_level="error",
            message=" ".join(error.messages),
        )
    return AdminContactsCrudOutcome(
        should_redirect=True,
        message_level="success",
        message=_("Contact désactivé: %(name)s") % {"name": contact.name},
    )


def handle_contact_merge(post_data) -> AdminContactsCrudOutcome:
    source_contact_id = (post_data.get("source_contact_id") or "").strip()
    target_contact_id = (post_data.get("target_contact_id") or "").strip()
    if not source_contact_id.isdigit() or not target_contact_id.isdigit():
        return AdminContactsCrudOutcome(
            should_redirect=True,
            message_level="error",
            message=_("Choisissez une source et une cible pour la fusion."),
        )

    source_contact = Contact.objects.filter(pk=int(source_contact_id)).first()
    target_contact = Contact.objects.filter(pk=int(target_contact_id)).first()
    if source_contact is None or target_contact is None:
        return AdminContactsCrudOutcome(
            should_redirect=True,
            message_level="error",
            message=_("Fiche de fusion introuvable."),
        )

    try:
        merge_contacts(source_contact=source_contact, target_contact=target_contact)
    except ValidationError as error:
        return AdminContactsCrudOutcome(
            should_redirect=True,
            message_level="error",
            message=" ".join(error.messages),
        )

    return AdminContactsCrudOutcome(
        should_redirect=True,
        message_level="success",
        message=_("Fusion terminée vers %(name)s.") % {"name": target_contact.name},
    )
