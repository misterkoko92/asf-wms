from django.db import transaction

from wms.models import (
    PlanningFlightSnapshot,
    PlanningIssueSeverity,
    PlanningRunStatus,
    PlanningShipmentSnapshot,
    PlanningVolunteerSnapshot,
    ShipmentUnitEquivalenceRule,
    VolunteerConstraint,
)
from wms.planning.sources import (
    build_shipper_reference,
    get_run_flights,
    get_run_shipments,
    get_run_volunteers,
)
from wms.planning.validation import get_destination_rule_map, validate_run_inputs
from wms.unit_equivalence import ShipmentUnitInput, resolve_shipment_unit_count


def _get_constraints(volunteer):
    try:
        return volunteer.constraints
    except VolunteerConstraint.DoesNotExist:
        return None


def _build_availability_summary(*, volunteer, run):
    availabilities = volunteer.availabilities.filter(
        date__gte=run.week_start,
        date__lte=run.week_end,
    ).order_by("date", "start_time", "id")
    slots = [
        {
            "date": availability.date.isoformat(),
            "start_time": availability.start_time.isoformat(timespec="minutes"),
            "end_time": availability.end_time.isoformat(timespec="minutes"),
        }
        for availability in availabilities
    ]
    unavailability_dates = list(
        volunteer.unavailabilities.filter(date__gte=run.week_start, date__lte=run.week_end)
        .order_by("date", "id")
        .values_list("date", flat=True)
    )
    return {
        "slot_count": len(slots),
        "slots": slots,
        "unavailable_dates": [value.isoformat() for value in unavailability_dates],
    }


def _build_shipment_equivalence_items(shipment):
    items = []
    for carton in shipment.carton_set.all().prefetch_related(
        "cartonitem_set__product_lot__product"
    ):
        for carton_item in carton.cartonitem_set.all():
            items.append(
                ShipmentUnitInput(
                    product=carton_item.product_lot.product,
                    quantity=carton_item.quantity,
                )
            )
    return items


def _build_shipment_payload(*, shipment, destination_rule_map):
    destination_rule = destination_rule_map.get(shipment.destination_id)
    payload = {
        "destination_id": shipment.destination_id,
        "destination_iata": shipment.destination.iata_code if shipment.destination_id else "",
        "shipper_reference": build_shipper_reference(shipment),
    }
    if destination_rule is not None:
        payload["destination_rule"] = {
            "id": destination_rule.pk,
            "label": destination_rule.label,
            "priority": destination_rule.priority,
            "max_cartons_per_flight": destination_rule.max_cartons_per_flight,
            "allowed_weekdays": list(destination_rule.allowed_weekdays or []),
        }
    return payload


def _serialize_time(value):
    if value is None:
        return ""
    return value.isoformat(timespec="minutes")


@transaction.atomic
def prepare_run_inputs(run):
    run.issues.all().delete()
    run.shipment_snapshots.all().delete()
    run.volunteer_snapshots.all().delete()
    run.flight_snapshots.all().delete()
    run.status = PlanningRunStatus.VALIDATING
    run.validation_summary = {}
    run.save(update_fields=["status", "validation_summary", "updated_at"])

    shipments = list(get_run_shipments(run))
    volunteers = list(get_run_volunteers(run))
    flights = list(get_run_flights(run))
    destination_rule_map = get_destination_rule_map(run)
    equivalence_rules = list(
        ShipmentUnitEquivalenceRule.objects.filter(is_active=True).select_related(
            "category",
            "category__parent",
        )
    )

    for shipment in shipments:
        PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment=shipment,
            shipment_reference=shipment.reference,
            shipper_name=shipment.shipper_name,
            destination_iata=shipment.destination.iata_code if shipment.destination_id else "",
            priority=destination_rule_map.get(shipment.destination_id).priority
            if shipment.destination_id in destination_rule_map
            else 0,
            carton_count=shipment.carton_set.count(),
            equivalent_units=resolve_shipment_unit_count(
                items=_build_shipment_equivalence_items(shipment),
                rules=equivalence_rules,
            ),
            payload=_build_shipment_payload(
                shipment=shipment,
                destination_rule_map=destination_rule_map,
            ),
        )

    for volunteer in volunteers:
        constraints = _get_constraints(volunteer)
        volunteer_label = volunteer.user.get_full_name().strip() or volunteer.user.email
        PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer=volunteer,
            volunteer_label=volunteer_label,
            max_colis_vol=constraints.max_colis_vol if constraints else None,
            availability_summary=_build_availability_summary(volunteer=volunteer, run=run),
            payload={
                "phone": volunteer.phone,
                "city": volunteer.city,
                "country": volunteer.country,
            },
        )

    for flight in flights:
        PlanningFlightSnapshot.objects.create(
            run=run,
            flight=flight,
            flight_number=flight.flight_number,
            departure_date=flight.departure_date,
            destination_iata=flight.destination_iata,
            capacity_units=flight.capacity_units,
            payload={
                "batch_id": flight.batch_id,
                "source": flight.batch.source,
                "departure_time": _serialize_time(flight.departure_time),
                "arrival_time": _serialize_time(flight.arrival_time),
                "origin_iata": flight.origin_iata,
                "routing": flight.routing,
                "route_pos": flight.route_pos,
            },
        )

    validate_run_inputs(
        run=run,
        shipments=shipments,
        destination_rule_map=destination_rule_map,
    )

    error_count = run.issues.filter(severity=PlanningIssueSeverity.ERROR).count()
    warning_count = run.issues.count() - error_count
    run.status = PlanningRunStatus.VALIDATION_FAILED if error_count else PlanningRunStatus.READY
    run.validation_summary = {
        "shipment_count": len(shipments),
        "volunteer_count": len(volunteers),
        "flight_count": len(flights),
        "error_count": error_count,
        "warning_count": warning_count,
    }
    run.save(update_fields=["status", "validation_summary", "updated_at"])
    return run
