from wms.models import Flight, Shipment, ShipmentStatus, VolunteerProfile

ELIGIBLE_SHIPMENT_STATUSES = (
    ShipmentStatus.PACKED,
    ShipmentStatus.PLANNED,
)


def get_run_shipments(run):
    return (
        Shipment.objects.select_related("destination", "shipper_contact_ref")
        .filter(
            status__in=ELIGIBLE_SHIPMENT_STATUSES,
            ready_at__date__gte=run.week_start,
            ready_at__date__lte=run.week_end,
            archived_at__isnull=True,
        )
        .order_by("ready_at", "reference", "id")
    )


def build_shipper_reference(shipment):
    contact = shipment.shipper_contact_ref
    if contact is None:
        return {}

    association_profile = (
        contact.association_profiles.prefetch_related("portal_contacts").order_by("id").first()
    )
    notification_emails = (
        association_profile.get_notification_emails() if association_profile else []
    )

    return {
        "contact_id": contact.pk,
        "contact_name": contact.name,
        "association_profile_id": association_profile.pk if association_profile else None,
        "notification_emails": notification_emails,
    }


def get_run_volunteers(run):
    return (
        VolunteerProfile.objects.select_related("user", "contact")
        .filter(is_active=True)
        .order_by("volunteer_id", "id")
    )


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
