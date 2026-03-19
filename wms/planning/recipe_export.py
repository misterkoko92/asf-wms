from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationPortalContact,
    AssociationProfile,
    Carton,
    CartonItem,
    Destination,
    Flight,
    FlightSourceBatch,
    Location,
    PlanningDestinationRule,
    PlanningParameterSet,
    Product,
    ProductCategory,
    ProductLot,
    Shipment,
    ShipmentUnitEquivalenceRule,
    VolunteerAvailability,
    VolunteerConstraint,
    VolunteerProfile,
    VolunteerUnavailability,
    Warehouse,
)
from wms.planning.sources import ELIGIBLE_SHIPMENT_STATUSES, build_shipper_reference


@dataclass
class PlanningRecipeExport:
    meta: dict[str, Any]
    selection: dict[str, Any]
    summary: dict[str, Any]
    fixtures: dict[str, list[dict[str, Any]]]
    alias_map: dict[str, dict[int, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": _json_safe(self.meta),
            "selection": _json_safe(self.selection),
            "summary": _json_safe(self.summary),
            "fixtures": _json_safe(self.fixtures),
            "alias_map": {
                kind: {str(source_pk): alias for source_pk, alias in mapping.items()}
                for kind, mapping in self.alias_map.items()
            },
        }


class _AliasRegistry:
    def __init__(self) -> None:
        self._maps: dict[str, dict[int, str]] = {}

    def get(self, *, kind: str, source_pk: int | None, prefix: str) -> str:
        if source_pk is None:
            return ""
        mapping = self._maps.setdefault(kind, {})
        if source_pk not in mapping:
            mapping[source_pk] = f"{prefix}-{len(mapping) + 1:03d}"
        return mapping[source_pk]

    @property
    def maps(self) -> dict[str, dict[int, str]]:
        return {kind: dict(mapping) for kind, mapping in self._maps.items()}


def build_planning_recipe_export(
    *,
    week_start: date,
    week_end: date,
    parameter_set_id: int | None = None,
    parameter_set_name: str | None = None,
    include_flight_batches: bool = True,
    anonymize: bool = True,
) -> PlanningRecipeExport:
    parameter_set = _resolve_parameter_set(
        parameter_set_id=parameter_set_id,
        parameter_set_name=parameter_set_name,
    )
    shipments = list(
        Shipment.objects.select_related(
            "destination",
            "shipper_contact_ref",
            "recipient_contact_ref",
            "correspondent_contact_ref",
            "created_by",
        )
        .filter(
            status__in=ELIGIBLE_SHIPMENT_STATUSES,
            ready_at__date__gte=week_start,
            ready_at__date__lte=week_end,
            archived_at__isnull=True,
        )
        .order_by("ready_at", "reference", "id")
    )
    flights = list(
        Flight.objects.select_related("batch", "destination")
        .filter(
            departure_date__gte=week_start,
            departure_date__lte=week_end,
        )
        .order_by("departure_date", "flight_number", "id")
    )
    volunteers = list(
        VolunteerProfile.objects.select_related("user", "contact")
        .filter(is_active=True)
        .order_by("volunteer_id", "id")
    )
    volunteer_ids = [volunteer.pk for volunteer in volunteers]
    volunteer_constraints = list(
        VolunteerConstraint.objects.filter(volunteer_id__in=volunteer_ids)
        .select_related("volunteer")
        .order_by("volunteer_id")
    )
    volunteer_availabilities = list(
        VolunteerAvailability.objects.filter(
            volunteer_id__in=volunteer_ids,
            date__gte=week_start,
            date__lte=week_end,
        ).order_by("volunteer_id", "date", "start_time", "id")
    )
    volunteer_unavailabilities = list(
        VolunteerUnavailability.objects.filter(
            volunteer_id__in=volunteer_ids,
            date__gte=week_start,
            date__lte=week_end,
        ).order_by("volunteer_id", "date", "id")
    )

    shipment_ids = [shipment.pk for shipment in shipments]
    cartons = list(
        Carton.objects.filter(shipment_id__in=shipment_ids)
        .select_related("shipment", "current_location__warehouse", "prepared_by")
        .order_by("code", "id")
    )
    carton_ids = [carton.pk for carton in cartons]
    carton_items = list(
        CartonItem.objects.filter(carton_id__in=carton_ids)
        .select_related(
            "carton",
            "product_lot__product__category",
            "product_lot__location__warehouse",
        )
        .order_by("carton_id", "id")
    )
    product_lot_ids = sorted({item.product_lot_id for item in carton_items})
    product_lots = list(
        ProductLot.objects.filter(id__in=product_lot_ids)
        .select_related("product__category__parent", "location__warehouse")
        .order_by("id")
    )
    product_ids = sorted({lot.product_id for lot in product_lots})
    products = list(
        Product.objects.filter(id__in=product_ids)
        .select_related("category__parent", "default_location__warehouse")
        .order_by("id")
    )
    categories = _collect_categories(products)
    category_ids = [category.pk for category in categories]
    locations = _collect_locations(cartons, product_lots, products)
    warehouses = _collect_warehouses(locations)
    equivalence_rules = list(
        ShipmentUnitEquivalenceRule.objects.filter(
            is_active=True,
        )
        .filter(Q(category_id__in=category_ids) | Q(category__isnull=True))
        .select_related("category")
        .order_by("priority", "id")
    )

    parameter_rules = []
    if parameter_set is not None:
        parameter_rules = list(
            PlanningDestinationRule.objects.filter(parameter_set=parameter_set)
            .select_related("destination")
            .order_by("priority", "id")
        )

    flight_batches = []
    if include_flight_batches:
        batch_ids = sorted({flight.batch_id for flight in flights if flight.batch_id})
        flight_batches = list(FlightSourceBatch.objects.filter(id__in=batch_ids).order_by("id"))

    destinations = _collect_destinations(shipments, flights, parameter_rules)
    destination_ids = [destination.pk for destination in destinations]
    shipper_contact_ids = {
        shipment.shipper_contact_ref_id for shipment in shipments if shipment.shipper_contact_ref_id
    }
    correspondent_contact_ids = {
        destination.correspondent_contact_id
        for destination in destinations
        if destination.correspondent_contact_id
    }
    contact_ids = set()
    for shipment in shipments:
        for contact_id in (
            shipment.shipper_contact_ref_id,
            shipment.recipient_contact_ref_id,
            shipment.correspondent_contact_ref_id,
        ):
            if contact_id:
                contact_ids.add(contact_id)
    for volunteer in volunteers:
        if volunteer.contact_id:
            contact_ids.add(volunteer.contact_id)
    contact_ids.update(correspondent_contact_ids)
    contacts = list(Contact.objects.filter(id__in=sorted(contact_ids)).order_by("name", "id"))
    association_profiles = list(
        AssociationProfile.objects.filter(contact_id__in=sorted(contact_ids))
        .select_related("user", "contact")
        .order_by("id")
    )
    association_profile_ids = [profile.pk for profile in association_profiles]
    portal_contacts = list(
        AssociationPortalContact.objects.filter(profile_id__in=association_profile_ids)
        .select_related("profile")
        .order_by("profile_id", "position", "id")
    )

    user_ids = set()
    for volunteer in volunteers:
        if volunteer.user_id:
            user_ids.add(volunteer.user_id)
    for profile in association_profiles:
        if profile.user_id:
            user_ids.add(profile.user_id)
    for shipment in shipments:
        if shipment.created_by_id:
            user_ids.add(shipment.created_by_id)
    if parameter_set and parameter_set.created_by_id:
        user_ids.add(parameter_set.created_by_id)
    user_model = get_user_model()
    users = list(user_model.objects.filter(id__in=sorted(user_ids)).order_by("id"))

    alias_registry = _AliasRegistry()
    fixtures = {
        "users": [
            _serialize_user(user, anonymize=anonymize, alias_registry=alias_registry)
            for user in users
        ],
        "contacts": [
            _serialize_contact(
                contact,
                anonymize=anonymize,
                alias_registry=alias_registry,
                shipper_contact_ids=shipper_contact_ids,
                correspondent_contact_ids=correspondent_contact_ids,
            )
            for contact in contacts
        ],
        "destinations": [_serialize_destination(destination) for destination in destinations],
        "planning_parameter_sets": [
            _serialize_parameter_set(parameter_set)
            for parameter_set in [parameter_set]
            if parameter_set is not None
        ],
        "planning_destination_rules": [
            _serialize_destination_rule(rule)
            for rule in parameter_rules
            if rule.destination_id in destination_ids
        ],
        "shipment_unit_equivalence_rules": [
            _serialize_equivalence_rule(rule) for rule in equivalence_rules
        ],
        "flight_source_batches": [_serialize_flight_batch(batch) for batch in flight_batches],
        "flights": [_serialize_flight(flight) for flight in flights],
        "association_profiles": [
            _serialize_association_profile(
                profile,
                anonymize=anonymize,
                alias_registry=alias_registry,
            )
            for profile in association_profiles
        ],
        "association_portal_contacts": [
            _serialize_portal_contact(
                portal_contact,
                anonymize=anonymize,
                alias_registry=alias_registry,
            )
            for portal_contact in portal_contacts
        ],
        "volunteer_profiles": [
            _serialize_volunteer(
                volunteer,
                anonymize=anonymize,
                alias_registry=alias_registry,
            )
            for volunteer in volunteers
        ],
        "volunteer_constraints": [
            _serialize_volunteer_constraint(constraint) for constraint in volunteer_constraints
        ],
        "volunteer_availabilities": [
            _serialize_volunteer_availability(availability)
            for availability in volunteer_availabilities
        ],
        "volunteer_unavailabilities": [
            _serialize_volunteer_unavailability(unavailability)
            for unavailability in volunteer_unavailabilities
        ],
        "product_categories": [_serialize_category(category) for category in categories],
        "warehouses": [_serialize_warehouse(warehouse) for warehouse in warehouses],
        "locations": [_serialize_location(location) for location in locations],
        "products": [_serialize_product(product) for product in products],
        "product_lots": [_serialize_product_lot(product_lot) for product_lot in product_lots],
        "shipments": [
            _serialize_shipment(
                shipment,
                anonymize=anonymize,
                alias_registry=alias_registry,
            )
            for shipment in shipments
        ],
        "cartons": [_serialize_carton(carton) for carton in cartons],
        "carton_items": [_serialize_carton_item(carton_item) for carton_item in carton_items],
    }

    selection = {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "parameter_set_id": parameter_set.pk if parameter_set is not None else None,
        "parameter_set_name": parameter_set.name if parameter_set is not None else "",
        "anonymized": anonymize,
        "shipment_ids": shipment_ids,
        "flight_ids": [flight.pk for flight in flights],
        "volunteer_ids": volunteer_ids,
    }
    summary = {
        "shipments": len(shipments),
        "flights": len(flights),
        "flight_batches": len(flight_batches),
        "volunteers": len(volunteers),
        "destinations": len(destinations),
        "contacts": len(contacts),
        "association_profiles": len(association_profiles),
        "portal_contacts": len(portal_contacts),
    }
    meta = {
        "generated_at": timezone.now(),
        "generator": "planning_recipe_export",
        "schema_version": 1,
        "anonymized": anonymize,
    }
    return PlanningRecipeExport(
        meta=meta,
        selection=selection,
        summary=summary,
        fixtures=fixtures,
        alias_map=alias_registry.maps,
    )


def _resolve_parameter_set(
    *,
    parameter_set_id: int | None,
    parameter_set_name: str | None,
) -> PlanningParameterSet | None:
    if parameter_set_id is not None:
        return PlanningParameterSet.objects.filter(pk=parameter_set_id).first()
    if parameter_set_name:
        return PlanningParameterSet.objects.filter(name=parameter_set_name).first()
    current = PlanningParameterSet.objects.filter(is_current=True).order_by("-id").first()
    if current is not None:
        return current
    return PlanningParameterSet.objects.order_by("-is_current", "name", "id").first()


def _collect_categories(products: list[Product]) -> list[ProductCategory]:
    category_map: dict[int, ProductCategory] = {}
    pending_ids = {product.category_id for product in products if product.category_id}
    while pending_ids:
        batch = list(
            ProductCategory.objects.filter(id__in=sorted(pending_ids))
            .select_related("parent")
            .order_by("id")
        )
        pending_ids = set()
        for category in batch:
            if category.pk in category_map:
                continue
            category_map[category.pk] = category
            if category.parent_id and category.parent_id not in category_map:
                pending_ids.add(category.parent_id)
    return list(category_map.values())


def _collect_locations(
    cartons: list[Carton],
    product_lots: list[ProductLot],
    products: list[Product],
) -> list[Location]:
    location_ids = {carton.current_location_id for carton in cartons if carton.current_location_id}
    location_ids.update(
        product_lot.location_id for product_lot in product_lots if product_lot.location_id
    )
    location_ids.update(
        product.default_location_id for product in products if product.default_location_id
    )
    return list(
        Location.objects.filter(id__in=sorted(location_ids))
        .select_related("warehouse")
        .order_by("warehouse__name", "zone", "aisle", "shelf", "id")
    )


def _collect_warehouses(locations: list[Location]) -> list[Warehouse]:
    warehouse_ids = sorted(
        {location.warehouse_id for location in locations if location.warehouse_id}
    )
    return list(Warehouse.objects.filter(id__in=warehouse_ids).order_by("name", "id"))


def _collect_destinations(
    shipments: list[Shipment],
    flights: list[Flight],
    parameter_rules: list[PlanningDestinationRule],
) -> list[Destination]:
    destination_ids = {shipment.destination_id for shipment in shipments if shipment.destination_id}
    destination_ids.update(flight.destination_id for flight in flights if flight.destination_id)
    destination_ids.update(rule.destination_id for rule in parameter_rules if rule.destination_id)
    return list(Destination.objects.filter(id__in=sorted(destination_ids)).order_by("city", "id"))


def _serialize_user(user, *, anonymize: bool, alias_registry: _AliasRegistry) -> dict[str, Any]:
    alias = alias_registry.get(kind="user", source_pk=user.pk, prefix="USER")
    username = user.username
    email = user.email
    first_name = user.first_name
    last_name = user.last_name
    if anonymize:
        username = alias.lower()
        email = _alias_email(alias)
        first_name = alias
        last_name = ""
    return {
        "source_pk": user.pk,
        "username": username,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
    }


def _serialize_contact(
    contact: Contact,
    *,
    anonymize: bool,
    alias_registry: _AliasRegistry,
    shipper_contact_ids: set[int],
    correspondent_contact_ids: set[int],
) -> dict[str, Any]:
    alias = alias_registry.get(
        kind="contact",
        source_pk=contact.pk,
        prefix=_contact_prefix(
            contact=contact,
            shipper_contact_ids=shipper_contact_ids,
            correspondent_contact_ids=correspondent_contact_ids,
        ),
    )
    name = alias if anonymize else contact.name
    first_name = (
        alias if anonymize and contact.contact_type == ContactType.PERSON else contact.first_name
    )
    last_name = (
        "" if anonymize and contact.contact_type == ContactType.PERSON else contact.last_name
    )
    email = _alias_email(alias) if anonymize and alias else contact.email
    email2 = _alias_email(f"{alias}-ALT") if anonymize and contact.email2 else contact.email2
    return {
        "source_pk": contact.pk,
        "contact_type": contact.contact_type,
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "email2": email2,
        "phone": contact.phone,
        "phone2": contact.phone2,
        "is_active": contact.is_active,
        "organization_id": contact.organization_id,
    }


def _serialize_destination(destination: Destination) -> dict[str, Any]:
    return {
        "source_pk": destination.pk,
        "city": destination.city,
        "iata_code": destination.iata_code,
        "country": destination.country,
        "correspondent_contact_id": destination.correspondent_contact_id,
        "is_active": destination.is_active,
    }


def _serialize_parameter_set(parameter_set: PlanningParameterSet) -> dict[str, Any]:
    return {
        "source_pk": parameter_set.pk,
        "name": parameter_set.name,
        "status": parameter_set.status,
        "effective_from": parameter_set.effective_from,
        "notes": parameter_set.notes,
        "is_current": parameter_set.is_current,
        "created_by_id": parameter_set.created_by_id,
    }


def _serialize_destination_rule(rule: PlanningDestinationRule) -> dict[str, Any]:
    return {
        "source_pk": rule.pk,
        "parameter_set_id": rule.parameter_set_id,
        "destination_id": rule.destination_id,
        "label": rule.label,
        "weekly_frequency": rule.weekly_frequency,
        "max_cartons_per_flight": rule.max_cartons_per_flight,
        "allowed_weekdays": list(rule.allowed_weekdays or []),
        "priority": rule.priority,
        "notes": rule.notes,
        "is_active": rule.is_active,
    }


def _serialize_equivalence_rule(rule: ShipmentUnitEquivalenceRule) -> dict[str, Any]:
    return {
        "source_pk": rule.pk,
        "label": rule.label,
        "category_id": rule.category_id,
        "applies_to_hors_format": rule.applies_to_hors_format,
        "units_per_item": rule.units_per_item,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "notes": rule.notes,
    }


def _serialize_flight_batch(batch: FlightSourceBatch) -> dict[str, Any]:
    return {
        "source_pk": batch.pk,
        "source": batch.source,
        "period_start": batch.period_start,
        "period_end": batch.period_end,
        "file_name": batch.file_name,
        "checksum": batch.checksum,
        "status": batch.status,
        "imported_at": batch.imported_at,
        "notes": batch.notes,
    }


def _serialize_flight(flight: Flight) -> dict[str, Any]:
    return {
        "source_pk": flight.pk,
        "batch_id": flight.batch_id,
        "flight_number": flight.flight_number,
        "departure_date": flight.departure_date,
        "departure_time": flight.departure_time,
        "arrival_time": flight.arrival_time,
        "origin_iata": flight.origin_iata,
        "destination_iata": flight.destination_iata,
        "routing": flight.routing,
        "route_pos": flight.route_pos,
        "destination_id": flight.destination_id,
        "capacity_units": flight.capacity_units,
        "quality_notes": flight.quality_notes,
    }


def _serialize_association_profile(
    profile: AssociationProfile,
    *,
    anonymize: bool,
    alias_registry: _AliasRegistry,
) -> dict[str, Any]:
    alias = alias_registry.get(kind="association_profile", source_pk=profile.pk, prefix="ASSOC")
    notification_emails = profile.get_notification_emails()
    if anonymize:
        anonymized_notification_emails = _anonymized_profile_notification_emails(
            profile=profile,
            alias_registry=alias_registry,
        )
        if anonymized_notification_emails:
            notification_emails = anonymized_notification_emails
        else:
            notification_emails = [
                _alias_email(f"{alias}-{index + 1}") for index, _ in enumerate(notification_emails)
            ]
    return {
        "source_pk": profile.pk,
        "user_id": profile.user_id,
        "contact_id": profile.contact_id,
        "display_name": alias if anonymize else str(profile),
        "notification_emails": notification_emails,
        "must_change_password": profile.must_change_password,
    }


def _serialize_portal_contact(
    portal_contact: AssociationPortalContact,
    *,
    anonymize: bool,
    alias_registry: _AliasRegistry,
) -> dict[str, Any]:
    alias = alias_registry.get(kind="portal_contact", source_pk=portal_contact.pk, prefix="PORTAL")
    return {
        "source_pk": portal_contact.pk,
        "profile_id": portal_contact.profile_id,
        "position": portal_contact.position,
        "title": portal_contact.title,
        "first_name": alias if anonymize else portal_contact.first_name,
        "last_name": "" if anonymize else portal_contact.last_name,
        "email": _alias_email(alias) if anonymize else portal_contact.email,
        "phone": portal_contact.phone,
        "is_administrative": portal_contact.is_administrative,
        "is_shipping": portal_contact.is_shipping,
        "is_billing": portal_contact.is_billing,
        "is_active": portal_contact.is_active,
    }


def _serialize_volunteer(
    volunteer: VolunteerProfile,
    *,
    anonymize: bool,
    alias_registry: _AliasRegistry,
) -> dict[str, Any]:
    alias = alias_registry.get(kind="volunteer", source_pk=volunteer.pk, prefix="VOL")
    display_name = (
        alias if anonymize else volunteer.user.get_full_name().strip() or volunteer.user.email
    )
    email = _alias_email(alias) if anonymize else volunteer.user.email
    return {
        "source_pk": volunteer.pk,
        "user_id": volunteer.user_id,
        "contact_id": volunteer.contact_id,
        "volunteer_id": volunteer.volunteer_id,
        "display_name": display_name,
        "email": email,
        "short_name": alias if anonymize else volunteer.short_name,
        "phone": volunteer.phone,
        "city": volunteer.city,
        "country": volunteer.country,
        "is_active": volunteer.is_active,
    }


def _serialize_volunteer_constraint(constraint: VolunteerConstraint) -> dict[str, Any]:
    return {
        "source_pk": constraint.pk,
        "volunteer_id": constraint.volunteer_id,
        "max_days_per_week": constraint.max_days_per_week,
        "max_expeditions_per_week": constraint.max_expeditions_per_week,
        "max_expeditions_per_day": constraint.max_expeditions_per_day,
        "max_colis_vol": constraint.max_colis_vol,
        "max_wait_hours": constraint.max_wait_hours,
    }


def _serialize_volunteer_availability(availability: VolunteerAvailability) -> dict[str, Any]:
    return {
        "source_pk": availability.pk,
        "volunteer_id": availability.volunteer_id,
        "date": availability.date,
        "start_time": availability.start_time,
        "end_time": availability.end_time,
    }


def _serialize_volunteer_unavailability(unavailability: VolunteerUnavailability) -> dict[str, Any]:
    return {
        "source_pk": unavailability.pk,
        "volunteer_id": unavailability.volunteer_id,
        "date": unavailability.date,
    }


def _serialize_category(category: ProductCategory) -> dict[str, Any]:
    return {
        "source_pk": category.pk,
        "name": category.name,
        "parent_id": category.parent_id,
    }


def _serialize_warehouse(warehouse: Warehouse) -> dict[str, Any]:
    return {
        "source_pk": warehouse.pk,
        "name": warehouse.name,
        "code": warehouse.code,
    }


def _serialize_location(location: Location) -> dict[str, Any]:
    return {
        "source_pk": location.pk,
        "warehouse_id": location.warehouse_id,
        "zone": location.zone,
        "aisle": location.aisle,
        "shelf": location.shelf,
        "notes": location.notes,
    }


def _serialize_product(product: Product) -> dict[str, Any]:
    return {
        "source_pk": product.pk,
        "sku": product.sku,
        "name": product.name,
        "category_id": product.category_id,
        "default_location_id": product.default_location_id,
        "is_active": product.is_active,
    }


def _serialize_product_lot(product_lot: ProductLot) -> dict[str, Any]:
    return {
        "source_pk": product_lot.pk,
        "product_id": product_lot.product_id,
        "lot_code": product_lot.lot_code,
        "expires_on": product_lot.expires_on,
        "received_on": product_lot.received_on,
        "status": product_lot.status,
        "quantity_on_hand": product_lot.quantity_on_hand,
        "quantity_reserved": product_lot.quantity_reserved,
        "location_id": product_lot.location_id,
    }


def _serialize_shipment(
    shipment: Shipment,
    *,
    anonymize: bool,
    alias_registry: _AliasRegistry,
) -> dict[str, Any]:
    shipper_reference = build_shipper_reference(shipment)
    if anonymize and shipper_reference:
        contact_id = shipper_reference.get("contact_id")
        contact_alias = alias_registry.get(kind="contact", source_pk=contact_id, prefix="SHIPPER")
        notification_emails = []
        if shipment.shipper_contact_ref_id:
            notification_emails = _anonymized_shipper_notification_emails(
                shipper_contact=shipment.shipper_contact_ref,
                alias_registry=alias_registry,
            )
        shipper_reference = {
            **shipper_reference,
            "contact_name": contact_alias,
            "notification_emails": notification_emails,
        }
    return {
        "source_pk": shipment.pk,
        "reference": shipment.reference,
        "status": shipment.status,
        "shipper_name": (
            alias_registry.get(
                kind="contact", source_pk=shipment.shipper_contact_ref_id, prefix="SHIPPER"
            )
            if anonymize and shipment.shipper_contact_ref_id
            else shipment.shipper_name
        ),
        "recipient_name": (
            alias_registry.get(
                kind="contact", source_pk=shipment.recipient_contact_ref_id, prefix="PERSON"
            )
            if anonymize and shipment.recipient_contact_ref_id
            else shipment.recipient_name
        ),
        "destination_id": shipment.destination_id,
        "destination_iata": shipment.destination.iata_code if shipment.destination_id else "",
        "destination_country": shipment.destination_country,
        "ready_at": shipment.ready_at,
        "created_by_id": shipment.created_by_id,
        "shipper_reference": shipper_reference,
    }


def _serialize_carton(carton: Carton) -> dict[str, Any]:
    return {
        "source_pk": carton.pk,
        "code": carton.code,
        "status": carton.status,
        "shipment_id": carton.shipment_id,
        "current_location_id": carton.current_location_id,
        "prepared_by_id": carton.prepared_by_id,
    }


def _serialize_carton_item(carton_item: CartonItem) -> dict[str, Any]:
    return {
        "source_pk": carton_item.pk,
        "carton_id": carton_item.carton_id,
        "product_lot_id": carton_item.product_lot_id,
        "quantity": carton_item.quantity,
    }


def _contact_prefix(
    *,
    contact: Contact,
    shipper_contact_ids: set[int],
    correspondent_contact_ids: set[int],
) -> str:
    if contact.pk in shipper_contact_ids:
        return "SHIPPER"
    if contact.pk in correspondent_contact_ids:
        return "CORRESP"
    if contact.contact_type == ContactType.PERSON:
        return "PERSON"
    return "CONTACT"


def _alias_email(alias: str) -> str:
    normalized = alias.lower().replace("_", "-")
    return f"{normalized}@example.invalid"


def _anonymized_shipper_notification_emails(
    *,
    shipper_contact: Contact | None,
    alias_registry: _AliasRegistry,
) -> list[str]:
    if shipper_contact is None:
        return []
    profile = (
        shipper_contact.association_profiles.prefetch_related("portal_contacts")
        .order_by("id")
        .first()
    )
    if profile is None:
        return []
    return _anonymized_profile_notification_emails(
        profile=profile,
        alias_registry=alias_registry,
    )


def _anonymized_profile_notification_emails(
    *,
    profile: AssociationProfile,
    alias_registry: _AliasRegistry,
) -> list[str]:
    emails = []
    seen = set()
    for portal_contact in profile.portal_contacts.filter(is_active=True).order_by("position", "id"):
        raw_email = (portal_contact.email or "").strip()
        if not raw_email:
            continue
        normalized = raw_email.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        alias = alias_registry.get(
            kind="portal_contact", source_pk=portal_contact.pk, prefix="PORTAL"
        )
        emails.append(_alias_email(alias))
    return emails


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value
