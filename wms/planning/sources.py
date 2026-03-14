from django.utils.text import slugify

from wms.models import Flight, Shipment, ShipmentStatus, VolunteerProfile
from wms.shipment_party_rules import build_party_contact_reference, normalize_party_contact_to_org

ELIGIBLE_SHIPMENT_STATUSES = (
    ShipmentStatus.PACKED,
    ShipmentStatus.PLANNED,
)


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
    contact = normalize_party_contact_to_org(shipment.shipper_contact_ref)
    reference = build_party_contact_reference(contact, fallback_name=shipment.shipper_name)
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
    return build_party_contact_reference(
        normalize_party_contact_to_org(shipment.recipient_contact_ref),
        fallback_name=shipment.recipient_name,
    )


def build_correspondent_reference(shipment):
    contact = shipment.correspondent_contact_ref or getattr(
        shipment.destination, "correspondent_contact", None
    )
    normalized_contact = normalize_party_contact_to_org(contact)
    fallback_name = shipment.correspondent_name or getattr(contact, "name", "") or ""
    return build_party_contact_reference(normalized_contact, fallback_name=fallback_name)


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
