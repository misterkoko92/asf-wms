from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from contacts.models import Contact, ContactAddress, ContactType
from wms.document_scan import DocumentScanStatus
from wms.document_scan_queue import queue_document_scan
from wms.models import (
    AssociationRecipient,
    DocumentReviewStatus,
    RecipientProductPreference,
    RecipientStructureDocument,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from wms.parties.projections import (
    refresh_legacy_association_recipient_projection,
    refresh_legacy_association_recipient_projections_for_runtime,
)
from wms.parties.sync import (
    resolve_portal_recipient_party_contact as resolve_portal_recipient_party_contact_runtime,
)
from wms.parties.sync import sync_portal_recipient_graph
from wms.shipment_party_setup import (
    ensure_authorized_recipient_contact,
    ensure_shipment_recipient_link,
    ensure_shipment_shipper,
)

PENDING_SCAN_MESSAGE = "Scan antivirus en cours."


@dataclass(frozen=True)
class RecipientSharedProfileResult:
    synced_contact: object
    shipper: ShipmentShipper
    recipient_organization: ShipmentRecipientOrganization
    shipment_contact: ShipmentRecipientContact
    link: ShipmentShipperRecipientLink
    legacy_projection: AssociationRecipient | None = None


@dataclass(frozen=True)
class RuntimeRecipientSharedProfileResult:
    recipient_organization: ShipmentRecipientOrganization
    shipment_contact: ShipmentRecipientContact
    refreshed_legacy_projections: list[AssociationRecipient]


@dataclass(frozen=True)
class RuntimeRecipientProfileResult:
    recipient_organization: ShipmentRecipientOrganization
    shipment_contact: ShipmentRecipientContact
    refreshed_legacy_projections: list[AssociationRecipient]
    uploaded_documents: list[RecipientStructureDocument]


def _build_projection_candidate(
    *,
    association_contact,
    destination,
    structure_name="",
    structure_asf_id="",
    contact_title="",
    contact_first_name="",
    contact_last_name="",
    emails="",
    phones="",
    address_line1="",
    address_line2="",
    postal_code="",
    city="",
    country="France",
    legal_form="",
    beneficiary_count=None,
    notes="",
    notify_deliveries=False,
    is_delivery_contact=False,
    is_active=True,
    legacy_projection=None,
):
    projection = legacy_projection or AssociationRecipient(
        association_contact=association_contact,
    )
    projection.association_contact = association_contact
    projection.destination = destination
    projection.structure_name = (structure_name or "").strip()
    projection.name = projection.structure_name or "Destinataire"
    projection.contact_title = (contact_title or "").strip()
    projection.contact_first_name = (contact_first_name or "").strip()
    projection.contact_last_name = (contact_last_name or "").strip()
    projection.emails = (emails or "").strip()
    projection.phones = (phones or "").strip()
    projection.address_line1 = (address_line1 or "").strip()
    projection.address_line2 = (address_line2 or "").strip()
    projection.postal_code = (postal_code or "").strip()
    projection.city = (city or "").strip()
    projection.country = (country or "France").strip()
    projection.legal_form = legal_form or ""
    projection.beneficiary_count = beneficiary_count
    projection.notes = (notes or "").strip()
    projection.notify_deliveries = bool(notify_deliveries)
    projection.is_delivery_contact = bool(is_delivery_contact)
    projection.is_active = bool(is_active)
    projection.structure_asf_id = (structure_asf_id or "").strip()
    if legacy_projection is not None and legacy_projection.synced_contact_id:
        projection.synced_contact = legacy_projection.synced_contact
    projection._normalize_legacy_fields()
    return projection


def _seed_projection_candidate_synced_contact(*, projection_candidate, prefer_existing_structure):
    if not prefer_existing_structure or getattr(projection_candidate, "synced_contact_id", None):
        return projection_candidate
    structure_asf_id = str(getattr(projection_candidate, "structure_asf_id", "") or "").strip()
    if structure_asf_id:
        matching_contact = (
            Contact.objects.filter(
                contact_type=ContactType.ORGANIZATION,
                is_active=True,
                asf_id=structure_asf_id,
            )
            .only("id")
            .first()
        )
        if matching_contact is not None:
            projection_candidate.synced_contact_id = matching_contact.id
            return projection_candidate

    structure_name = (projection_candidate.structure_name or "").strip()
    destination = getattr(projection_candidate, "destination", None)
    if not structure_name or destination is None:
        return projection_candidate

    matching_organization_ids = list(
        ShipmentRecipientOrganization.objects.filter(
            organization__contact_type=ContactType.ORGANIZATION,
            organization__is_active=True,
            organization__name__iexact=structure_name,
        )
        .order_by("organization_id")
        .values_list("organization_id", flat=True)
        .distinct()[:2]
    )
    if len(matching_organization_ids) == 1:
        projection_candidate.synced_contact_id = matching_organization_ids[0]
    return projection_candidate


def create_or_link_shipper_recipient(
    *,
    association_contact,
    recipient_organization,
    shipment_contact,
    is_active=True,
    set_as_default=True,
):
    shipper = ensure_shipment_shipper(association_contact)
    link = ensure_shipment_recipient_link(
        shipper=shipper,
        recipient_organization=recipient_organization,
    )
    ensure_authorized_recipient_contact(
        link=link,
        recipient_contact=shipment_contact,
        is_active=bool(is_active),
        set_as_default=set_as_default,
    )
    return shipper, link


def update_recipient_shared_profile(
    *,
    association_contact,
    destination,
    structure_name="",
    structure_asf_id="",
    contact_title="",
    contact_first_name="",
    contact_last_name="",
    emails="",
    phones="",
    address_line1="",
    address_line2="",
    postal_code="",
    city="",
    country="France",
    legal_form="",
    beneficiary_count=None,
    notes="",
    notify_deliveries=False,
    is_delivery_contact=False,
    is_active=True,
    persist_projection=True,
    legacy_projection=None,
    prefer_existing_structure=True,
    set_as_default=True,
):
    projection_candidate = _build_projection_candidate(
        association_contact=association_contact,
        destination=destination,
        structure_name=structure_name,
        structure_asf_id=structure_asf_id,
        contact_title=contact_title,
        contact_first_name=contact_first_name,
        contact_last_name=contact_last_name,
        emails=emails,
        phones=phones,
        address_line1=address_line1,
        address_line2=address_line2,
        postal_code=postal_code,
        city=city,
        country=country,
        legal_form=legal_form,
        beneficiary_count=beneficiary_count,
        notes=notes,
        notify_deliveries=notify_deliveries,
        is_delivery_contact=is_delivery_contact,
        is_active=is_active,
        legacy_projection=legacy_projection,
    )
    projection_candidate = _seed_projection_candidate_synced_contact(
        projection_candidate=projection_candidate,
        prefer_existing_structure=prefer_existing_structure,
    )

    with transaction.atomic():
        result = sync_portal_recipient_graph(
            projection_candidate,
            set_as_default=set_as_default,
            prefer_existing_structure=prefer_existing_structure,
        )
        if result is None:
            raise ValueError("Recipient shared profile sync returned no runtime result.")

        legacy_projection_instance = None
        if persist_projection:
            legacy_projection_instance = refresh_legacy_association_recipient_projection(
                projection=legacy_projection,
                association_contact=association_contact,
                synced_contact=result["synced_contact"],
                recipient_organization=result["recipient_organization"],
                shipment_contact=result["shipment_contact"],
                structure_name=projection_candidate.structure_name,
                contact_title=projection_candidate.contact_title,
                contact_first_name=projection_candidate.contact_first_name,
                contact_last_name=projection_candidate.contact_last_name,
                emails=projection_candidate.emails,
                phones=projection_candidate.phones,
                address_line1=projection_candidate.address_line1,
                address_line2=projection_candidate.address_line2,
                postal_code=projection_candidate.postal_code,
                city=projection_candidate.city,
                country=projection_candidate.country,
                legal_form=projection_candidate.legal_form,
                beneficiary_count=projection_candidate.beneficiary_count,
                notes=projection_candidate.notes,
                notify_deliveries=projection_candidate.notify_deliveries,
                is_delivery_contact=projection_candidate.is_delivery_contact,
                is_active=projection_candidate.is_active,
            )

        return RecipientSharedProfileResult(
            synced_contact=result["synced_contact"],
            shipper=result["shipper"],
            recipient_organization=result["recipient_organization"],
            shipment_contact=result["shipment_contact"],
            link=result["link"],
            legacy_projection=legacy_projection_instance,
        )


def upsert_recipient_structure_documents(
    *,
    contact,
    files_by_type,
    uploaded_by=None,
    queue_scan=False,
):
    if contact is None:
        return []

    uploaded_user = uploaded_by if getattr(uploaded_by, "is_authenticated", False) else None
    documents = []
    for doc_type, uploaded in (files_by_type or {}).items():
        if not uploaded:
            continue
        document, _created = RecipientStructureDocument.objects.update_or_create(
            contact=contact,
            doc_type=doc_type,
            defaults={
                "status": DocumentReviewStatus.PENDING,
                "file": uploaded,
                "scan_status": DocumentScanStatus.PENDING,
                "scan_message": PENDING_SCAN_MESSAGE,
                "scan_updated_at": None,
                "uploaded_by": uploaded_user,
                "reviewed_by": None,
                "reviewed_at": None,
            },
        )
        if queue_scan:
            queue_document_scan(document)
        documents.append(document)
    return documents


def save_recipient_product_preference(
    *,
    recipient_organization,
    product=None,
    category=None,
    status,
    quantity_target=None,
    period_unit="",
    notes="",
    source="",
    user=None,
):
    preference = None
    if product is not None:
        preference = recipient_organization.product_preferences.filter(product=product).first()
    elif category is not None:
        preference = recipient_organization.product_preferences.filter(category=category).first()

    if preference is None:
        preference = RecipientProductPreference(
            recipient_organization=recipient_organization,
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )

    preference.product = product
    preference.category = category
    preference.status = status
    preference.quantity_target = quantity_target
    preference.period_unit = period_unit or ""
    preference.notes = notes or ""
    preference.source = source or preference.source
    preference.updated_by = user if getattr(user, "is_authenticated", False) else None
    preference.full_clean()
    preference.save()
    return preference


def update_runtime_recipient_shared_profile(
    *,
    organization,
    referent,
    destination,
    allowed_shipper_contacts=None,
    is_correspondent=False,
    is_active=True,
    validation_status=ShipmentValidationStatus.VALIDATED,
    refresh_legacy_projections=True,
):
    with transaction.atomic():
        recipient_organization, _created = ShipmentRecipientOrganization.objects.update_or_create(
            organization=organization,
            destination=destination,
            defaults={
                "validation_status": validation_status,
                "is_correspondent": is_correspondent,
                "is_active": bool(is_active),
            },
        )
        shipment_contact, _created = ShipmentRecipientContact.objects.update_or_create(
            recipient_organization=recipient_organization,
            contact=referent,
            defaults={"is_active": bool(is_active)},
        )

        if is_correspondent:
            ShipmentRecipientOrganization.objects.filter(
                destination=destination,
                is_correspondent=True,
            ).exclude(pk=recipient_organization.pk).update(is_correspondent=False)
            destination.correspondent_contact = referent
            destination.save(update_fields=["correspondent_contact"])
        else:
            for shipper_contact in allowed_shipper_contacts or []:
                shipper = ensure_shipment_shipper(shipper_contact)
                link = ensure_shipment_recipient_link(
                    shipper=shipper,
                    recipient_organization=recipient_organization,
                )
                ensure_authorized_recipient_contact(
                    link=link,
                    recipient_contact=shipment_contact,
                    is_active=bool(is_active),
                    set_as_default=True,
                )

        refreshed_legacy_projections = []
        if refresh_legacy_projections:
            refreshed_legacy_projections = (
                refresh_legacy_association_recipient_projections_for_runtime(
                    recipient_organization=recipient_organization,
                    shipment_contact=shipment_contact,
                )
            )

        return RuntimeRecipientSharedProfileResult(
            recipient_organization=recipient_organization,
            shipment_contact=shipment_contact,
            refreshed_legacy_projections=refreshed_legacy_projections,
        )


def _join_multi_values(values):
    return "; ".join(value for value in values if value)


def _upsert_runtime_recipient_profile_address(
    *,
    organization,
    address_line1="",
    address_line2="",
    postal_code="",
    city="",
    country="France",
):
    address = (
        organization.addresses.filter(is_default=True).first() or organization.addresses.first()
    )
    if address is None:
        address = ContactAddress(contact=organization, is_default=True)
    address.address_line1 = address_line1
    address.address_line2 = address_line2
    address.postal_code = postal_code
    address.city = city
    address.country = (country or "France").strip() or "France"
    address.is_default = True
    address.save()
    return address


def _upsert_runtime_recipient_profile_contact(
    *,
    recipient_organization,
    structure_name="",
    contact_title="",
    contact_first_name="",
    contact_last_name="",
    email_values=None,
    phone_values=None,
):
    shipment_contact = (
        recipient_organization.recipient_contacts.select_related("contact")
        .order_by("-is_active", "id")
        .first()
    )
    contact = shipment_contact.contact if shipment_contact is not None else None
    if contact is None:
        contact = Contact(
            contact_type=ContactType.PERSON,
            organization=recipient_organization.organization,
            is_active=True,
        )

    emails = list(email_values or [])
    phones = list(phone_values or [])
    contact.contact_type = ContactType.PERSON
    contact.organization = recipient_organization.organization
    contact.title = contact_title
    contact.first_name = contact_first_name
    contact.last_name = contact_last_name
    full_name = " ".join(part for part in [contact.first_name, contact.last_name] if part).strip()
    contact.name = (
        full_name
        or contact.name
        or (structure_name or "").strip()
        or recipient_organization.organization.name
        or "Referent destinataire"
    )
    contact.email = emails[0] if emails else ""
    contact.email2 = emails[1] if len(emails) > 1 else ""
    contact.phone = phones[0] if phones else ""
    contact.phone2 = phones[1] if len(phones) > 1 else ""
    contact.is_active = True
    contact.save()

    if shipment_contact is None:
        shipment_contact = recipient_organization.recipient_contacts.create(
            contact=contact,
            is_active=True,
        )
    else:
        shipment_contact.contact = contact
        shipment_contact.is_active = True
        shipment_contact.save(update_fields=["contact", "is_active"])
    return shipment_contact


def update_runtime_recipient_profile(
    *,
    recipient_organization,
    structure_name="",
    contact_title="",
    contact_first_name="",
    contact_last_name="",
    email_values=None,
    phone_values=None,
    address_line1="",
    address_line2="",
    postal_code="",
    city="",
    country="France",
    legal_form="",
    beneficiary_count=None,
    notes="",
    notify_deliveries=False,
    is_delivery_contact=False,
    uploaded_by=None,
    files_by_type=None,
    queue_scan=True,
):
    with transaction.atomic():
        organization = recipient_organization.organization
        organization.name = (structure_name or "").strip()
        organization.legal_form = legal_form or ""
        organization.beneficiary_count = beneficiary_count
        organization.notes = (notes or "").strip()
        organization.is_active = True
        organization.save(
            update_fields=[
                "name",
                "legal_form",
                "beneficiary_count",
                "notes",
                "is_active",
            ]
        )
        _upsert_runtime_recipient_profile_address(
            organization=organization,
            address_line1=(address_line1 or "").strip(),
            address_line2=(address_line2 or "").strip(),
            postal_code=(postal_code or "").strip(),
            city=(city or "").strip(),
            country=(country or "").strip() or "France",
        )
        shipment_contact = _upsert_runtime_recipient_profile_contact(
            recipient_organization=recipient_organization,
            structure_name=(structure_name or "").strip(),
            contact_title=(contact_title or "").strip(),
            contact_first_name=(contact_first_name or "").strip(),
            contact_last_name=(contact_last_name or "").strip(),
            email_values=email_values or [],
            phone_values=phone_values or [],
        )
        allowed_shipper_contacts = [
            link.shipper.organization
            for link in recipient_organization.shipper_links.filter(
                is_active=True,
                shipper__is_active=True,
                shipper__organization__is_active=True,
            ).select_related("shipper__organization")
        ]
        runtime_result = update_runtime_recipient_shared_profile(
            organization=organization,
            referent=shipment_contact.contact,
            destination=recipient_organization.destination,
            allowed_shipper_contacts=allowed_shipper_contacts,
            is_correspondent=recipient_organization.is_correspondent,
            is_active=recipient_organization.is_active,
            validation_status=recipient_organization.validation_status,
            refresh_legacy_projections=False,
        )

        refreshed_legacy_projections = []
        projections = AssociationRecipient.objects.filter(
            synced_contact=organization,
            destination=recipient_organization.destination,
        ).select_related("association_contact")
        emails = _join_multi_values(email_values or [])
        phones = _join_multi_values(phone_values or [])
        for projection in projections:
            refreshed_legacy_projections.append(
                refresh_legacy_association_recipient_projection(
                    projection=projection,
                    association_contact=projection.association_contact,
                    synced_contact=organization,
                    recipient_organization=runtime_result.recipient_organization,
                    shipment_contact=runtime_result.shipment_contact,
                    structure_name=(structure_name or "").strip(),
                    contact_title=(contact_title or "").strip(),
                    contact_first_name=(contact_first_name or "").strip(),
                    contact_last_name=(contact_last_name or "").strip(),
                    emails=emails,
                    phones=phones,
                    address_line1=(address_line1 or "").strip(),
                    address_line2=(address_line2 or "").strip(),
                    postal_code=(postal_code or "").strip(),
                    city=(city or "").strip(),
                    country=(country or "").strip() or "France",
                    legal_form=legal_form or "",
                    beneficiary_count=beneficiary_count,
                    notes=(notes or "").strip(),
                    notify_deliveries=bool(notify_deliveries),
                    is_delivery_contact=bool(is_delivery_contact),
                    is_active=projection.is_active,
                )
            )

        uploaded_documents = upsert_recipient_structure_documents(
            contact=organization,
            files_by_type=files_by_type or {},
            uploaded_by=uploaded_by,
            queue_scan=queue_scan,
        )
        return RuntimeRecipientProfileResult(
            recipient_organization=runtime_result.recipient_organization,
            shipment_contact=runtime_result.shipment_contact,
            refreshed_legacy_projections=refreshed_legacy_projections,
            uploaded_documents=uploaded_documents,
        )


def sync_portal_recipient(
    *,
    recipient,
    set_as_default=True,
    prefer_existing_structure=True,
):
    result = sync_portal_recipient_graph(
        recipient,
        set_as_default=set_as_default,
        prefer_existing_structure=prefer_existing_structure,
    )
    if result is None:
        return {}

    synced_contact = result["synced_contact"]
    shipper = result["shipper"]
    recipient_organization = result["recipient_organization"]
    shipment_contact = result["shipment_contact"]
    link = result["link"]
    return {
        "synced_contact": synced_contact,
        "synced_contact_id": synced_contact.id,
        "shipper": shipper,
        "shipper_id": shipper.id,
        "recipient_organization": recipient_organization,
        "recipient_organization_id": recipient_organization.id,
        "shipment_contact": shipment_contact,
        "shipment_contact_id": shipment_contact.id,
        "link": link,
        "link_id": link.id,
    }


def resolve_portal_recipient_party_contact(recipient):
    return resolve_portal_recipient_party_contact_runtime(recipient)
