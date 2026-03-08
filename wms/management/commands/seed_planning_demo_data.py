from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
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

DEMO_WEEK_START = date(2026, 3, 9)
DEMO_WEEK_END = date(2026, 3, 15)


@dataclass(frozen=True)
class DemoShipmentSpec:
    suffix: str
    destination_iata: str
    ready_at: datetime
    carton_codes: tuple[str, ...]
    item_quantity: int
    product_name: str


class Command(BaseCommand):
    help = "Seed a coherent fictive planning dataset for local verification."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario",
            default="demo",
            help="Scenario slug used to namespace the demo dataset",
        )
        parser.add_argument(
            "--solve",
            action="store_true",
            help="Prepare and solve the seeded planning run after creating the dataset",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        scenario_slug = slugify(options["scenario"]).strip("-") or "demo"
        dataset = self._seed_dataset(scenario_slug)
        version = None

        if options["solve"]:
            self._reset_run(dataset["run"])
            prepare_run_inputs(dataset["run"])
            dataset["run"].refresh_from_db()
            if dataset["run"].status != PlanningRunStatus.READY:
                raise CommandError(
                    f"Scenario {scenario_slug} seeded but validation failed: "
                    f"{dataset['run'].validation_summary}"
                )
            version = solve_run(dataset["run"])
            dataset["run"].refresh_from_db()

        assignments = version.assignments.count() if version is not None else 0
        self.stdout.write(
            self.style.SUCCESS(
                f"Scenario {scenario_slug} ready: "
                f"run={dataset['run'].pk} "
                f"status={dataset['run'].status} "
                f"shipments={len(dataset['shipments'])} "
                f"volunteers={len(dataset['volunteers'])} "
                f"flights={len(dataset['flights'])} "
                f"assignments={assignments}"
            )
        )

    def _resolve_destination(
        self,
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

    def _seed_dataset(self, scenario_slug: str) -> dict[str, object]:
        label = f"[DEMO {scenario_slug}]"
        ref_prefix = f"DEMO-{scenario_slug.upper().replace('-', '-')}"
        planner = self._get_or_create_user(
            username=f"planning-demo-{scenario_slug}",
            email=f"planning-demo-{scenario_slug}@example.com",
            first_name="Planning",
            last_name=f"Demo {scenario_slug}",
        )
        association_user = self._get_or_create_user(
            username=f"association-demo-{scenario_slug}",
            email=f"association-demo-{scenario_slug}@example.com",
            first_name="Association",
            last_name=f"Demo {scenario_slug}",
        )
        volunteer_users = [
            self._get_or_create_user(
                username=f"alice-demo-{scenario_slug}",
                email=f"alice-{scenario_slug}@example.com",
                first_name="Alice",
                last_name="Volunteer",
            ),
            self._get_or_create_user(
                username=f"bob-demo-{scenario_slug}",
                email=f"bob-{scenario_slug}@example.com",
                first_name="Bob",
                last_name="Volunteer",
            ),
        ]

        shipper_contact = Contact.objects.get_or_create(
            name=f"{label} Association Source",
            defaults={
                "contact_type": ContactType.ORGANIZATION,
                "is_active": True,
            },
        )[0]
        correspondent_abj = Contact.objects.get_or_create(
            name=f"{label} Correspondant ABJ",
            defaults={
                "contact_type": ContactType.ORGANIZATION,
                "is_active": True,
            },
        )[0]
        correspondent_dkr = Contact.objects.get_or_create(
            name=f"{label} Correspondant DKR",
            defaults={
                "contact_type": ContactType.ORGANIZATION,
                "is_active": True,
            },
        )[0]

        profile, _ = AssociationProfile.objects.get_or_create(
            user=association_user,
            defaults={
                "contact": shipper_contact,
                "notification_emails": f"ops-{scenario_slug}@example.com",
            },
        )
        if profile.contact_id != shipper_contact.pk:
            profile.contact = shipper_contact
            profile.notification_emails = f"ops-{scenario_slug}@example.com"
            profile.save(update_fields=["contact", "notification_emails"])
        AssociationPortalContact.objects.update_or_create(
            profile=profile,
            email=f"ops-{scenario_slug}@example.com",
            defaults={
                "position": 1,
                "first_name": "Ada",
                "last_name": "Ops",
                "is_administrative": True,
                "is_shipping": False,
                "is_billing": False,
                "is_active": True,
            },
        )
        AssociationPortalContact.objects.update_or_create(
            profile=profile,
            email=f"shipping-{scenario_slug}@example.com",
            defaults={
                "position": 2,
                "first_name": "Sam",
                "last_name": "Shipping",
                "is_administrative": False,
                "is_shipping": True,
                "is_billing": False,
                "is_active": True,
            },
        )

        destinations = {
            "ABJ": self._resolve_destination(
                iata_code="ABJ",
                city="Abidjan",
                country="Cote d'Ivoire",
                correspondent_contact=correspondent_abj,
            ),
            "DKR": self._resolve_destination(
                iata_code="DKR",
                city="Dakar",
                country="Senegal",
                correspondent_contact=correspondent_dkr,
            ),
        }

        parameter_set, _ = PlanningParameterSet.objects.update_or_create(
            name=f"DEMO {scenario_slug}",
            defaults={
                "notes": f"Seeded planning demo dataset for scenario {scenario_slug}.",
                "status": "draft",
                "is_current": False,
            },
        )
        PlanningDestinationRule.objects.update_or_create(
            parameter_set=parameter_set,
            destination=destinations["ABJ"],
            defaults={
                "label": f"{label} ABJ",
                "weekly_frequency": 2,
                "max_cartons_per_flight": 6,
                "priority": 5,
                "is_active": True,
            },
        )
        PlanningDestinationRule.objects.update_or_create(
            parameter_set=parameter_set,
            destination=destinations["DKR"],
            defaults={
                "label": f"{label} DKR",
                "weekly_frequency": 1,
                "max_cartons_per_flight": 4,
                "priority": 3,
                "is_active": True,
            },
        )

        warehouse, _ = Warehouse.objects.get_or_create(
            name=f"DEMO Warehouse {scenario_slug}",
            defaults={"code": f"D{scenario_slug[:6].upper()}"},
        )
        location, _ = Location.objects.get_or_create(
            warehouse=warehouse,
            zone="D",
            aisle="01",
            shelf="01",
        )

        categories = {
            "medical": ProductCategory.objects.get_or_create(name=f"{label} Medical")[0],
            "school": ProductCategory.objects.get_or_create(name=f"{label} School")[0],
        }
        products = {
            "Wheelchair Kit": Product.objects.get_or_create(
                name=f"{label} Wheelchair Kit",
                defaults={
                    "category": categories["medical"],
                    "default_location": location,
                },
            )[0],
            "School Kit": Product.objects.get_or_create(
                name=f"{label} School Kit",
                defaults={
                    "category": categories["school"],
                    "default_location": location,
                },
            )[0],
        }
        lots = {
            name: ProductLot.objects.get_or_create(
                product=product,
                location=location,
                defaults={"quantity_on_hand": 100},
            )[0]
            for name, product in products.items()
        }
        ShipmentUnitEquivalenceRule.objects.update_or_create(
            label=f"{label} Medical x2",
            defaults={
                "category": categories["medical"],
                "units_per_item": 2,
                "priority": 1,
                "is_active": True,
            },
        )
        ShipmentUnitEquivalenceRule.objects.update_or_create(
            label=f"{label} School x1",
            defaults={
                "category": categories["school"],
                "units_per_item": 1,
                "priority": 2,
                "is_active": True,
            },
        )

        shipment_specs = (
            DemoShipmentSpec(
                suffix="001",
                destination_iata="ABJ",
                ready_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
                carton_codes=(f"{ref_prefix}-C1", f"{ref_prefix}-C2"),
                item_quantity=1,
                product_name="Wheelchair Kit",
            ),
            DemoShipmentSpec(
                suffix="002",
                destination_iata="ABJ",
                ready_at=datetime(2026, 3, 10, 10, 0, tzinfo=UTC),
                carton_codes=(f"{ref_prefix}-C3",),
                item_quantity=1,
                product_name="Wheelchair Kit",
            ),
            DemoShipmentSpec(
                suffix="003",
                destination_iata="DKR",
                ready_at=datetime(2026, 3, 11, 8, 30, tzinfo=UTC),
                carton_codes=(f"{ref_prefix}-C4",),
                item_quantity=2,
                product_name="School Kit",
            ),
        )
        shipments = [
            self._upsert_shipment(
                ref_prefix=ref_prefix,
                spec=spec,
                shipper_contact=shipper_contact,
                destination=destinations[spec.destination_iata],
                product_lot=lots[spec.product_name],
                created_by=planner,
            )
            for spec in shipment_specs
        ]

        volunteers = [
            self._upsert_volunteer(
                user=volunteer_users[0],
                scenario_slug=scenario_slug,
                city="Paris",
                max_colis_vol=4,
                availability_specs=(
                    (DEMO_WEEK_START + timedelta(days=1), time(8, 30), time(12, 0)),
                    (DEMO_WEEK_START + timedelta(days=2), time(8, 30), time(12, 0)),
                ),
            ),
            self._upsert_volunteer(
                user=volunteer_users[1],
                scenario_slug=scenario_slug,
                city="Lyon",
                max_colis_vol=2,
                availability_specs=(
                    (DEMO_WEEK_START + timedelta(days=1), time(9, 0), time(11, 30)),
                ),
            ),
        ]

        batch, _ = FlightSourceBatch.objects.update_or_create(
            source="demo",
            file_name=f"planning-demo-{scenario_slug}.json",
            defaults={
                "period_start": DEMO_WEEK_START,
                "period_end": DEMO_WEEK_END,
                "status": FlightSourceBatchStatus.IMPORTED,
                "notes": f"Demo planning flights for scenario {scenario_slug}.",
            },
        )
        flights = [
            Flight.objects.update_or_create(
                batch=batch,
                flight_number="AF702",
                departure_date=DEMO_WEEK_START + timedelta(days=1),
                defaults={
                    "departure_time": time(10, 15),
                    "arrival_time": time(15, 45),
                    "origin_iata": "CDG",
                    "destination_iata": "ABJ",
                    "destination": destinations["ABJ"],
                    "capacity_units": 8,
                },
            )[0],
            Flight.objects.update_or_create(
                batch=batch,
                flight_number="AF718",
                departure_date=DEMO_WEEK_START + timedelta(days=2),
                defaults={
                    "departure_time": time(9, 40),
                    "arrival_time": time(13, 5),
                    "origin_iata": "CDG",
                    "destination_iata": "DKR",
                    "destination": destinations["DKR"],
                    "capacity_units": 6,
                },
            )[0],
        ]

        self._ensure_communication_templates(scenario_slug)

        run, _ = PlanningRun.objects.update_or_create(
            week_start=DEMO_WEEK_START,
            week_end=DEMO_WEEK_END,
            created_by=planner,
            parameter_set=parameter_set,
            defaults={
                "flight_mode": PlanningRunFlightMode.EXCEL,
                "flight_batch": batch,
                "status": PlanningRunStatus.DRAFT,
                "validation_summary": {},
                "solver_payload": {},
                "solver_result": {},
                "log_excerpt": f"demo:{scenario_slug}",
            },
        )
        if run.flight_batch_id != batch.pk or run.flight_mode != PlanningRunFlightMode.EXCEL:
            run.flight_batch = batch
            run.flight_mode = PlanningRunFlightMode.EXCEL
            run.status = PlanningRunStatus.DRAFT
            run.validation_summary = {}
            run.solver_payload = {}
            run.solver_result = {}
            run.log_excerpt = f"demo:{scenario_slug}"
            run.save(
                update_fields=[
                    "flight_batch",
                    "flight_mode",
                    "status",
                    "validation_summary",
                    "solver_payload",
                    "solver_result",
                    "log_excerpt",
                    "updated_at",
                ]
            )

        return {
            "run": run,
            "shipments": shipments,
            "volunteers": volunteers,
            "flights": flights,
        }

    def _get_or_create_user(self, *, username: str, email: str, first_name: str, last_name: str):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        needs_update = False
        for field, value in {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
        }.items():
            if getattr(user, field) != value:
                setattr(user, field, value)
                needs_update = True
        if created:
            user.set_unusable_password()
            needs_update = True
        if needs_update:
            update_fields = ["email", "first_name", "last_name"]
            if created:
                update_fields.append("password")
            user.save(update_fields=update_fields)
        return user

    def _upsert_shipment(
        self,
        *,
        ref_prefix: str,
        spec: DemoShipmentSpec,
        shipper_contact: Contact,
        destination: Destination,
        product_lot: ProductLot,
        created_by,
    ) -> Shipment:
        shipment, _ = Shipment.objects.update_or_create(
            reference=f"{ref_prefix}-{spec.suffix}",
            defaults={
                "status": ShipmentStatus.PACKED,
                "shipper_name": shipper_contact.name,
                "shipper_contact_ref": shipper_contact,
                "recipient_name": f"Recipient {spec.destination_iata}",
                "destination": destination,
                "destination_address": f"{destination.city} airport",
                "destination_country": destination.country,
                "ready_at": spec.ready_at,
                "created_by": created_by,
            },
        )
        for index, carton_code in enumerate(spec.carton_codes, start=1):
            carton, _ = Carton.objects.update_or_create(
                code=carton_code,
                defaults={
                    "shipment": shipment,
                    "current_location": product_lot.location,
                    "status": "packed",
                    "notes": f"Demo carton {index} for {shipment.reference}.",
                },
            )
            CartonItem.objects.update_or_create(
                carton=carton,
                product_lot=product_lot,
                defaults={"quantity": spec.item_quantity},
            )
        return shipment

    def _upsert_volunteer(
        self,
        *,
        user,
        scenario_slug: str,
        city: str,
        max_colis_vol: int,
        availability_specs: tuple[tuple[date, time, time], ...],
    ) -> VolunteerProfile:
        volunteer, _ = VolunteerProfile.objects.get_or_create(
            user=user,
            defaults={
                "phone": f"0600{scenario_slug[:4].ljust(4, '0')}",
                "city": city,
                "country": "France",
                "is_active": True,
            },
        )
        update_fields = []
        if volunteer.city != city:
            volunteer.city = city
            update_fields.append("city")
        if volunteer.country != "France":
            volunteer.country = "France"
            update_fields.append("country")
        if not volunteer.is_active:
            volunteer.is_active = True
            update_fields.append("is_active")
        if update_fields:
            volunteer.save(update_fields=update_fields)
        VolunteerConstraint.objects.update_or_create(
            volunteer=volunteer,
            defaults={"max_colis_vol": max_colis_vol},
        )
        for availability_date, start_time, end_time in availability_specs:
            VolunteerAvailability.objects.update_or_create(
                volunteer=volunteer,
                date=availability_date,
                start_time=start_time,
                defaults={"end_time": end_time},
            )
        return volunteer

    def _ensure_communication_templates(self, scenario_slug: str) -> None:
        CommunicationTemplate.objects.update_or_create(
            label=f"DEMO {scenario_slug} email volunteer",
            channel=CommunicationChannel.EMAIL,
            defaults={
                "scope": "planning_demo",
                "subject": "Planning v{{ version_number }} pour {{ volunteer }}",
                "body": (
                    "Bonjour {{ volunteer }},\n"
                    "vol {{ flight }} pour {{ shipment_reference }} "
                    "({{ cartons }} colis)."
                ),
                "is_active": True,
            },
        )
        CommunicationTemplate.objects.update_or_create(
            label=f"DEMO {scenario_slug} whatsapp volunteer",
            channel=CommunicationChannel.WHATSAPP,
            defaults={
                "scope": "planning_demo",
                "subject": "",
                "body": (
                    "Planning v{{ version_number }}: vol {{ flight }} "
                    "pour {{ shipment_reference }}."
                ),
                "is_active": True,
            },
        )

    def _reset_run(self, run: PlanningRun) -> None:
        run.versions.all().delete()
        run.issues.all().delete()
        run.shipment_snapshots.all().delete()
        run.volunteer_snapshots.all().delete()
        run.flight_snapshots.all().delete()
        run.status = PlanningRunStatus.DRAFT
        run.validation_summary = {}
        run.solver_payload = {}
        run.solver_result = {}
        run.save(
            update_fields=[
                "status",
                "validation_summary",
                "solver_payload",
                "solver_result",
                "updated_at",
            ]
        )
