from __future__ import annotations

from dataclasses import dataclass, field

from contacts.models import Contact, ContactAddress, ContactType

from .application.parties.use_cases import update_runtime_recipient_shared_profile
from .default_shipper_bindings import ensure_default_shipper_links_for_recipient_organization_id
from .models import (
    Destination,
    PortalAccessGrant,
    PortalAccessRole,
    PublicAccountRequestType,
)

RECIPIENT_DEFAULT_CONTACT_FIRST_NAME = "Referent"
RECIPIENT_DEFAULT_CONTACT_LAST_NAME = "Portail"


def _clean_text(value) -> str:
    return str(value or "").strip()


def _clean_int(value):
    if value in (None, "", []):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_int_list(values) -> list[int]:
    if values in (None, "", []):
        return []
    if isinstance(values, str | bytes):
        values = [values]
    cleaned = []
    for value in values:
        parsed = _clean_int(value)
        if parsed is not None:
            cleaned.append(parsed)
    return cleaned


@dataclass(frozen=True)
class AccountRequestReviewPayload:
    final_account_type: str
    organization_name: str
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    address_line1: str = ""
    address_line2: str = ""
    postal_code: str = ""
    city: str = ""
    country: str = ""
    destination_id: int | None = None
    allowed_shipper_ids: list[int] = field(default_factory=list)
    legal_form: str = ""
    beneficiary_count: int | None = None

    def build_snapshot(self) -> dict:
        snapshot = {
            "final_account_type": self.final_account_type,
            "organization_name": self.organization_name,
            "email": self.email,
            "phone": self.phone,
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "postal_code": self.postal_code,
            "city": self.city,
            "country": self.country,
            "allowed_shipper_ids": list(self.allowed_shipper_ids),
        }
        if self.first_name:
            snapshot["first_name"] = self.first_name
        if self.last_name:
            snapshot["last_name"] = self.last_name
        if self.destination_id is not None:
            snapshot["destination_id"] = self.destination_id
        if self.legal_form:
            snapshot["legal_form"] = self.legal_form
        if self.beneficiary_count is not None:
            snapshot["beneficiary_count"] = self.beneficiary_count
        return snapshot


def build_account_request_review_payload(*, account_request, review_overrides=None):
    overrides = dict(review_overrides or {})
    return AccountRequestReviewPayload(
        final_account_type=(
            _clean_text(overrides.get("final_account_type")) or account_request.account_type
        ),
        organization_name=(
            _clean_text(overrides.get("organization_name")) or account_request.association_name
        ),
        first_name=_clean_text(overrides.get("first_name")),
        last_name=_clean_text(overrides.get("last_name")),
        email=_clean_text(overrides.get("email")) or account_request.email,
        phone=_clean_text(overrides.get("phone")) or account_request.phone,
        address_line1=_clean_text(overrides.get("address_line1")) or account_request.address_line1,
        address_line2=_clean_text(overrides.get("address_line2")) or account_request.address_line2,
        postal_code=_clean_text(overrides.get("postal_code")) or account_request.postal_code,
        city=_clean_text(overrides.get("city")) or account_request.city,
        country=_clean_text(overrides.get("country")) or account_request.country or "France",
        destination_id=_clean_int(overrides.get("destination_id"))
        or account_request.destination_id,
        allowed_shipper_ids=_clean_int_list(overrides.get("allowed_shipper_ids")),
        legal_form=_clean_text(overrides.get("legal_form")),
        beneficiary_count=_clean_int(overrides.get("beneficiary_count")),
    )


def apply_review_payload_to_account_request(*, account_request, payload):
    original_account_type = account_request.account_type
    update_fields = []

    if payload.final_account_type != original_account_type and not _clean_text(
        account_request.requested_account_type
    ):
        account_request.requested_account_type = original_account_type
        update_fields.append("requested_account_type")

    field_updates = {
        "account_type": payload.final_account_type,
        "association_name": payload.organization_name or account_request.association_name,
        "email": payload.email,
        "phone": payload.phone,
        "address_line1": payload.address_line1,
        "address_line2": payload.address_line2,
        "postal_code": payload.postal_code,
        "city": payload.city,
        "country": payload.country,
        "destination_id": (
            payload.destination_id
            if payload.final_account_type == PublicAccountRequestType.RECIPIENT
            else None
        ),
        "review_snapshot": payload.build_snapshot(),
    }
    for field_name, value in field_updates.items():
        if getattr(account_request, field_name) != value:
            setattr(account_request, field_name, value)
            update_fields.append(field_name)

    return update_fields


def _ensure_contact_address(*, contact, payload):
    address = (
        contact.get_effective_address()
        if hasattr(contact, "get_effective_address")
        else contact.addresses.filter(is_default=True).first() or contact.addresses.first()
    )
    if address is None:
        address = ContactAddress(contact=contact, is_default=True)
    address.address_line1 = payload.address_line1
    address.address_line2 = payload.address_line2
    address.postal_code = payload.postal_code
    address.city = payload.city
    address.country = payload.country or "France"
    address.phone = payload.phone
    address.email = payload.email
    address.is_default = True
    address.save()
    return address


def ensure_review_organization_contact(*, account_request, payload):
    contact = account_request.contact
    if contact is None:
        contact = Contact(
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    update_fields = []
    if contact.contact_type != ContactType.ORGANIZATION:
        contact.contact_type = ContactType.ORGANIZATION
        update_fields.append("contact_type")
    if not contact.is_active:
        contact.is_active = True
        update_fields.append("is_active")
    if payload.organization_name and contact.name != payload.organization_name:
        contact.name = payload.organization_name
        update_fields.append("name")
    if payload.email and contact.email != payload.email:
        contact.email = payload.email
        update_fields.append("email")
    if payload.phone and contact.phone != payload.phone:
        contact.phone = payload.phone
        update_fields.append("phone")
    if payload.legal_form and contact.legal_form != payload.legal_form:
        contact.legal_form = payload.legal_form
        update_fields.append("legal_form")
    if (
        payload.beneficiary_count is not None
        and contact.beneficiary_count != payload.beneficiary_count
    ):
        contact.beneficiary_count = payload.beneficiary_count
        update_fields.append("beneficiary_count")

    if contact.pk is None:
        contact.save()
    elif update_fields:
        contact.save(update_fields=update_fields)

    _ensure_contact_address(contact=contact, payload=payload)
    return contact


def ensure_review_recipient_referent(*, organization, payload):
    referent = (
        organization.members.filter(
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        .order_by("id")
        .first()
    )
    if referent is None:
        referent = Contact(
            contact_type=ContactType.PERSON,
            organization=organization,
            is_active=True,
            use_organization_address=True,
        )

    first_name = payload.first_name or referent.first_name or RECIPIENT_DEFAULT_CONTACT_FIRST_NAME
    last_name = payload.last_name or referent.last_name or RECIPIENT_DEFAULT_CONTACT_LAST_NAME
    full_name = (
        " ".join(part for part in [first_name, last_name] if part).strip() or organization.name
    )

    update_fields = []
    scalar_updates = {
        "contact_type": ContactType.PERSON,
        "organization": organization,
        "first_name": first_name,
        "last_name": last_name,
        "name": full_name,
        "email": payload.email or referent.email,
        "phone": payload.phone or referent.phone,
        "use_organization_address": True,
        "is_active": True,
    }
    for field_name, value in scalar_updates.items():
        current_value = getattr(referent, field_name)
        if current_value != value:
            setattr(referent, field_name, value)
            update_fields.append(field_name)

    if referent.pk is None:
        referent.save()
    elif update_fields:
        referent.save(update_fields=update_fields)
    return referent


def resolve_review_destination(payload):
    if payload.destination_id is None:
        return None
    return Destination.objects.filter(pk=payload.destination_id, is_active=True).first()


def resolve_allowed_shipper_contacts(payload) -> list[Contact]:
    if not payload.allowed_shipper_ids:
        return []
    return list(
        Contact.objects.filter(
            pk__in=payload.allowed_shipper_ids,
            is_active=True,
            contact_type=ContactType.ORGANIZATION,
        ).order_by("name", "id")
    )


def provision_recipient_review_runtime(*, request_user, account_request, user, payload):
    organization = ensure_review_organization_contact(
        account_request=account_request,
        payload=payload,
    )
    referent = ensure_review_recipient_referent(
        organization=organization,
        payload=payload,
    )
    destination = resolve_review_destination(payload)
    allowed_shipper_contacts = resolve_allowed_shipper_contacts(payload)
    result = update_runtime_recipient_shared_profile(
        organization=organization,
        referent=referent,
        destination=destination,
        allowed_shipper_contacts=allowed_shipper_contacts,
        is_correspondent=False,
        is_active=True,
    )

    grant, _created = PortalAccessGrant.objects.get_or_create(
        user=user,
        role=PortalAccessRole.RECIPIENT_ADMIN,
        recipient_organization=result.recipient_organization,
        defaults={
            "is_active": True,
            "created_by": request_user,
            "reviewed_by": request_user,
            "reviewed_at": account_request.reviewed_at,
        },
    )
    grant_update_fields = []
    if not grant.is_active:
        grant.is_active = True
        grant_update_fields.append("is_active")
    if grant.reviewed_by_id != getattr(request_user, "id", None):
        grant.reviewed_by = request_user
        grant_update_fields.append("reviewed_by")
    if grant.reviewed_at != account_request.reviewed_at:
        grant.reviewed_at = account_request.reviewed_at
        grant_update_fields.append("reviewed_at")
    if grant.created_by_id is None and getattr(request_user, "id", None):
        grant.created_by = request_user
        grant_update_fields.append("created_by")
    if grant_update_fields:
        grant.save(update_fields=grant_update_fields)

    ensure_default_shipper_links_for_recipient_organization_id(result.recipient_organization.id)
    return organization
