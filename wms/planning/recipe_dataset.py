from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationPortalContact,
    AssociationProfile,
    Carton,
    CartonItem,
    CommunicationChannel,
    CommunicationTemplate,
    Destination,
    Flight,
    FlightSourceBatch,
    FlightSourceBatchStatus,
    Location,
    PlanningDestinationRule,
    PlanningParameterSet,
    PlanningRun,
    PlanningRunFlightMode,
    PlanningRunStatus,
    Product,
    ProductCategory,
    ProductLot,
    Shipment,
    ShipmentStatus,
    ShipmentUnitEquivalenceRule,
    VolunteerAvailability,
    VolunteerConstraint,
    VolunteerProfile,
    Warehouse,
)
from wms.planning.snapshots import prepare_run_inputs
from wms.planning.solver import solve_run

RECIPE_WEEK_START = date(2026, 3, 9)
RECIPE_WEEK_END = date(2026, 3, 15)


@dataclass(frozen=True)
class ScenarioNamespace:
    scenario_slug: str
    label_prefix: str
    contact_prefix: str
    parameter_set_name: str
    reference_prefix: str
    user_prefix: str
    template_prefix: str
    batch_file_name: str
    warehouse_name: str
    run_log_excerpt: str


@dataclass(frozen=True)
class RecipeShipmentSpec:
    suffix: str
    destination_iata: str
    ready_at: datetime
    quantity: int
    product_key: str
    carton_code: str


@dataclass(frozen=True)
class RecipeVolunteerSpec:
    username_suffix: str
    first_name: str
    last_name: str
    city: str
    phone: str
    max_colis_vol: int
    availability_specs: tuple[tuple[date, time, time], ...]


@dataclass(frozen=True)
class RecipeFlightSpec:
    flight_number: str
    departure_date: date
    departure_time: time
    arrival_time: time
    destination_iata: str
    routing: str
    route_pos: int
    capacity_units: int


def normalize_recipe_scenario_slug(raw_value: str) -> str:
    return slugify(raw_value).strip("-") or "phase3-s11-recipe"


def seed_recipe_dataset(*, scenario_slug: str, solve: bool = False) -> dict[str, object]:
    namespace = build_recipe_namespace(scenario_slug)
    purge_recipe_dataset(scenario_slug=scenario_slug, dry_run=False)

    planner = _create_user(
        username=f"{namespace.user_prefix}planner",
        email=f"{namespace.user_prefix}planner@example.com",
        first_name="Recipe",
        last_name="Planner",
    )
    association_user = _create_user(
        username=f"{namespace.user_prefix}association",
        email=f"{namespace.user_prefix}association@example.com",
        first_name="Recipe",
        last_name="Association",
    )
    volunteer_specs = (
        RecipeVolunteerSpec(
            username_suffix="theo-thursday",
            first_name="Theo",
            last_name="Thursday",
            city="Paris",
            phone="+33600000001",
            max_colis_vol=6,
            availability_specs=(
                (date(2026, 3, 10), time(6, 0), time(18, 0)),
                (date(2026, 3, 12), time(6, 0), time(18, 0)),
            ),
        ),
        RecipeVolunteerSpec(
            username_suffix="dina-dla",
            first_name="Dina",
            last_name="Dla",
            city="Paris",
            phone="+33600000002",
            max_colis_vol=5,
            availability_specs=((date(2026, 3, 14), time(5, 0), time(13, 0)),),
        ),
        RecipeVolunteerSpec(
            username_suffix="nora-limit",
            first_name="Nora",
            last_name="Limit",
            city="Paris",
            phone="+33600000003",
            max_colis_vol=2,
            availability_specs=((date(2026, 3, 14), time(5, 0), time(13, 0)),),
        ),
        RecipeVolunteerSpec(
            username_suffix="abby-compact",
            first_name="Abby",
            last_name="Compact",
            city="Paris",
            phone="+33600000004",
            max_colis_vol=8,
            availability_specs=((date(2026, 3, 14), time(10, 0), time(15, 0)),),
        ),
        RecipeVolunteerSpec(
            username_suffix="abel-long",
            first_name="Abel",
            last_name="Long",
            city="Paris",
            phone="+33600000005",
            max_colis_vol=8,
            availability_specs=((date(2026, 3, 14), time(10, 0), time(21, 0)),),
        ),
    )

    shipper_contact = Contact.objects.create(
        name=f"{namespace.contact_prefix} Association Source",
        contact_type=ContactType.ORGANIZATION,
        is_active=True,
    )
    correspondent_contacts = {
        "NSI": Contact.objects.create(
            name=f"{namespace.contact_prefix} Correspondant NSI",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        ),
        "DLA": Contact.objects.create(
            name=f"{namespace.contact_prefix} Correspondant DLA",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        ),
        "ABJ": Contact.objects.create(
            name=f"{namespace.contact_prefix} Correspondant ABJ",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        ),
    }
    association_profile = AssociationProfile.objects.create(
        user=association_user,
        contact=shipper_contact,
        notification_emails=f"{namespace.user_prefix}ops@example.com",
    )
    AssociationPortalContact.objects.create(
        profile=association_profile,
        position=1,
        first_name="Shipping",
        last_name="Primary",
        email=f"{namespace.user_prefix}shipping-primary@example.com",
        is_shipping=True,
    )
    AssociationPortalContact.objects.create(
        profile=association_profile,
        position=2,
        first_name="Shipping",
        last_name="Backup",
        email=f"{namespace.user_prefix}shipping-backup@example.com",
        is_shipping=True,
    )

    destinations = {
        "NSI": _resolve_destination(
            iata_code="NSI",
            city="Yaounde",
            country="Cameroun",
            correspondent_contact=correspondent_contacts["NSI"],
        ),
        "DLA": _resolve_destination(
            iata_code="DLA",
            city="Douala",
            country="Cameroun",
            correspondent_contact=correspondent_contacts["DLA"],
        ),
        "ABJ": _resolve_destination(
            iata_code="ABJ",
            city="Abidjan",
            country="Cote d'Ivoire",
            correspondent_contact=correspondent_contacts["ABJ"],
        ),
    }

    parameter_set = PlanningParameterSet.objects.create(
        name=namespace.parameter_set_name,
        notes=f"Recipe dataset for scenario {namespace.scenario_slug}.",
        status="draft",
        is_current=False,
        created_by=planner,
    )
    PlanningDestinationRule.objects.create(
        parameter_set=parameter_set,
        destination=destinations["NSI"],
        label=f"{namespace.label_prefix} NSI",
        weekly_frequency=1,
        max_cartons_per_flight=6,
        allowed_weekdays=["thu"],
        priority=1,
        is_active=True,
    )
    PlanningDestinationRule.objects.create(
        parameter_set=parameter_set,
        destination=destinations["DLA"],
        label=f"{namespace.label_prefix} DLA",
        weekly_frequency=2,
        max_cartons_per_flight=5,
        priority=3,
        is_active=True,
    )
    PlanningDestinationRule.objects.create(
        parameter_set=parameter_set,
        destination=destinations["ABJ"],
        label=f"{namespace.label_prefix} ABJ",
        weekly_frequency=1,
        max_cartons_per_flight=8,
        priority=5,
        is_active=True,
    )

    warehouse = Warehouse.objects.create(name=namespace.warehouse_name, code="RCP")
    location = Location.objects.create(
        warehouse=warehouse,
        zone="R",
        aisle="01",
        shelf="01",
    )
    categories = {
        "medical": ProductCategory.objects.create(name=f"{namespace.label_prefix} Medical"),
        "school": ProductCategory.objects.create(name=f"{namespace.label_prefix} School"),
    }
    products = {
        "medical": Product.objects.create(
            name=f"{namespace.label_prefix} Medical Kit",
            category=categories["medical"],
            default_location=location,
        ),
        "school": Product.objects.create(
            name=f"{namespace.label_prefix} School Kit",
            category=categories["school"],
            default_location=location,
        ),
    }
    lots = {
        key: ProductLot.objects.create(
            product=product,
            location=location,
            quantity_on_hand=100,
        )
        for key, product in products.items()
    }
    ShipmentUnitEquivalenceRule.objects.create(
        label=f"{namespace.label_prefix} Medical x1",
        category=categories["medical"],
        units_per_item=1,
        priority=1,
        is_active=True,
    )
    ShipmentUnitEquivalenceRule.objects.create(
        label=f"{namespace.label_prefix} School x1",
        category=categories["school"],
        units_per_item=1,
        priority=2,
        is_active=True,
    )

    shipment_specs = (
        RecipeShipmentSpec(
            suffix="001",
            destination_iata="NSI",
            ready_at=datetime(2026, 3, 10, 8, 0, tzinfo=UTC),
            quantity=3,
            product_key="medical",
            carton_code=f"{namespace.reference_prefix}-C001",
        ),
        RecipeShipmentSpec(
            suffix="002",
            destination_iata="NSI",
            ready_at=datetime(2026, 3, 11, 9, 30, tzinfo=UTC),
            quantity=2,
            product_key="medical",
            carton_code=f"{namespace.reference_prefix}-C002",
        ),
        RecipeShipmentSpec(
            suffix="003",
            destination_iata="DLA",
            ready_at=datetime(2026, 3, 10, 10, 0, tzinfo=UTC),
            quantity=3,
            product_key="medical",
            carton_code=f"{namespace.reference_prefix}-C003",
        ),
        RecipeShipmentSpec(
            suffix="004",
            destination_iata="DLA",
            ready_at=datetime(2026, 3, 11, 11, 0, tzinfo=UTC),
            quantity=3,
            product_key="medical",
            carton_code=f"{namespace.reference_prefix}-C004",
        ),
        RecipeShipmentSpec(
            suffix="005",
            destination_iata="DLA",
            ready_at=datetime(2026, 3, 12, 8, 45, tzinfo=UTC),
            quantity=3,
            product_key="medical",
            carton_code=f"{namespace.reference_prefix}-C005",
        ),
        RecipeShipmentSpec(
            suffix="006",
            destination_iata="ABJ",
            ready_at=datetime(2026, 3, 13, 9, 15, tzinfo=UTC),
            quantity=4,
            product_key="school",
            carton_code=f"{namespace.reference_prefix}-C006",
        ),
        RecipeShipmentSpec(
            suffix="007",
            destination_iata="ABJ",
            ready_at=datetime(2026, 3, 13, 9, 45, tzinfo=UTC),
            quantity=3,
            product_key="school",
            carton_code=f"{namespace.reference_prefix}-C007",
        ),
        RecipeShipmentSpec(
            suffix="008",
            destination_iata="ABJ",
            ready_at=datetime(2026, 3, 13, 10, 15, tzinfo=UTC),
            quantity=3,
            product_key="school",
            carton_code=f"{namespace.reference_prefix}-C008",
        ),
    )
    shipments = [
        _create_shipment(
            namespace=namespace,
            spec=spec,
            shipper_contact=shipper_contact,
            destination=destinations[spec.destination_iata],
            product_lot=lots[spec.product_key],
            created_by=planner,
        )
        for spec in shipment_specs
    ]

    volunteers = [_create_volunteer(namespace=namespace, spec=spec) for spec in volunteer_specs]

    batch = FlightSourceBatch.objects.create(
        source="recipe",
        period_start=RECIPE_WEEK_START,
        period_end=RECIPE_WEEK_END,
        file_name=namespace.batch_file_name,
        status=FlightSourceBatchStatus.IMPORTED,
        notes=f"Recipe planning flights for {namespace.scenario_slug}.",
    )
    flight_specs = (
        RecipeFlightSpec(
            flight_number="AF945",
            departure_date=date(2026, 3, 10),
            departure_time=time(10, 0),
            arrival_time=time(16, 0),
            destination_iata="NSI",
            routing="CDG-NSI",
            route_pos=1,
            capacity_units=6,
        ),
        RecipeFlightSpec(
            flight_number="AF982",
            departure_date=date(2026, 3, 12),
            departure_time=time(9, 30),
            arrival_time=time(15, 0),
            destination_iata="NSI",
            routing="CDG-NSI-DLA",
            route_pos=1,
            capacity_units=6,
        ),
        RecipeFlightSpec(
            flight_number="AF982",
            departure_date=date(2026, 3, 12),
            departure_time=time(9, 30),
            arrival_time=time(17, 0),
            destination_iata="DLA",
            routing="CDG-NSI-DLA",
            route_pos=2,
            capacity_units=6,
        ),
        RecipeFlightSpec(
            flight_number="AF968",
            departure_date=date(2026, 3, 14),
            departure_time=time(9, 0),
            arrival_time=time(15, 30),
            destination_iata="DLA",
            routing="CDG-DLA",
            route_pos=1,
            capacity_units=5,
        ),
        RecipeFlightSpec(
            flight_number="AF969",
            departure_date=date(2026, 3, 14),
            departure_time=time(11, 0),
            arrival_time=time(17, 30),
            destination_iata="DLA",
            routing="CDG-DLA",
            route_pos=1,
            capacity_units=5,
        ),
        RecipeFlightSpec(
            flight_number="AF704",
            departure_date=date(2026, 3, 14),
            departure_time=time(13, 0),
            arrival_time=time(19, 30),
            destination_iata="ABJ",
            routing="CDG-ABJ",
            route_pos=1,
            capacity_units=8,
        ),
    )
    flights = [
        Flight.objects.create(
            batch=batch,
            flight_number=spec.flight_number,
            departure_date=spec.departure_date,
            departure_time=spec.departure_time,
            arrival_time=spec.arrival_time,
            origin_iata="CDG",
            destination_iata=spec.destination_iata,
            routing=spec.routing,
            route_pos=spec.route_pos,
            destination=destinations[spec.destination_iata],
            capacity_units=spec.capacity_units,
        )
        for spec in flight_specs
    ]

    _ensure_communication_templates(namespace)

    run = PlanningRun.objects.create(
        week_start=RECIPE_WEEK_START,
        week_end=RECIPE_WEEK_END,
        flight_mode=PlanningRunFlightMode.EXCEL,
        flight_batch=batch,
        parameter_set=parameter_set,
        status=PlanningRunStatus.DRAFT,
        created_by=planner,
        validation_summary={},
        solver_payload={},
        solver_result={},
        log_excerpt=namespace.run_log_excerpt,
    )
    if solve:
        prepare_run_inputs(run)
        run.refresh_from_db()
        if run.status != PlanningRunStatus.READY:
            raise ValueError(f"Recipe scenario validation failed: {run.validation_summary}")
        version = solve_run(run)
    else:
        version = None
    return {
        "namespace": namespace,
        "run": run,
        "version": version,
        "shipments": shipments,
        "volunteers": volunteers,
        "flights": flights,
        "parameter_set": parameter_set,
    }


def purge_recipe_dataset(*, scenario_slug: str, dry_run: bool = True) -> dict[str, object]:
    namespace = build_recipe_namespace(scenario_slug)
    querysets = _build_recipe_querysets(namespace)
    counts = {key: queryset.count() for key, queryset in querysets.items()}
    if dry_run:
        return {"dry_run": True, "counts": counts}

    with transaction.atomic():
        for key in (
            "planning_runs",
            "carton_items",
            "cartons",
            "shipments",
            "flights",
            "flight_batches",
            "volunteer_profiles",
            "portal_contacts",
            "association_profiles",
            "communication_templates",
            "product_lots",
            "products",
            "product_categories",
            "locations",
            "warehouses",
            "planning_destination_rules",
            "planning_parameter_sets",
            "destinations",
            "contacts",
            "users",
            "equivalence_rules",
        ):
            querysets[key].delete()
    return {"dry_run": False, "counts": counts}


def build_recipe_namespace(scenario_slug: str) -> ScenarioNamespace:
    normalized = normalize_recipe_scenario_slug(scenario_slug)
    base_slug = normalized.removesuffix("-recipe")
    base_upper = base_slug.upper().replace("-", "-")
    label_prefix = "[RECIPE phase3-s11]"
    return ScenarioNamespace(
        scenario_slug=normalized,
        label_prefix=label_prefix,
        contact_prefix=label_prefix,
        parameter_set_name=f"RECIPE {normalized}",
        reference_prefix=f"RECIPE-{base_upper}",
        user_prefix=f"recipe-{normalized}-",
        template_prefix=f"RECIPE {normalized}",
        batch_file_name=normalized,
        warehouse_name=f"{label_prefix} Warehouse",
        run_log_excerpt=f"recipe:{normalized}",
    )


def _build_recipe_querysets(namespace: ScenarioNamespace) -> dict[str, object]:
    user_model = get_user_model()
    users = user_model.objects.filter(username__startswith=namespace.user_prefix)
    volunteer_profiles = VolunteerProfile.objects.filter(user__in=users)
    association_profiles = AssociationProfile.objects.filter(user__in=users)
    contacts = Contact.objects.filter(name__startswith=namespace.contact_prefix)
    destinations = Destination.objects.filter(
        correspondent_contact__name__startswith=namespace.contact_prefix,
        iata_code__in=["NSI", "DLA", "ABJ"],
    )
    planning_parameter_sets = PlanningParameterSet.objects.filter(name=namespace.parameter_set_name)
    planning_destination_rules = PlanningDestinationRule.objects.filter(
        parameter_set__in=planning_parameter_sets
    )
    flight_batches = FlightSourceBatch.objects.filter(
        source="recipe",
        file_name=namespace.batch_file_name,
    )
    flights = Flight.objects.filter(batch__in=flight_batches)
    planning_runs = PlanningRun.objects.filter(
        parameter_set__in=planning_parameter_sets,
    )
    shipments = Shipment.objects.filter(reference__startswith=namespace.reference_prefix)
    cartons = Carton.objects.filter(code__startswith=namespace.reference_prefix)
    carton_items = CartonItem.objects.filter(carton__in=cartons)
    portal_contacts = AssociationPortalContact.objects.filter(profile__in=association_profiles)
    communication_templates = CommunicationTemplate.objects.filter(
        label__startswith=namespace.template_prefix
    )
    product_categories = ProductCategory.objects.filter(name__startswith=namespace.label_prefix)
    products = Product.objects.filter(name__startswith=namespace.label_prefix)
    product_lots = ProductLot.objects.filter(product__in=products)
    locations = Location.objects.filter(warehouse__name=namespace.warehouse_name)
    warehouses = Warehouse.objects.filter(name=namespace.warehouse_name)
    equivalence_rules = ShipmentUnitEquivalenceRule.objects.filter(
        label__startswith=namespace.label_prefix
    )
    return {
        "users": users,
        "contacts": contacts,
        "destinations": destinations,
        "planning_parameter_sets": planning_parameter_sets,
        "planning_destination_rules": planning_destination_rules,
        "flight_batches": flight_batches,
        "flights": flights,
        "planning_runs": planning_runs,
        "shipments": shipments,
        "cartons": cartons,
        "carton_items": carton_items,
        "volunteer_profiles": volunteer_profiles,
        "association_profiles": association_profiles,
        "portal_contacts": portal_contacts,
        "communication_templates": communication_templates,
        "product_categories": product_categories,
        "products": products,
        "product_lots": product_lots,
        "locations": locations,
        "warehouses": warehouses,
        "equivalence_rules": equivalence_rules,
    }


def _create_user(*, username: str, email: str, first_name: str, last_name: str):
    user = get_user_model().objects.create_user(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user


def _resolve_destination(
    *,
    iata_code: str,
    city: str,
    country: str,
    correspondent_contact: Contact,
) -> Destination:
    destination = Destination.objects.filter(iata_code=iata_code).first()
    if destination is not None:
        return destination
    destination = Destination.objects.filter(city=city, country=country).first()
    if destination is not None:
        return destination
    return Destination.objects.create(
        city=city,
        country=country,
        iata_code=iata_code,
        correspondent_contact=correspondent_contact,
        is_active=True,
    )


def _create_shipment(
    *,
    namespace: ScenarioNamespace,
    spec: RecipeShipmentSpec,
    shipper_contact: Contact,
    destination: Destination,
    product_lot: ProductLot,
    created_by,
) -> Shipment:
    shipment = Shipment.objects.create(
        reference=f"{namespace.reference_prefix}-{spec.suffix}",
        status=ShipmentStatus.PACKED,
        shipper_name=shipper_contact.name,
        shipper_contact_ref=shipper_contact,
        recipient_name=f"Recipient {spec.destination_iata}",
        destination=destination,
        destination_address=f"{destination.city} airport",
        destination_country=destination.country,
        ready_at=spec.ready_at,
        created_by=created_by,
    )
    carton = Carton.objects.create(
        code=spec.carton_code,
        shipment=shipment,
        current_location=product_lot.location,
        status="packed",
        notes=f"Recipe carton for {shipment.reference}.",
    )
    CartonItem.objects.create(
        carton=carton,
        product_lot=product_lot,
        quantity=spec.quantity,
    )
    return shipment


def _create_volunteer(
    *, namespace: ScenarioNamespace, spec: RecipeVolunteerSpec
) -> VolunteerProfile:
    user = _create_user(
        username=f"{namespace.user_prefix}{spec.username_suffix}",
        email=f"{namespace.user_prefix}{spec.username_suffix}@example.com",
        first_name=spec.first_name,
        last_name=spec.last_name,
    )
    volunteer = VolunteerProfile.objects.create(
        user=user,
        phone=spec.phone,
        city=spec.city,
        country="France",
        is_active=True,
    )
    VolunteerConstraint.objects.create(
        volunteer=volunteer,
        max_colis_vol=spec.max_colis_vol,
    )
    for availability_date, start_time, end_time in spec.availability_specs:
        VolunteerAvailability.objects.create(
            volunteer=volunteer,
            date=availability_date,
            start_time=start_time,
            end_time=end_time,
        )
    return volunteer


def _ensure_communication_templates(namespace: ScenarioNamespace) -> None:
    CommunicationTemplate.objects.create(
        label=f"{namespace.template_prefix} email volunteer",
        channel=CommunicationChannel.EMAIL,
        scope="planning_recipe",
        subject="Planning v{{ version_number }} pour {{ volunteer }}",
        body=(
            "Bonjour {{ volunteer }},\n"
            "vol {{ flight }} pour {{ shipment_reference }} "
            "({{ cartons }} colis)."
        ),
        is_active=True,
    )
    CommunicationTemplate.objects.create(
        label=f"{namespace.template_prefix} whatsapp volunteer",
        channel=CommunicationChannel.WHATSAPP,
        scope="planning_recipe",
        subject="",
        body=("Planning v{{ version_number }}: vol {{ flight }} " "pour {{ shipment_reference }}."),
        is_active=True,
    )
