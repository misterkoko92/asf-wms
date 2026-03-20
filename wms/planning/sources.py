from django.utils.text import slugify

from contacts.models import Contact
from wms.models import Flight, Shipment, ShipmentStatus, VolunteerProfile
from wms.shipment_party_rules import build_party_contact_reference, normalize_party_contact_to_org
from wms.shipment_party_snapshot import build_shipment_party_label

ELIGIBLE_SHIPMENT_STATUSES = (
    ShipmentStatus.PACKED,
    ShipmentStatus.PLANNED,
)


def _normalized_text(value):
    return str(value or "").strip()


def _shipment_party_snapshot_entry(shipment, party_key):
    snapshot = getattr(shipment, "party_snapshot", None) or {}
    if not isinstance(snapshot, dict):
        return {}
    entry = snapshot.get(party_key) or {}
    return entry if isinstance(entry, dict) else {}


def _snapshot_reference(entry, *, prefer):
    if not entry:
        return None
    preferred = entry.get(prefer) or {}
    alternate_key = "contact" if prefer == "organization" else "organization"
    alternate = entry.get(alternate_key) or {}
    source = preferred if isinstance(preferred, dict) else {}
    if not source.get("contact_id") and not source.get("contact_name"):
        source = alternate if isinstance(alternate, dict) else {}
    if not source:
        return None
    reference = dict(source)
    label = _normalized_text(entry.get("label"))
    if label:
        reference["contact_name"] = label
    return reference


def _party_label(contact, *, fallback_name):
    return build_shipment_party_label(contact, fallback_name=_normalized_text(fallback_name))


def _fallback_reference(contact, *, fallback_name):
    normalized_contact = normalize_party_contact_to_org(contact)
    label = _party_label(contact, fallback_name=fallback_name)
    reference = build_party_contact_reference(normalized_contact, fallback_name=label)
    reference["contact_name"] = label
    return reference


def _get_recipe_scope(run):
    if run.flight_batch_id is None or run.flight_batch.source != "recipe":
        return None
    marker = str(run.log_excerpt or "").strip()
    if not marker.startswith("recipe:"):
        return None
    scenario_slug = slugify(marker.split(":", 1)[1]).strip("-")
    if not scenario_slug:
        return None
    base_slug = scenario_slug.removesuffix("-recipe")
    return {
        "shipment_reference_prefix": f"RECIPE-{base_slug.upper()}",
        "user_prefix": f"recipe-{scenario_slug}-",
    }


def get_run_shipments(run):
    queryset = (
        Shipment.objects.select_related(
            "destination",
            "destination__correspondent_contact",
            "shipper_contact_ref",
            "recipient_contact_ref",
            "correspondent_contact_ref",
        )
        .filter(
            status__in=ELIGIBLE_SHIPMENT_STATUSES,
            ready_at__date__gte=run.week_start,
            ready_at__date__lte=run.week_end,
            archived_at__isnull=True,
        )
        .order_by("ready_at", "reference", "id")
    )
    recipe_scope = _get_recipe_scope(run)
    if recipe_scope is not None:
        queryset = queryset.filter(reference__startswith=recipe_scope["shipment_reference_prefix"])
    return queryset


def build_shipper_reference(shipment):
    snapshot_reference = _snapshot_reference(
        _shipment_party_snapshot_entry(shipment, "shipper"),
        prefer="organization",
    )
    if snapshot_reference is not None:
        contact_id = snapshot_reference.get("contact_id")
        contact = Contact.objects.filter(pk=contact_id).first() if contact_id else None
    else:
        contact = normalize_party_contact_to_org(shipment.shipper_contact_ref)
        snapshot_reference = _fallback_reference(
            shipment.shipper_contact_ref,
            fallback_name=shipment.shipper_name,
        )

    reference = dict(snapshot_reference)
    association_profile = (
        contact.association_profiles.prefetch_related("portal_contacts").order_by("id").first()
        if contact is not None
        else None
    )
    notification_emails = (
        association_profile.get_notification_emails() if association_profile else []
    )
    if notification_emails:
        reference["notification_emails"] = notification_emails
    reference["association_profile_id"] = association_profile.pk if association_profile else None
    return reference


def build_recipient_reference(shipment):
    snapshot_reference = _snapshot_reference(
        _shipment_party_snapshot_entry(shipment, "recipient"),
        prefer="organization",
    )
    if snapshot_reference is not None:
        return snapshot_reference
    return _fallback_reference(
        shipment.recipient_contact_ref,
        fallback_name=shipment.recipient_name,
    )


def build_correspondent_reference(shipment):
    snapshot_reference = _snapshot_reference(
        _shipment_party_snapshot_entry(shipment, "correspondent"),
        prefer="organization",
    )
    if snapshot_reference is not None:
        return snapshot_reference
    contact = shipment.correspondent_contact_ref or getattr(
        shipment.destination, "correspondent_contact", None
    )
    fallback_name = shipment.correspondent_name or getattr(contact, "name", "") or ""
    return _fallback_reference(contact, fallback_name=fallback_name)


def get_run_volunteers(run):
    queryset = (
        VolunteerProfile.objects.select_related("user", "contact")
        .filter(is_active=True)
        .order_by("volunteer_id", "id")
    )
    recipe_scope = _get_recipe_scope(run)
    if recipe_scope is not None:
        queryset = queryset.filter(user__username__startswith=recipe_scope["user_prefix"])
    return queryset


def get_run_flights(run):
    if run.flight_batch_id is None:
        return Flight.objects.none()
    return (
        Flight.objects.select_related("destination")
        .filter(
            batch=run.flight_batch,
            departure_date__gte=run.week_start,
            departure_date__lte=run.week_end,
        )
        .order_by("departure_date", "flight_number", "id")
    )
