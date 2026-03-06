from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone

from contacts.models import Contact, ContactType
from contacts.querysets import contacts_with_tags
from contacts.tagging import TAG_SHIPPER

from . import models

ADMIN_ORGANIZATION_ROLES_REVIEW_URL_NAME = "wms_organization_roles_review"
ADMIN_ORGANIZATION_ROLES_REVIEW_TEMPLATE = "admin/wms/organization_roles_review.html"

ACTION_RESOLVE_BINDING = "resolve_binding"
ACTION_RESOLVE_WITHOUT_BINDING = "resolve_without_binding"


def get_organization_roles_review_urls(*, admin_site):
    def _view(request):
        return organization_roles_review_view(request=request, admin_site=admin_site)

    return [
        path(
            "wms/organization-roles-review/",
            admin_site.admin_view(_view),
            name=ADMIN_ORGANIZATION_ROLES_REVIEW_URL_NAME,
        )
    ]


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _active_org_contacts(queryset):
    return queryset.filter(
        contact_type=ContactType.ORGANIZATION,
        is_active=True,
    )


def _open_review_items_queryset():
    return (
        models.MigrationReviewItem.objects.filter(status=models.MigrationReviewItemStatus.OPEN)
        .select_related(
            "organization",
            "legacy_contact",
            "legacy_contact__organization",
        )
        .order_by("created_at", "id")
    )


def _resolve_recipient_organization(review_item: models.MigrationReviewItem):
    organization = review_item.organization
    if organization and organization.contact_type == ContactType.ORGANIZATION:
        return organization

    legacy_contact = review_item.legacy_contact
    if not legacy_contact:
        return None

    if legacy_contact.contact_type == ContactType.ORGANIZATION:
        return legacy_contact

    organization = legacy_contact.organization
    if organization and organization.contact_type == ContactType.ORGANIZATION:
        return organization
    return None


def _collect_destination_ids_for_contact(contact: Contact | None) -> set[int]:
    if not contact:
        return set()
    destination_ids = set(contact.destinations.values_list("id", flat=True))
    destination = contact.destination
    if destination:
        destination_ids.add(destination.pk)
    return destination_ids


def _collect_shipper_options(
    *,
    review_item: models.MigrationReviewItem,
    recipient_org: Contact | None,
):
    shipper_ids: set[int] = set()

    payload_shipper_id = _to_int((review_item.payload or {}).get("shipper_id"))
    if payload_shipper_id:
        shipper_ids.add(payload_shipper_id)

    if recipient_org:
        shipper_ids.update(
            _active_org_contacts(recipient_org.linked_shippers.all()).values_list("id", flat=True)
        )
        shipper_ids.update(
            models.RecipientBinding.objects.filter(recipient_org=recipient_org).values_list(
                "shipper_org_id", flat=True
            )
        )

    legacy_contact = review_item.legacy_contact
    if legacy_contact:
        shipper_ids.update(
            _active_org_contacts(legacy_contact.linked_shippers.all()).values_list("id", flat=True)
        )

    if shipper_ids:
        return list(
            Contact.objects.filter(
                pk__in=shipper_ids,
                contact_type=ContactType.ORGANIZATION,
                is_active=True,
            ).order_by("name")
        )

    # Fallback for manual review when no explicit legacy links are available.
    return list(_active_org_contacts(contacts_with_tags(TAG_SHIPPER)).order_by("name"))


def _collect_destination_options(
    *,
    review_item: models.MigrationReviewItem,
    recipient_org: Contact | None,
):
    destination_ids: set[int] = set()

    payload_destination_id = _to_int((review_item.payload or {}).get("destination_id"))
    if payload_destination_id:
        destination_ids.add(payload_destination_id)

    destination_ids.update(_collect_destination_ids_for_contact(recipient_org))
    destination_ids.update(_collect_destination_ids_for_contact(review_item.legacy_contact))

    if recipient_org:
        destination_ids.update(
            models.RecipientBinding.objects.filter(recipient_org=recipient_org).values_list(
                "destination_id", flat=True
            )
        )

    if destination_ids:
        return list(
            models.Destination.objects.filter(
                pk__in=destination_ids,
                is_active=True,
            ).order_by("city", "iata_code")
        )

    return list(models.Destination.objects.filter(is_active=True).order_by("city", "iata_code"))


def _latest_recipient_binding(recipient_org: Contact | None):
    if recipient_org is None:
        return None
    return (
        models.RecipientBinding.objects.filter(recipient_org=recipient_org, is_active=True)
        .select_related("shipper_org", "destination")
        .order_by("-valid_from", "-created_at", "-id")
        .first()
    )


def _suggest_shipper_id(
    *,
    review_item: models.MigrationReviewItem,
    recipient_org: Contact | None,
    shipper_options,
):
    option_ids = {contact.id for contact in shipper_options}
    if not option_ids:
        return None

    payload_shipper_id = _to_int((review_item.payload or {}).get("shipper_id"))
    if payload_shipper_id in option_ids:
        return payload_shipper_id

    latest_binding = _latest_recipient_binding(recipient_org)
    if latest_binding and latest_binding.shipper_org.pk in option_ids:
        return latest_binding.shipper_org.pk

    if recipient_org:
        linked_ids = list(
            _active_org_contacts(recipient_org.linked_shippers.all()).values_list("id", flat=True)
        )
        if len(linked_ids) == 1 and linked_ids[0] in option_ids:
            return linked_ids[0]

    if len(option_ids) == 1:
        return next(iter(option_ids))

    return None


def _suggest_destination_id(
    *,
    review_item: models.MigrationReviewItem,
    recipient_org: Contact | None,
    destination_options,
):
    option_ids = {destination.id for destination in destination_options}
    if not option_ids:
        return None

    payload_destination_id = _to_int((review_item.payload or {}).get("destination_id"))
    if payload_destination_id in option_ids:
        return payload_destination_id

    latest_binding = _latest_recipient_binding(recipient_org)
    if latest_binding and latest_binding.destination.pk in option_ids:
        return latest_binding.destination.pk

    legacy_contact = review_item.legacy_contact
    if (
        legacy_contact
        and legacy_contact.destination
        and legacy_contact.destination.pk in option_ids
    ):
        return legacy_contact.destination.pk

    if recipient_org and recipient_org.destination and recipient_org.destination.pk in option_ids:
        return recipient_org.destination.pk

    if len(option_ids) == 1:
        return next(iter(option_ids))

    return None


def _build_review_row(review_item: models.MigrationReviewItem):
    recipient_org = _resolve_recipient_organization(review_item)
    shipper_options = _collect_shipper_options(
        review_item=review_item,
        recipient_org=recipient_org,
    )
    destination_options = _collect_destination_options(
        review_item=review_item,
        recipient_org=recipient_org,
    )

    return {
        "item": review_item,
        "recipient_org": recipient_org,
        "shipper_options": shipper_options,
        "destination_options": destination_options,
        "suggested_shipper_id": _suggest_shipper_id(
            review_item=review_item,
            recipient_org=recipient_org,
            shipper_options=shipper_options,
        ),
        "suggested_destination_id": _suggest_destination_id(
            review_item=review_item,
            recipient_org=recipient_org,
            destination_options=destination_options,
        ),
    }


def _resolve_review_item(*, review_item, user, note):
    review_item.status = models.MigrationReviewItemStatus.RESOLVED
    review_item.resolved_by = user
    review_item.resolved_at = timezone.now()
    review_item.resolution_note = (note or "").strip()
    review_item.save(
        update_fields=[
            "status",
            "resolved_by",
            "resolved_at",
            "resolution_note",
            "updated_at",
        ]
    )


def _ensure_role_assignment(*, organization: Contact, role: str):
    assignment, _created = models.OrganizationRoleAssignment.objects.get_or_create(
        organization=organization,
        role=role,
        defaults={"is_active": True},
    )
    return assignment


def _handle_resolve_binding(*, request, review_item):
    if review_item.role != models.OrganizationRole.RECIPIENT:
        messages.error(
            request,
            "Ce type d'item ne supporte pas la creation de RecipientBinding.",
        )
        return

    recipient_org = _resolve_recipient_organization(review_item)
    if recipient_org is None:
        messages.error(
            request,
            "Impossible de determiner le destinataire a partir du contact legacy.",
        )
        return

    shipper_org_id = _to_int(request.POST.get("shipper_org_id"))
    destination_id = _to_int(request.POST.get("destination_id"))
    resolution_note = request.POST.get("resolution_note", "")

    shipper_org = Contact.objects.filter(
        pk=shipper_org_id,
        contact_type=ContactType.ORGANIZATION,
        is_active=True,
    ).first()
    if shipper_org is None:
        messages.error(request, "Selectionnez un expediteur valide.")
        return

    destination = models.Destination.objects.filter(
        pk=destination_id,
        is_active=True,
    ).first()
    if destination is None:
        messages.error(request, "Selectionnez une escale valide.")
        return

    with transaction.atomic():
        shipper_assignment = _ensure_role_assignment(
            organization=shipper_org,
            role=str(models.OrganizationRole.SHIPPER),
        )
        _ensure_role_assignment(
            organization=recipient_org,
            role=str(models.OrganizationRole.RECIPIENT),
        )
        models.ShipperScope.objects.get_or_create(
            role_assignment=shipper_assignment,
            destination=destination,
            defaults={
                "all_destinations": False,
                "is_active": True,
                "valid_from": timezone.now(),
            },
        )
        models.RecipientBinding.objects.get_or_create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
            is_active=True,
            defaults={"valid_from": timezone.now()},
        )
        _resolve_review_item(
            review_item=review_item,
            user=request.user,
            note=resolution_note,
        )

    messages.success(request, "Mapping destinataire valide et item resolu.")


def _handle_resolve_without_binding(*, request, review_item):
    _resolve_review_item(
        review_item=review_item,
        user=request.user,
        note=request.POST.get("resolution_note", ""),
    )
    messages.success(request, "Item de revue cloture sans mapping.")


def organization_roles_review_view(*, request, admin_site):
    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method == "POST":
        item_id = _to_int(request.POST.get("item_id"))
        action = request.POST.get("action")
        review_item = _open_review_items_queryset().filter(pk=item_id).first()
        if review_item is None:
            messages.error(request, "Item de revue introuvable ou deja resolu.")
        elif action == ACTION_RESOLVE_BINDING:
            _handle_resolve_binding(request=request, review_item=review_item)
        elif action == ACTION_RESOLVE_WITHOUT_BINDING:
            _handle_resolve_without_binding(request=request, review_item=review_item)
        else:
            messages.error(request, "Action de revue non supportee.")

        return redirect(reverse(f"admin:{ADMIN_ORGANIZATION_ROLES_REVIEW_URL_NAME}"))

    review_rows = [_build_review_row(item) for item in _open_review_items_queryset()]
    context = {
        **admin_site.each_context(request),
        "opts": models.MigrationReviewItem._meta,
        "title": "Revue migration des roles organisation",
        "open_items_count": len(review_rows),
        "review_items": review_rows,
    }
    return render(request, ADMIN_ORGANIZATION_ROLES_REVIEW_TEMPLATE, context)
