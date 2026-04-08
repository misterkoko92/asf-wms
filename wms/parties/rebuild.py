from __future__ import annotations

from django.db import transaction
from django.db.models import Count

from wms.models import (
    AssociationProfile,
    AssociationRecipient,
    PortalAccessGrant,
    PortalAccessRole,
    RecipientProductPreference,
    ShipmentPreferenceOverride,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from wms.parties.merge import _merge_authorized_contacts, _merge_shipper_links
from wms.parties.projections import refresh_legacy_association_recipient_projection
from wms.shipment_party_registry import default_recipient_contact_for_link


def _duplicate_recipient_organization_scopes():
    duplicate_rows = list(
        ShipmentRecipientOrganization.objects.values(
            "organization_id",
            "organization__name",
            "destination_id",
            "destination__city",
            "destination__iata_code",
            "destination__country",
        )
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("destination__city", "organization__name", "organization_id", "destination_id")
    )
    duplicates = []
    for row in duplicate_rows:
        recipient_organization_ids = list(
            ShipmentRecipientOrganization.objects.filter(
                organization_id=row["organization_id"],
                destination_id=row["destination_id"],
            )
            .order_by("-is_active", "-is_correspondent", "id")
            .values_list("id", flat=True)
        )
        duplicates.append(
            {
                "organization_id": row["organization_id"],
                "organization_name": row["organization__name"] or "",
                "destination_id": row["destination_id"],
                "destination_label": (
                    f"{row['destination__city']} ({row['destination__iata_code']})"
                    f" - {row['destination__country']}"
                ),
                "recipient_organization_ids": recipient_organization_ids,
            }
        )
    return duplicates


def _ensure_shipper_portal_grants(*, apply: bool) -> int:
    created_count = 0
    profiles = list(
        AssociationProfile.objects.select_related("user", "contact")
        .filter(user__isnull=False, contact__isnull=False)
        .order_by("id")
    )
    for profile in profiles:
        shipper = (
            ShipmentShipper.objects.filter(
                organization=profile.contact,
                is_active=True,
            )
            .order_by("id")
            .first()
        )
        if shipper is None:
            continue
        existing = (
            PortalAccessGrant.objects.filter(
                user=profile.user,
                role=PortalAccessRole.SHIPPER_ADMIN,
                shipper=shipper,
            )
            .order_by("id")
            .first()
        )
        if existing is None:
            created_count += 1
            if apply:
                PortalAccessGrant.objects.create(
                    user=profile.user,
                    role=PortalAccessRole.SHIPPER_ADMIN,
                    shipper=shipper,
                )
        elif apply and not existing.is_active:
            existing.is_active = True
            existing.save(update_fields=["is_active"])
    return created_count


def _merge_duplicate_recipient_contacts(*, source, target):
    for source_recipient_contact in (
        ShipmentRecipientContact.objects.filter(recipient_organization=source)
        .select_related("contact")
        .order_by("id")
    ):
        target_recipient_contact = (
            ShipmentRecipientContact.objects.filter(
                recipient_organization=target,
                contact=source_recipient_contact.contact,
            )
            .exclude(pk=source_recipient_contact.pk)
            .first()
        )
        if target_recipient_contact is None:
            source_recipient_contact.recipient_organization = target
            source_recipient_contact.save(update_fields=["recipient_organization"])
            continue

        if source_recipient_contact.is_active and not target_recipient_contact.is_active:
            target_recipient_contact.is_active = True
            target_recipient_contact.save(update_fields=["is_active"])
        _merge_authorized_contacts(
            source_recipient_contact=source_recipient_contact,
            target_recipient_contact=target_recipient_contact,
        )
        source_recipient_contact.delete()


def _merge_duplicate_shipper_links(*, source, target):
    for source_link in source.shipper_links.select_related("shipper").order_by("id"):
        target_link = (
            source_link.shipper.recipient_links.filter(
                recipient_organization=target,
            )
            .exclude(pk=source_link.pk)
            .first()
        )
        if target_link is None:
            source_link.recipient_organization = target
            source_link.save(update_fields=["recipient_organization"])
            continue
        if source_link.is_active and not target_link.is_active:
            target_link.is_active = True
            target_link.save(update_fields=["is_active"])
        _merge_shipper_links(source_link=source_link, target_link=target_link)


def _merge_duplicate_product_preferences(*, source, target):
    for preference in RecipientProductPreference.objects.filter(
        recipient_organization=source
    ).order_by("id"):
        if preference.product_id is not None:
            existing = target.product_preferences.filter(product_id=preference.product_id).first()
        else:
            existing = target.product_preferences.filter(category_id=preference.category_id).first()

        if existing is None:
            preference.recipient_organization = target
            preference.save(update_fields=["recipient_organization"])
            continue

        updated_fields = []
        if existing.quantity_target is None and preference.quantity_target is not None:
            existing.quantity_target = preference.quantity_target
            updated_fields.append("quantity_target")
        if not existing.period_unit and preference.period_unit:
            existing.period_unit = preference.period_unit
            updated_fields.append("period_unit")
        if not existing.notes and preference.notes:
            existing.notes = preference.notes
            updated_fields.append("notes")
        if not existing.source and preference.source:
            existing.source = preference.source
            updated_fields.append("source")
        if updated_fields:
            existing.save(update_fields=updated_fields)
        preference.delete()


def _reassign_recipient_grants(*, source, target) -> int:
    reassigned_count = 0
    for grant in PortalAccessGrant.objects.filter(recipient_organization=source).order_by("id"):
        existing = (
            PortalAccessGrant.objects.filter(
                user=grant.user,
                role=grant.role,
                recipient_organization=target,
            )
            .exclude(pk=grant.pk)
            .first()
        )
        if existing is None:
            grant.recipient_organization = target
            grant.save(update_fields=["recipient_organization"])
            reassigned_count += 1
            continue

        updated_fields = []
        if grant.is_active and not existing.is_active:
            existing.is_active = True
            updated_fields.append("is_active")
        if existing.reviewed_at is None and grant.reviewed_at is not None:
            existing.reviewed_at = grant.reviewed_at
            updated_fields.append("reviewed_at")
        if existing.reviewed_by_id is None and grant.reviewed_by_id is not None:
            existing.reviewed_by = grant.reviewed_by
            updated_fields.append("reviewed_by")
        if updated_fields:
            existing.save(update_fields=updated_fields)
        grant.delete()
        reassigned_count += 1
    return reassigned_count


def _merge_duplicate_recipient_organization_scopes(duplicate_scopes):
    merged_count = 0
    recipient_grants_reassigned = 0
    for scope in duplicate_scopes:
        recipient_organization_ids = scope["recipient_organization_ids"]
        if len(recipient_organization_ids) < 2:
            continue

        target = ShipmentRecipientOrganization.objects.get(pk=recipient_organization_ids[0])
        sources = list(
            ShipmentRecipientOrganization.objects.filter(
                id__in=recipient_organization_ids[1:]
            ).order_by("id")
        )
        for source in sources:
            updated_fields = []
            if source.is_correspondent and not target.is_correspondent:
                target.is_correspondent = True
                updated_fields.append("is_correspondent")
            if source.is_active and not target.is_active:
                target.is_active = True
                updated_fields.append("is_active")
            if (
                source.validation_status == ShipmentValidationStatus.VALIDATED
                and target.validation_status != ShipmentValidationStatus.VALIDATED
            ):
                target.validation_status = ShipmentValidationStatus.VALIDATED
                updated_fields.append("validation_status")
            if updated_fields:
                target.save(update_fields=updated_fields)

            _merge_duplicate_recipient_contacts(source=source, target=target)
            _merge_duplicate_shipper_links(source=source, target=target)
            _merge_duplicate_product_preferences(source=source, target=target)
            ShipmentPreferenceOverride.objects.filter(recipient_organization=source).update(
                recipient_organization=target
            )
            recipient_grants_reassigned += _reassign_recipient_grants(
                source=source,
                target=target,
            )
            source.delete()
            merged_count += 1
    return merged_count, recipient_grants_reassigned


def _recipient_contact_for_projection(link):
    shipment_contact = default_recipient_contact_for_link(link)
    if shipment_contact is not None:
        return shipment_contact
    return (
        link.recipient_organization.recipient_contacts.filter(
            is_active=True,
            contact__is_active=True,
        )
        .select_related("contact")
        .order_by("id")
        .first()
    )


def _projection_candidate_for_link(link):
    projections = AssociationRecipient.objects.filter(
        association_contact=link.shipper.organization,
        destination=link.recipient_organization.destination,
    ).select_related("synced_contact")

    exact = (
        projections.filter(
            synced_contact=link.recipient_organization.organization,
        )
        .order_by("id")
        .first()
    )
    if exact is not None:
        return exact, True

    name_matches = list(
        projections.filter(
            structure_name__iexact=link.recipient_organization.organization.name or "",
        ).order_by("id")[:2]
    )
    if len(name_matches) == 1:
        return name_matches[0], True

    stale_matches = list(
        projections.filter(
            synced_contact__isnull=False,
            synced_contact__is_active=False,
        ).order_by("id")[:2]
    )
    if len(stale_matches) == 1:
        return stale_matches[0], True

    first_two = list(projections.order_by("id")[:2])
    if not first_two:
        return None, True
    if len(first_two) == 1:
        return first_two[0], True
    return None, False


def _refresh_legacy_projections(*, apply: bool) -> int:
    refreshed_count = 0
    links = list(
        ShipmentShipperRecipientLink.objects.filter(
            is_active=True,
            shipper__is_active=True,
            shipper__organization__is_active=True,
            recipient_organization__is_active=True,
            recipient_organization__organization__is_active=True,
        )
        .select_related(
            "shipper__organization",
            "recipient_organization__organization",
            "recipient_organization__destination",
        )
        .order_by("id")
    )
    for link in links:
        shipment_contact = _recipient_contact_for_projection(link)
        if shipment_contact is None:
            continue
        projection, can_refresh = _projection_candidate_for_link(link)
        if not can_refresh:
            continue
        refreshed_count += 1
        if not apply:
            continue

        organization = link.recipient_organization.organization
        address = organization.get_effective_address()
        refresh_legacy_association_recipient_projection(
            projection=projection,
            association_contact=link.shipper.organization,
            synced_contact=organization,
            recipient_organization=link.recipient_organization,
            shipment_contact=shipment_contact,
            structure_name=organization.name or "",
            contact_title=shipment_contact.contact.title or "",
            contact_first_name=shipment_contact.contact.first_name or "",
            contact_last_name=shipment_contact.contact.last_name or "",
            emails=shipment_contact.contact.email or organization.email or "",
            phones=shipment_contact.contact.phone or organization.phone or "",
            address_line1=getattr(address, "address_line1", ""),
            address_line2=getattr(address, "address_line2", ""),
            postal_code=getattr(address, "postal_code", ""),
            city=getattr(address, "city", ""),
            country=getattr(address, "country", "France"),
            legal_form=organization.legal_form or "",
            beneficiary_count=organization.beneficiary_count,
            notes=organization.notes or "",
            notify_deliveries=projection.notify_deliveries if projection is not None else False,
            is_delivery_contact=(
                projection.is_delivery_contact if projection is not None else False
            ),
            is_active=projection.is_active if projection is not None else True,
        )
    return refreshed_count


def rebuild_recipient_party_graph(*, apply: bool = False):
    duplicate_scopes = _duplicate_recipient_organization_scopes()
    summary = {
        "mode": "APPLY" if apply else "DRY RUN",
        "recipient_organizations_scanned": ShipmentRecipientOrganization.objects.count(),
        "duplicate_scopes": duplicate_scopes,
        "recipient_organizations_merged": 0,
        "shipper_grants_created": 0,
        "recipient_grants_reassigned": 0,
        "legacy_projections_refreshed": 0,
    }

    if not apply:
        summary["recipient_organizations_merged"] = sum(
            max(len(scope["recipient_organization_ids"]) - 1, 0) for scope in duplicate_scopes
        )
        summary["shipper_grants_created"] = _ensure_shipper_portal_grants(apply=False)
        summary["legacy_projections_refreshed"] = _refresh_legacy_projections(apply=False)
        return summary

    with transaction.atomic():
        (
            summary["recipient_organizations_merged"],
            summary["recipient_grants_reassigned"],
        ) = _merge_duplicate_recipient_organization_scopes(duplicate_scopes)
        summary["shipper_grants_created"] = _ensure_shipper_portal_grants(apply=True)
        summary["legacy_projections_refreshed"] = _refresh_legacy_projections(apply=True)
    return summary
