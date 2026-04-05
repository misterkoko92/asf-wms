from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.text import slugify

from contacts.models import Contact, ContactAddress, ContactType
from wms.billing_document_handlers import (
    create_billing_draft,
    create_credit_note_for_invoice,
    create_replacement_invoice_from_invoice,
    issue_billing_document,
    record_billing_payment,
)
from wms.billing_permissions import BILLING_STAFF_GROUP_NAME
from wms.carton_status_events import set_carton_status
from wms.document_scan import DocumentScanStatus
from wms.document_scan_queue import (
    DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
    DOCUMENT_SCAN_QUEUE_SOURCE,
    DOCUMENT_SCAN_QUEUE_TARGET,
)
from wms.models import (
    AccountDocument,
    AccountDocumentType,
    AssociationBillingChangeRequest,
    AssociationBillingChangeRequestStatus,
    AssociationBillingFrequency,
    AssociationBillingGroupingMode,
    AssociationBillingProfile,
    AssociationPortalContact,
    AssociationProfile,
    AssociationRecipient,
    BillingAssociationPriceOverride,
    BillingComputationProfile,
    BillingDocument,
    BillingDocumentCorrectionState,
    BillingDocumentKind,
    BillingDocumentStatus,
    BillingIssue,
    BillingIssueStatus,
    BillingPaymentMethod,
    BillingServiceCatalogItem,
    Carton,
    CartonItem,
    CartonStatus,
    CommunicationChannel,
    CommunicationTemplate,
    Destination,
    DocumentReviewStatus,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Location,
    Order,
    OrderDocument,
    OrderDocumentType,
    OrderLine,
    OrderReviewStatus,
    OrderStatus,
    PlanningRun,
    Product,
    ProductCategory,
    ProductKitItem,
    ProductLot,
    ProductLotStatus,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicAccountRequestType,
    PublicOrderLink,
    Receipt,
    ReceiptLine,
    ReceiptShipmentAllocation,
    ReceiptStatus,
    ReceiptType,
    Shipment,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    ShipmentUnitEquivalenceRule,
    ShipmentValidationStatus,
    VolunteerAvailability,
    VolunteerConstraint,
    VolunteerProfile,
    VolunteerUnavailability,
    Warehouse,
)
from wms.planning.recipe_dataset import seed_recipe_dataset
from wms.portal_recipient_sync import sync_association_recipient_to_contact
from wms.reset_operational_data import reset_operational_data
from wms.scan_permissions import PREPARATEUR_GROUP_NAME
from wms.shipment_party_setup import ensure_shipment_shipper

DEFAULT_LOCAL_PASSWORD = "pass1234"  # pragma: allowlist secret  # nosec B105


@dataclass(frozen=True)
class LocalExhaustiveSeedSummary:
    scenario_slug: str
    users_count: int
    shipments_count: int
    orders_count: int
    receipts_count: int
    billing_documents_count: int
    integration_events_count: int
    planning_runs_count: int


def normalize_local_exhaustive_scenario_slug(raw_value: str) -> str:
    return slugify(raw_value).strip("-") or "local-exhaustive"


def seed_local_exhaustive_dataset(
    *,
    scenario_slug: str,
    fresh: bool = False,
    with_planning_solve: bool = False,
    with_demo_documents: bool = False,
    with_queue_backlog: bool = False,
    with_e2e_baseline: bool = False,
) -> LocalExhaustiveSeedSummary:
    normalized_slug = normalize_local_exhaustive_scenario_slug(scenario_slug)
    namespace = LocalExhaustiveSeedNamespace.from_slug(normalized_slug)
    if fresh:
        reset_operational_data(apply=True)
    _seed_shared_references(
        namespace,
        with_queue_backlog=with_queue_backlog,
        with_demo_documents=with_demo_documents,
        with_e2e_baseline=with_e2e_baseline,
    )
    _seed_planning_recipe(namespace, solve=with_planning_solve)
    return LocalExhaustiveSeedSummary(
        scenario_slug=namespace.slug,
        users_count=get_user_model().objects.filter(username__icontains=namespace.slug).count(),
        shipments_count=Shipment.objects.filter(
            reference__startswith=namespace.shipment_prefix
        ).count(),
        orders_count=Order.objects.filter(shipper_name__contains=namespace.label).count(),
        receipts_count=Receipt.objects.filter(notes__contains=namespace.label).count(),
        billing_documents_count=BillingDocument.objects.filter(
            association_profile__user__username__contains=namespace.slug
        ).count(),
        integration_events_count=IntegrationEvent.objects.filter(
            payload__scenario=namespace.slug
        ).count(),
        planning_runs_count=PlanningRun.objects.filter(
            parameter_set__name__icontains=namespace.slug
        ).count(),
    )


def render_local_exhaustive_seed_summary(summary: LocalExhaustiveSeedSummary) -> str:
    lines = [
        (
            f"Scenario {summary.scenario_slug} ready: "
            f"users={summary.users_count} "
            f"shipments={summary.shipments_count} "
            f"orders={summary.orders_count} "
            f"receipts={summary.receipts_count} "
            f"billing_documents={summary.billing_documents_count} "
            f"events={summary.integration_events_count} "
            f"planning_runs={summary.planning_runs_count}"
        ),
        "Users:",
        f"- staff: scan-{summary.scenario_slug}-staff / {DEFAULT_LOCAL_PASSWORD}",
        f"- billing: scan-{summary.scenario_slug}-billing / {DEFAULT_LOCAL_PASSWORD}",
        f"- admin: scan-{summary.scenario_slug}-admin / {DEFAULT_LOCAL_PASSWORD}",
        f"- portal A: portal-{summary.scenario_slug}-a / {DEFAULT_LOCAL_PASSWORD}",
        f"- portal B: portal-{summary.scenario_slug}-b / {DEFAULT_LOCAL_PASSWORD}",
        f"- volunteer: volunteer-{summary.scenario_slug}-alice / {DEFAULT_LOCAL_PASSWORD}",
        "URLs:",
        "- scan dashboard: /scan/dashboard/",
        "- shipments tracking: /scan/shipments-tracking/",
        "- orders: /scan/orders/",
        "- billing: /scan/billing/",
        "- portal: /portal/",
        "- volunteer portal: /volunteer/",
    ]
    return "\n".join(lines)


@dataclass(frozen=True)
class LocalExhaustiveSeedNamespace:
    slug: str
    label: str
    upper_slug: str
    shipment_prefix: str

    @classmethod
    def from_slug(cls, slug: str) -> LocalExhaustiveSeedNamespace:
        normalized = normalize_local_exhaustive_scenario_slug(slug)
        upper_slug = normalized.upper().replace("-", "-")
        return cls(
            slug=normalized,
            label=f"[LOCAL {normalized}]",
            upper_slug=upper_slug,
            shipment_prefix=f"LOCAL-{upper_slug}",
        )


def _seed_shared_references(
    namespace: LocalExhaustiveSeedNamespace,
    *,
    with_queue_backlog: bool,
    with_demo_documents: bool,
    with_e2e_baseline: bool,
) -> None:
    _seed_groups()
    staff_user = _upsert_user(
        username=f"scan-{namespace.slug}-staff",
        email=_scenario_email("scan-staff", namespace),
        is_staff=True,
    )
    billing_user = _upsert_user(
        username=f"scan-{namespace.slug}-billing",
        email=_scenario_email("scan-billing", namespace),
        is_staff=True,
    )
    superuser = _upsert_user(
        username=f"scan-{namespace.slug}-admin",
        email=_scenario_email("scan-admin", namespace),
        is_staff=True,
        is_superuser=True,
    )
    billing_group = Group.objects.get(name=BILLING_STAFF_GROUP_NAME)
    billing_user.groups.add(billing_group)

    _warehouse, main_location, overflow_location = _ensure_locations(namespace)
    categories, products = _ensure_catalog(
        namespace,
        locations={"main": main_location, "overflow": overflow_location},
    )
    _ensure_equivalence_rules(namespace, categories)
    _ensure_communication_templates(namespace)

    association_a = _ensure_association_profile(
        namespace,
        code="a",
        email_local="portal-a",
    )
    association_b = _ensure_association_profile(
        namespace,
        code="b",
        email_local="portal-b",
    )
    _ensure_portal_contacts(namespace, association_a, code="a")
    _ensure_portal_contacts(namespace, association_b, code="b")
    ensure_shipment_shipper(association_a.contact)
    ensure_shipment_shipper(association_b.contact)
    _ensure_billing_references(
        namespace,
        association_profiles=[association_a, association_b],
    )
    if superuser:
        superuser.email = _scenario_email("scan-admin", namespace)
        superuser.save(update_fields=["email"])

    destination_a = _ensure_destination(
        namespace,
        code="ABJ",
        city="Abidjan",
        country="Cote d'Ivoire",
    )
    destination_b = _ensure_destination(namespace, code="DKR", city="Dakar", country="Senegal")
    recipient_a = _ensure_association_recipient(
        namespace,
        association_profile=association_a,
        destination=destination_a,
        code="alpha",
        is_active=True,
    )
    recipient_b = _ensure_association_recipient(
        namespace,
        association_profile=association_b,
        destination=destination_b,
        code="bravo",
        is_active=True,
    )
    _ensure_association_recipient(
        namespace,
        association_profile=association_b,
        destination=destination_b,
        code="charlie",
        is_active=False,
    )

    lots = _ensure_product_lots(
        namespace,
        products=products,
        locations={"main": main_location, "overflow": overflow_location},
    )

    staff_user.groups.add(Group.objects.get(name=PREPARATEUR_GROUP_NAME))
    shipments = _seed_operational_flow(
        namespace,
        staff_user=staff_user,
        billing_user=billing_user,
        association_profiles=[association_a, association_b],
        destinations=[destination_a, destination_b],
        recipients=[recipient_a, recipient_b],
        lots=lots,
        with_queue_backlog=with_queue_backlog,
    )
    _seed_portal_and_public_flow(
        namespace,
        association_profiles=[association_a, association_b],
        products=products,
        created_by=staff_user,
        with_demo_documents=with_demo_documents,
        shipments=shipments,
    )
    _seed_receipts_and_billing_flow(
        namespace,
        association_profiles=[association_a, association_b],
        products=products,
        lots=lots,
        shipments=shipments,
        main_location=main_location,
        created_by=billing_user,
    )
    _seed_volunteer_profiles(namespace)
    if with_e2e_baseline:
        _seed_e2e_baseline(
            namespace,
            association_profile=association_a,
            location=main_location,
            product=products["wheelchair"],
            created_by=staff_user,
        )


def _seed_groups() -> None:
    Group.objects.get_or_create(name=BILLING_STAFF_GROUP_NAME)
    Group.objects.get_or_create(name=PREPARATEUR_GROUP_NAME)


def _upsert_user(
    *,
    username: str,
    email: str,
    is_staff: bool = False,
    is_superuser: bool = False,
):
    user_model = get_user_model()
    user, _created = user_model.objects.update_or_create(
        username=username,
        defaults={
            "email": email,
            "is_staff": is_staff,
            "is_superuser": is_superuser,
            "is_active": True,
            "last_login": timezone.now(),
        },
    )
    user.set_password(DEFAULT_LOCAL_PASSWORD)
    user.save(
        update_fields=[
            "email",
            "is_staff",
            "is_superuser",
            "is_active",
            "last_login",
            "password",
        ]
    )
    return user


def _scenario_email(local_part: str, namespace: LocalExhaustiveSeedNamespace) -> str:
    return f"{local_part}-{namespace.slug}@example.test"


def _ensure_locations(namespace: LocalExhaustiveSeedNamespace):
    warehouse, _ = Warehouse.objects.get_or_create(
        code=f"L{namespace.slug[:7].upper()}",
        defaults={"name": f"{namespace.label} Main warehouse"},
    )
    if warehouse.name != f"{namespace.label} Main warehouse":
        warehouse.name = f"{namespace.label} Main warehouse"
        warehouse.save(update_fields=["name"])
    location, _ = Location.objects.get_or_create(
        warehouse=warehouse,
        zone="A",
        aisle="01",
        shelf="001",
    )
    overflow_warehouse, _ = Warehouse.objects.get_or_create(
        code=f"O{namespace.slug[:7].upper()}",
        defaults={"name": f"{namespace.label} Overflow warehouse"},
    )
    overflow_location, _ = Location.objects.get_or_create(
        warehouse=overflow_warehouse,
        zone="B",
        aisle="02",
        shelf="015",
    )
    return warehouse, location, overflow_location


def _ensure_catalog(
    namespace: LocalExhaustiveSeedNamespace,
    *,
    locations: dict[str, Location],
):
    aid, _ = ProductCategory.objects.get_or_create(name=f"{namespace.label} Aid")
    medical, _ = ProductCategory.objects.get_or_create(
        parent=aid,
        name=f"{namespace.label} Medical",
    )
    school, _ = ProductCategory.objects.get_or_create(
        parent=aid,
        name=f"{namespace.label} School",
    )
    kits, _ = ProductCategory.objects.get_or_create(
        parent=aid,
        name=f"{namespace.label} Kits",
    )
    consumables, _ = ProductCategory.objects.get_or_create(
        parent=medical,
        name=f"{namespace.label} Consumables",
    )

    wheelchair, _ = Product.objects.update_or_create(
        sku=f"{namespace.upper_slug}-WHEEL",
        defaults={
            "name": f"{namespace.label} Wheelchair",
            "brand": "ASF",
            "category": medical,
            "default_location": locations["main"],
            "is_active": True,
            "qr_code_image": f"qr_codes/{namespace.slug}-wheelchair.png",
        },
    )
    school_kit_component, _ = Product.objects.update_or_create(
        sku=f"{namespace.upper_slug}-SCHOOL",
        defaults={
            "name": f"{namespace.label} School Kit",
            "brand": "ASF",
            "category": school,
            "default_location": locations["main"],
            "is_active": True,
            "qr_code_image": f"qr_codes/{namespace.slug}-school-kit.png",
        },
    )
    family_kit, _ = Product.objects.update_or_create(
        sku=f"{namespace.upper_slug}-FAMILYKIT",
        defaults={
            "name": f"{namespace.label} Family Kit",
            "brand": "ASF",
            "category": kits,
            "default_location": locations["main"],
            "is_active": True,
            "qr_code_image": f"qr_codes/{namespace.slug}-family-kit.png",
        },
    )
    thermometer, _ = Product.objects.update_or_create(
        sku=f"{namespace.upper_slug}-THERMO",
        defaults={
            "name": f"{namespace.label} Thermometer",
            "brand": "ASF",
            "category": consumables,
            "default_location": locations["overflow"],
            "is_active": True,
            "qr_code_image": f"qr_codes/{namespace.slug}-thermometer.png",
        },
    )
    blanket, _ = Product.objects.update_or_create(
        sku=f"{namespace.upper_slug}-BLANKET",
        defaults={
            "name": f"{namespace.label} Blanket",
            "brand": "ASF",
            "category": kits,
            "default_location": locations["overflow"],
            "is_active": True,
            "qr_code_image": f"qr_codes/{namespace.slug}-blanket.png",
        },
    )
    archived_product, _ = Product.objects.update_or_create(
        sku=f"{namespace.upper_slug}-ARCHIVE",
        defaults={
            "name": f"{namespace.label} Archived Product",
            "brand": "ASF",
            "category": school,
            "default_location": locations["overflow"],
            "is_active": False,
            "qr_code_image": f"qr_codes/{namespace.slug}-archived.png",
        },
    )
    ProductKitItem.objects.update_or_create(
        kit=family_kit,
        component=school_kit_component,
        defaults={"quantity": 2},
    )
    return (
        {
            "aid": aid,
            "medical": medical,
            "school": school,
            "kits": kits,
            "consumables": consumables,
        },
        {
            "wheelchair": wheelchair,
            "school": school_kit_component,
            "family_kit": family_kit,
            "thermometer": thermometer,
            "blanket": blanket,
            "archived": archived_product,
        },
    )


def _ensure_product_lots(
    namespace: LocalExhaustiveSeedNamespace,
    *,
    products: dict[str, Product],
    locations: dict[str, Location],
) -> dict[str, ProductLot]:
    lot_specs = {
        "wheelchair": (
            products["wheelchair"],
            f"{namespace.upper_slug}-WH-01",
            ProductLotStatus.AVAILABLE,
            30,
            0,
            locations["main"],
        ),
        "school": (
            products["school"],
            f"{namespace.upper_slug}-SC-01",
            ProductLotStatus.AVAILABLE,
            50,
            0,
            locations["main"],
        ),
        "family_kit": (
            products["family_kit"],
            f"{namespace.upper_slug}-FK-01",
            ProductLotStatus.HOLD,
            4,
            0,
            locations["main"],
        ),
        "thermometer": (
            products["thermometer"],
            f"{namespace.upper_slug}-TH-01",
            ProductLotStatus.AVAILABLE,
            5,
            0,
            locations["overflow"],
        ),
        "blanket_quarantine": (
            products["blanket"],
            f"{namespace.upper_slug}-BL-QUAR",
            ProductLotStatus.QUARANTINED,
            8,
            0,
            locations["overflow"],
        ),
        "blanket_expired": (
            products["blanket"],
            f"{namespace.upper_slug}-BL-EXP",
            ProductLotStatus.EXPIRED,
            2,
            0,
            locations["overflow"],
        ),
    }
    lots: dict[str, ProductLot] = {}
    for key, (
        product,
        lot_code,
        status,
        quantity_on_hand,
        quantity_reserved,
        location,
    ) in lot_specs.items():
        lot, _ = ProductLot.objects.update_or_create(
            product=product,
            lot_code=lot_code,
            defaults={
                "status": status,
                "quantity_on_hand": quantity_on_hand,
                "quantity_reserved": quantity_reserved,
                "location": location,
            },
        )
        lots[key] = lot
    return lots


def _ensure_equivalence_rules(
    namespace: LocalExhaustiveSeedNamespace,
    categories: dict[str, ProductCategory],
) -> None:
    ShipmentUnitEquivalenceRule.objects.update_or_create(
        label=f"{namespace.label} Medical x2",
        defaults={
            "category": categories["medical"],
            "units_per_item": 2,
            "priority": 1,
            "is_active": True,
        },
    )
    ShipmentUnitEquivalenceRule.objects.update_or_create(
        label=f"{namespace.label} Consumables x1",
        defaults={
            "category": categories["consumables"],
            "units_per_item": 1,
            "priority": 3,
            "is_active": True,
        },
    )
    ShipmentUnitEquivalenceRule.objects.update_or_create(
        label=f"{namespace.label} School x1",
        defaults={
            "category": categories["school"],
            "units_per_item": 1,
            "priority": 2,
            "is_active": True,
        },
    )


def _ensure_billing_references(
    namespace: LocalExhaustiveSeedNamespace,
    *,
    association_profiles: list[AssociationProfile],
) -> None:
    per_shipment_profile, _ = BillingComputationProfile.objects.update_or_create(
        code=f"LOCAL-{namespace.upper_slug}-SHIP",
        defaults={
            "label": f"{namespace.label} Shipment pricing",
            "is_active": True,
            "base_step_size": 1,
            "base_step_price": Decimal("24.00"),
            "allow_manual_override": True,
            "is_default_for_shipment_only": True,
        },
    )
    receipt_linked_profile, _ = BillingComputationProfile.objects.update_or_create(
        code=f"LOCAL-{namespace.upper_slug}-RECEIPT",
        defaults={
            "label": f"{namespace.label} Receipt-linked pricing",
            "is_active": True,
            "applies_when_receipts_linked": True,
            "base_step_size": 1,
            "base_step_price": Decimal("18.00"),
            "extra_unit_price": Decimal("4.00"),
            "allow_manual_override": True,
            "is_default_for_receipt_linked": True,
        },
    )
    transport_item, _ = BillingServiceCatalogItem.objects.update_or_create(
        label=f"{namespace.label} Transport handling",
        defaults={
            "description": "Local-only transport handling service",
            "service_type": "shipment",
            "default_unit_price": Decimal("24.00"),
            "default_currency": "EUR",
            "display_order": 10,
            "is_active": True,
        },
    )
    dossier_item, _ = BillingServiceCatalogItem.objects.update_or_create(
        label=f"{namespace.label} Dossier admin",
        defaults={
            "description": "Local-only dossier admin surcharge",
            "service_type": "admin",
            "default_unit_price": Decimal("12.50"),
            "default_currency": "EUR",
            "display_order": 20,
            "is_active": True,
        },
    )

    for profile, currency, frequency, grouping_mode, computation_profile in (
        (
            association_profiles[0],
            "EUR",
            AssociationBillingFrequency.PER_SHIPMENT,
            AssociationBillingGroupingMode.SINGLE_DOCUMENT,
            receipt_linked_profile,
        ),
        (
            association_profiles[1],
            "USD",
            AssociationBillingFrequency.MONTHLY,
            AssociationBillingGroupingMode.PER_SHIPMENT,
            per_shipment_profile,
        ),
    ):
        billing_profile, _ = AssociationBillingProfile.objects.update_or_create(
            association_profile=profile,
            defaults={
                "billing_frequency": frequency,
                "grouping_mode": grouping_mode,
                "default_currency": currency,
                "default_computation_profile": computation_profile,
                "billing_name_override": f"{profile.contact.name} Billing",
                "billing_address_override": "1 avenue locale\n75001 Paris\nFrance",
            },
        )
        BillingAssociationPriceOverride.objects.update_or_create(
            association_billing_profile=billing_profile,
            service_catalog_item=transport_item,
            computation_profile=None,
            defaults={
                "overridden_amount": Decimal("27.50"),
                "currency": currency,
                "notes": f"{namespace.label} transport override",
            },
        )
        BillingAssociationPriceOverride.objects.update_or_create(
            association_billing_profile=billing_profile,
            service_catalog_item=dossier_item,
            computation_profile=None,
            defaults={
                "overridden_amount": Decimal("9.50"),
                "currency": currency,
                "notes": f"{namespace.label} admin override",
            },
        )


def _ensure_communication_templates(namespace: LocalExhaustiveSeedNamespace) -> None:
    CommunicationTemplate.objects.update_or_create(
        label=f"LOCAL {namespace.slug} email volunteer",
        channel=CommunicationChannel.EMAIL,
        defaults={
            "scope": "local_exhaustive_seed",
            "subject": "Planning v{{ version_number }} pour {{ volunteer }}",
            "body": "Bonjour {{ volunteer }}, mission {{ flight }} pour {{ shipment_reference }}.",
            "is_active": True,
        },
    )
    CommunicationTemplate.objects.update_or_create(
        label=f"LOCAL {namespace.slug} whatsapp volunteer",
        channel=CommunicationChannel.WHATSAPP,
        defaults={
            "scope": "local_exhaustive_seed",
            "subject": "",
            "body": "Planning {{ version_number }}: vol {{ flight }} pour {{ shipment_reference }}.",
            "is_active": True,
        },
    )


def _ensure_association_profile(
    namespace: LocalExhaustiveSeedNamespace,
    *,
    code: str,
    email_local: str,
) -> AssociationProfile:
    user = _upsert_user(
        username=f"portal-{namespace.slug}-{code}",
        email=_scenario_email(email_local, namespace),
    )
    association_contact, _ = Contact.objects.get_or_create(
        name=f"{namespace.label} Association {code.upper()}",
        defaults={
            "contact_type": ContactType.ORGANIZATION,
            "email": _scenario_email(f"association-{code}", namespace),
            "phone": f"+3315550000{code}",
            "is_active": True,
        },
    )
    if association_contact.contact_type != ContactType.ORGANIZATION:
        association_contact.contact_type = ContactType.ORGANIZATION
    association_contact.email = _scenario_email(f"association-{code}", namespace)
    association_contact.is_active = True
    association_contact.save(update_fields=["contact_type", "email", "is_active"])
    ContactAddress.objects.update_or_create(
        contact=association_contact,
        label="Siege",
        defaults={
            "address_line1": f"{code.upper()} avenue locale",
            "postal_code": "75001",
            "city": "Paris",
            "country": "France",
            "is_default": True,
        },
    )
    profile, _ = AssociationProfile.objects.update_or_create(
        user=user,
        defaults={
            "contact": association_contact,
            "notification_emails": _scenario_email(f"ops-{code}", namespace),
            "must_change_password": False,  # nosec B105
        },
    )
    return profile


def _ensure_portal_contacts(
    namespace: LocalExhaustiveSeedNamespace,
    profile: AssociationProfile,
    *,
    code: str,
) -> None:
    AssociationPortalContact.objects.update_or_create(
        profile=profile,
        email=_scenario_email(f"admin-{code}", namespace),
        defaults={
            "position": 1,
            "first_name": "Ada",
            "last_name": f"Admin {code.upper()}",
            "phone": f"+3360000000{code}",
            "is_administrative": True,
            "is_shipping": False,
            "is_billing": True,
            "is_active": True,
        },
    )
    AssociationPortalContact.objects.update_or_create(
        profile=profile,
        email=_scenario_email(f"shipping-{code}", namespace),
        defaults={
            "position": 2,
            "first_name": "Sam",
            "last_name": f"Shipping {code.upper()}",
            "phone": f"+3361000000{code}",
            "is_administrative": False,
            "is_shipping": True,
            "is_billing": False,
            "is_active": True,
        },
    )


def _ensure_destination(
    namespace: LocalExhaustiveSeedNamespace,
    *,
    code: str,
    city: str,
    country: str,
) -> Destination:
    correspondent, _ = Contact.objects.get_or_create(
        name=f"{namespace.label} Correspondent {code}",
        defaults={
            "contact_type": ContactType.ORGANIZATION,
            "email": _scenario_email(f"correspondent-{code.lower()}", namespace),
            "is_active": True,
        },
    )
    destination, _ = Destination.objects.get_or_create(
        city=city,
        country=country,
        defaults={
            "iata_code": code,
            "correspondent_contact": correspondent,
            "is_active": True,
        },
    )
    destination.iata_code = code
    destination.correspondent_contact = correspondent
    destination.is_active = True
    destination.save(update_fields=["iata_code", "correspondent_contact", "is_active"])
    return destination


def _ensure_association_recipient(
    namespace: LocalExhaustiveSeedNamespace,
    *,
    association_profile: AssociationProfile,
    destination: Destination,
    code: str,
    is_active: bool,
) -> AssociationRecipient:
    recipient, _ = AssociationRecipient.objects.update_or_create(
        association_contact=association_profile.contact,
        destination=destination,
        name=f"{namespace.label} Recipient {code.upper()}",
        defaults={
            "structure_name": f"{namespace.label} Structure {code.upper()}",
            "contact_first_name": "Rita",
            "contact_last_name": f"Receiver {code.upper()}",
            "emails": _scenario_email(f"recipient-{code}", namespace),
            "phones": f"+2250102030{len(code)}",
            "address_line1": f"{code.upper()} boulevard logistique",
            "postal_code": "00000",
            "city": destination.city,
            "country": destination.country,
            "is_delivery_contact": True,
            "is_active": is_active,
        },
    )
    synced_contact = sync_association_recipient_to_contact(recipient)
    ShipmentRecipientOrganization.objects.filter(
        organization=synced_contact,
        destination=destination,
    ).update(validation_status=ShipmentValidationStatus.VALIDATED)
    return recipient


def _seed_operational_flow(
    namespace: LocalExhaustiveSeedNamespace,
    *,
    staff_user,
    billing_user,
    association_profiles: list[AssociationProfile],
    destinations: list[Destination],
    recipients: list[AssociationRecipient],
    lots: dict[str, ProductLot],
    with_queue_backlog: bool,
) -> dict[str, Shipment]:
    association_a, association_b = association_profiles
    destination_a, destination_b = destinations
    recipient_a, recipient_b = recipients

    draft_shipment = _upsert_shipment(
        reference=f"EXP-TEMP-{namespace.slug[:3].upper()}-01",
        namespace=namespace,
        status=ShipmentStatus.DRAFT,
        association_profile=association_a,
        recipient=recipient_a,
        destination=destination_a,
        created_by=staff_user,
    )
    picking_shipment = _upsert_shipment(
        reference=f"{namespace.shipment_prefix}-000",
        namespace=namespace,
        status=ShipmentStatus.PICKING,
        association_profile=association_b,
        recipient=recipient_b,
        destination=destination_b,
        created_by=staff_user,
    )
    packed_shipment = _upsert_shipment(
        reference=f"{namespace.shipment_prefix}-001",
        namespace=namespace,
        status=ShipmentStatus.PACKED,
        association_profile=association_a,
        recipient=recipient_a,
        destination=destination_a,
        created_by=staff_user,
    )
    planned_shipment = _upsert_shipment(
        reference=f"{namespace.shipment_prefix}-002",
        namespace=namespace,
        status=ShipmentStatus.PLANNED,
        association_profile=association_a,
        recipient=recipient_a,
        destination=destination_a,
        created_by=staff_user,
    )
    week_planned_shipment = _upsert_shipment(
        reference=f"{namespace.shipment_prefix}-002B",
        namespace=namespace,
        status=ShipmentStatus.PLANNED,
        association_profile=association_a,
        recipient=recipient_a,
        destination=destination_a,
        created_by=staff_user,
    )
    shipped_shipment = _upsert_shipment(
        reference=f"{namespace.shipment_prefix}-003",
        namespace=namespace,
        status=ShipmentStatus.SHIPPED,
        association_profile=association_a,
        recipient=recipient_a,
        destination=destination_a,
        created_by=staff_user,
    )
    correspondent_shipment = _upsert_shipment(
        reference=f"{namespace.shipment_prefix}-004",
        namespace=namespace,
        status=ShipmentStatus.RECEIVED_CORRESPONDENT,
        association_profile=association_b,
        recipient=recipient_b,
        destination=destination_b,
        created_by=staff_user,
    )
    delivered_open_shipment = _upsert_shipment(
        reference=f"{namespace.shipment_prefix}-005",
        namespace=namespace,
        status=ShipmentStatus.DELIVERED,
        association_profile=association_b,
        recipient=recipient_b,
        destination=destination_b,
        created_by=staff_user,
    )
    delivered_closed_shipment = _upsert_shipment(
        reference=f"{namespace.shipment_prefix}-006",
        namespace=namespace,
        status=ShipmentStatus.DELIVERED,
        association_profile=association_a,
        recipient=recipient_a,
        destination=destination_a,
        created_by=staff_user,
        closed_by=billing_user,
        closed_delta_hours=4,
    )
    disputed_shipment = _upsert_shipment(
        reference=f"{namespace.shipment_prefix}-007",
        namespace=namespace,
        status=ShipmentStatus.PLANNED,
        association_profile=association_b,
        recipient=recipient_b,
        destination=destination_b,
        created_by=staff_user,
        is_disputed=True,
    )

    _seed_tracking_events(staff_user, planned_shipment, [(ShipmentTrackingStatus.PLANNED, 96)])
    _seed_tracking_events(staff_user, week_planned_shipment, [(ShipmentTrackingStatus.PLANNED, 8)])
    _seed_tracking_events(staff_user, shipped_shipment, [(ShipmentTrackingStatus.BOARDING_OK, 84)])
    _seed_tracking_events(
        staff_user,
        correspondent_shipment,
        [(ShipmentTrackingStatus.RECEIVED_CORRESPONDENT, 78)],
    )
    _seed_tracking_events(
        staff_user,
        delivered_open_shipment,
        [
            (ShipmentTrackingStatus.PLANNED, 20),
            (ShipmentTrackingStatus.BOARDING_OK, 18),
            (ShipmentTrackingStatus.RECEIVED_CORRESPONDENT, 12),
            (ShipmentTrackingStatus.RECEIVED_RECIPIENT, 3),
        ],
    )
    _seed_tracking_events(
        staff_user,
        delivered_closed_shipment,
        [
            (ShipmentTrackingStatus.PLANNED, 30),
            (ShipmentTrackingStatus.BOARDING_OK, 28),
            (ShipmentTrackingStatus.RECEIVED_CORRESPONDENT, 20),
            (ShipmentTrackingStatus.RECEIVED_RECIPIENT, 8),
        ],
    )
    _seed_tracking_events(
        staff_user,
        disputed_shipment,
        [(ShipmentTrackingStatus.PLANNED, 40)],
    )

    _seed_carton(
        namespace,
        code="picking",
        lot=lots["wheelchair"],
        quantity=1,
        status=CartonStatus.PICKING,
        shipment=picking_shipment,
        destination=destination_b,
        user=staff_user,
    )
    _seed_carton(
        namespace,
        code="packed-ready",
        lot=lots["school"],
        quantity=2,
        status=CartonStatus.PACKED,
        shipment=None,
        destination=destination_a,
        user=staff_user,
    )
    _seed_carton(
        namespace,
        code="packed",
        lot=lots["wheelchair"],
        quantity=2,
        status=CartonStatus.PACKED,
        shipment=None,
        destination=destination_a,
        user=staff_user,
    )
    _seed_carton(
        namespace,
        code="assigned",
        lot=lots["school"],
        quantity=2,
        status=CartonStatus.ASSIGNED,
        shipment=week_planned_shipment,
        destination=destination_a,
        user=staff_user,
    )
    _seed_carton(
        namespace,
        code="labeled",
        lot=lots["school"],
        quantity=3,
        status=CartonStatus.LABELED,
        shipment=planned_shipment,
        destination=destination_a,
        user=staff_user,
    )
    _seed_carton(
        namespace,
        code="shipped",
        lot=lots["family_kit"],
        quantity=1,
        status=CartonStatus.SHIPPED,
        shipment=shipped_shipment,
        destination=destination_a,
        user=staff_user,
    )
    _seed_carton(
        namespace,
        code="draft",
        lot=lots["wheelchair"],
        quantity=1,
        status=CartonStatus.DRAFT,
        shipment=None,
        destination=destination_b,
        user=staff_user,
    )

    if with_queue_backlog:
        _seed_queue_backlog(namespace)
    _set_timestamp(draft_shipment, created_at=timezone.now() - timedelta(hours=90))
    _set_timestamp(picking_shipment, created_at=timezone.now() - timedelta(hours=84))
    _set_timestamp(planned_shipment, ready_at=timezone.now() - timedelta(days=4))
    _set_timestamp(week_planned_shipment, ready_at=timezone.now() - timedelta(hours=12))
    _set_timestamp(shipped_shipment, ready_at=timezone.now() - timedelta(days=7))
    _set_timestamp(delivered_closed_shipment, ready_at=timezone.now() - timedelta(days=45))
    return {
        "draft": draft_shipment,
        "picking": picking_shipment,
        "packed": packed_shipment,
        "planned_alert": planned_shipment,
        "planned_week": week_planned_shipment,
        "shipped": shipped_shipment,
        "received_correspondent": correspondent_shipment,
        "delivered_open": delivered_open_shipment,
        "delivered_closed": delivered_closed_shipment,
        "disputed": disputed_shipment,
    }


def _seed_portal_and_public_flow(
    namespace: LocalExhaustiveSeedNamespace,
    *,
    association_profiles: list[AssociationProfile],
    products: dict[str, Product],
    created_by,
    with_demo_documents: bool,
    shipments: dict[str, Shipment],
) -> None:
    association_a, association_b = association_profiles
    recipient_a = association_a.contact.association_recipients.order_by("id").first()
    recipient_b = association_b.contact.association_recipients.order_by("id").first()
    if recipient_a is None or recipient_b is None:
        return

    public_link, _ = PublicOrderLink.objects.update_or_create(
        label=f"{namespace.label} Public order link",
        defaults={"is_active": True},
    )
    public_request, _ = PublicAccountRequest.objects.update_or_create(
        email=_scenario_email("public-account", namespace),
        defaults={
            "link": public_link,
            "contact": association_b.contact,
            "account_type": PublicAccountRequestType.ASSOCIATION,
            "status": PublicAccountRequestStatus.PENDING,
            "association_name": association_b.contact.name,
            "phone": "+33170000001",
            "address_line1": "1 rue des associations",
            "postal_code": "75002",
            "city": "Paris",
            "country": "France",
            "notes": f"{namespace.label} public intake",
        },
    )

    portal_order = _upsert_order(
        namespace,
        reference=f"{namespace.shipment_prefix}-ORD-001",
        association_profile=association_a,
        recipient=recipient_a,
        created_by=created_by,
        status=OrderStatus.READY,
        review_status=OrderReviewStatus.APPROVED,
        public_link=None,
    )
    public_order = _upsert_order(
        namespace,
        reference=f"{namespace.shipment_prefix}-ORD-002",
        association_profile=association_b,
        recipient=recipient_b,
        created_by=created_by,
        status=OrderStatus.DRAFT,
        review_status=OrderReviewStatus.PENDING,
        public_link=public_link,
    )
    preparing_order = _upsert_order(
        namespace,
        reference=f"{namespace.shipment_prefix}-ORD-003",
        association_profile=association_a,
        recipient=recipient_a,
        created_by=created_by,
        status=OrderStatus.PREPARING,
        review_status=OrderReviewStatus.APPROVED,
        public_link=None,
    )
    reserved_order = _upsert_order(
        namespace,
        reference=f"{namespace.shipment_prefix}-ORD-004",
        association_profile=association_b,
        recipient=recipient_b,
        created_by=created_by,
        status=OrderStatus.RESERVED,
        review_status=OrderReviewStatus.APPROVED,
        public_link=None,
    )
    changes_requested_order = _upsert_order(
        namespace,
        reference=f"{namespace.shipment_prefix}-ORD-005",
        association_profile=association_b,
        recipient=recipient_b,
        created_by=created_by,
        status=OrderStatus.DRAFT,
        review_status=OrderReviewStatus.CHANGES_REQUESTED,
        public_link=None,
    )
    portal_order.shipment = shipments["packed"]
    portal_order.save(update_fields=["shipment"])
    OrderLine.objects.update_or_create(
        order=portal_order,
        product=products["wheelchair"],
        defaults={"quantity": 3, "reserved_quantity": 1, "prepared_quantity": 0},
    )
    OrderLine.objects.update_or_create(
        order=public_order,
        product=products["school"],
        defaults={"quantity": 5, "reserved_quantity": 0, "prepared_quantity": 0},
    )
    OrderLine.objects.update_or_create(
        order=preparing_order,
        product=products["family_kit"],
        defaults={"quantity": 2, "reserved_quantity": 2, "prepared_quantity": 1},
    )
    OrderLine.objects.update_or_create(
        order=reserved_order,
        product=products["thermometer"],
        defaults={"quantity": 4, "reserved_quantity": 2, "prepared_quantity": 0},
    )
    OrderLine.objects.update_or_create(
        order=changes_requested_order,
        product=products["blanket"],
        defaults={"quantity": 6, "reserved_quantity": 0, "prepared_quantity": 0},
    )
    _set_timestamp(reserved_order, created_at=timezone.now() - timedelta(hours=84))

    AssociationBillingChangeRequest.objects.update_or_create(
        association_profile=association_b,
        requested_frequency=AssociationBillingFrequency.MONTHLY,
        requested_grouping_mode=AssociationBillingGroupingMode.PER_SHIPMENT,
        defaults={
            "status": AssociationBillingChangeRequestStatus.PENDING,
            "requested_by": association_b.user,
            "review_comment": "",
        },
    )

    if with_demo_documents:
        _upsert_account_document(
            association_contact=association_a.contact,
            account_request=None,
            doc_type=AccountDocumentType.REGISTRATION_PROOF,
            status=DocumentReviewStatus.PENDING,
            uploaded_by=association_a.user,
            filename=f"{namespace.slug}-association-registration.pdf",
            content=b"%PDF-1.4 local association registration",
            scan_status=DocumentScanStatus.PENDING,
        )
        _upsert_account_document(
            association_contact=None,
            account_request=public_request,
            doc_type=AccountDocumentType.STATUTES,
            status=DocumentReviewStatus.APPROVED,
            uploaded_by=created_by,
            filename=f"{namespace.slug}-public-account-statutes.pdf",
            content=b"%PDF-1.4 local public statutes",
            scan_status=DocumentScanStatus.CLEAN,
        )
        _upsert_account_document(
            association_contact=association_b.contact,
            account_request=None,
            doc_type=AccountDocumentType.ACTIVITY_REPORT,
            status=DocumentReviewStatus.REJECTED,
            uploaded_by=association_b.user,
            filename=f"{namespace.slug}-activity-report.pdf",
            content=b"%PDF-1.4 local activity report",
            scan_status=DocumentScanStatus.ERROR,
        )
        _upsert_order_document(
            order=portal_order,
            doc_type=OrderDocumentType.INVOICE,
            status=DocumentReviewStatus.APPROVED,
            uploaded_by=created_by,
            filename=f"{namespace.slug}-portal-order-invoice.pdf",
            content=b"%PDF-1.4 local order invoice",
            scan_status=DocumentScanStatus.CLEAN,
        )
        _upsert_order_document(
            order=public_order,
            doc_type=OrderDocumentType.HUMANITARIAN_ATTESTATION,
            status=DocumentReviewStatus.PENDING,
            uploaded_by=created_by,
            filename=f"{namespace.slug}-public-order-humanitarian.pdf",
            content=b"%PDF-1.4 local humanitarian attestation",
            scan_status=DocumentScanStatus.PENDING,
        )


def _seed_receipts_and_billing_flow(
    namespace: LocalExhaustiveSeedNamespace,
    *,
    association_profiles: list[AssociationProfile],
    products: dict[str, Product],
    lots: dict[str, ProductLot],
    shipments: dict[str, Shipment],
    main_location: Location,
    created_by,
) -> None:
    association_a, association_b = association_profiles
    number_token = namespace.upper_slug.replace("-", "")[:8]

    BillingDocument.objects.filter(
        association_profile__user__username__contains=namespace.slug
    ).delete()
    ReceiptShipmentAllocation.objects.filter(
        shipment__reference__startswith=namespace.shipment_prefix
    ).delete()

    draft_receipt, _ = Receipt.objects.update_or_create(
        reference=f"REC-{number_token}-DRAFT",
        defaults={
            "receipt_type": ReceiptType.DONATION,
            "status": ReceiptStatus.DRAFT,
            "source_contact": association_b.contact,
            "warehouse": main_location.warehouse,
            "created_by": created_by,
            "notes": f"{namespace.label} draft receipt",
            "received_on": timezone.localdate() - timedelta(days=2),
        },
    )
    received_receipt, _ = Receipt.objects.update_or_create(
        reference=f"REC-{number_token}-001",
        defaults={
            "receipt_type": ReceiptType.ASSOCIATION,
            "status": ReceiptStatus.RECEIVED,
            "source_contact": association_a.contact,
            "warehouse": main_location.warehouse,
            "created_by": created_by,
            "notes": f"{namespace.label} billed receipt",
            "received_on": timezone.localdate() - timedelta(days=7),
            "carton_count": 3,
        },
    )
    external_receipt, _ = Receipt.objects.update_or_create(
        reference=f"REC-{number_token}-002",
        defaults={
            "receipt_type": ReceiptType.ASSOCIATION,
            "status": ReceiptStatus.RECEIVED,
            "source_contact": association_b.contact,
            "warehouse": main_location.warehouse,
            "created_by": created_by,
            "notes": f"{namespace.label} monthly receipt",
            "received_on": timezone.localdate() - timedelta(days=40),
            "carton_count": 2,
        },
    )
    del draft_receipt

    for receipt, line_specs in (
        (
            received_receipt,
            (
                (products["wheelchair"], 4, lots["wheelchair"]),
                (products["thermometer"], 2, lots["thermometer"]),
            ),
        ),
        (
            external_receipt,
            ((products["school"], 6, lots["school"]),),
        ),
    ):
        receipt.lines.all().delete()
        for product, quantity, lot in line_specs:
            ReceiptLine.objects.create(
                receipt=receipt,
                product=product,
                quantity=quantity,
                lot_code=lot.lot_code,
                lot_status=lot.status,
                location=lot.location,
                received_lot=lot,
                received_by=created_by,
                received_at=timezone.now() - timedelta(days=1),
            )

    ReceiptShipmentAllocation.objects.update_or_create(
        receipt=received_receipt,
        shipment=shipments["shipped"],
        defaults={
            "allocated_received_units": 2,
            "note": f"{namespace.label} allocation",
            "created_by": created_by,
        },
    )
    ReceiptShipmentAllocation.objects.update_or_create(
        receipt=received_receipt,
        shipment=shipments["delivered_closed"],
        defaults={
            "allocated_received_units": 1,
            "note": f"{namespace.label} allocation closed",
            "created_by": created_by,
        },
    )

    quote = create_billing_draft(
        association_profile=association_b,
        kind=BillingDocumentKind.QUOTE,
        shipment_ids=[shipments["delivered_open"].id],
        created_by=created_by,
        manual_lines=[
            {
                "label": f"{namespace.label} manual fee",
                "description": "Portal dossier setup",
                "amount": "15.00",
            }
        ],
        currency="USD",
    )
    issue_billing_document(document=quote)

    invoice_partial = create_billing_draft(
        association_profile=association_a,
        kind=BillingDocumentKind.INVOICE,
        shipment_ids=[shipments["shipped"].id],
        created_by=created_by,
        manual_lines=[
            {
                "label": f"{namespace.label} billing note",
                "description": "Manual correction line",
                "amount": "11.00",
            }
        ],
    )
    invoice_partial = issue_billing_document(
        document=invoice_partial,
        invoice_number=f"FAC-{number_token}-01",
    )
    invoice_partial = record_billing_payment(
        document=invoice_partial,
        amount="12.00",
        payment_method=BillingPaymentMethod.BANK_TRANSFER,
        reference=f"PAY-{number_token}-01",
        created_by=created_by,
    )
    BillingIssue.objects.update_or_create(
        document=invoice_partial,
        description=f"{namespace.label} amount mismatch under review",
        defaults={
            "status": BillingIssueStatus.OPEN,
            "reported_by": created_by,
        },
    )
    invoice_partial.refresh_from_db()

    corrected_invoice = create_billing_draft(
        association_profile=association_a,
        kind=BillingDocumentKind.INVOICE,
        shipment_ids=[shipments["delivered_closed"].id],
        created_by=created_by,
    )
    corrected_invoice = issue_billing_document(
        document=corrected_invoice,
        invoice_number=f"FAC-{number_token}-02",
    )
    create_credit_note_for_invoice(
        document=corrected_invoice,
        credit_note_number=f"AVO-{number_token}-01",
        created_by=created_by,
    )
    replacement_invoice = create_replacement_invoice_from_invoice(
        document=corrected_invoice,
        created_by=created_by,
    )
    issue_billing_document(
        document=replacement_invoice,
        invoice_number=f"FAC-{number_token}-03",
    )


def _seed_volunteer_profiles(namespace: LocalExhaustiveSeedNamespace) -> None:
    volunteer_specs = (
        {
            "username": f"volunteer-{namespace.slug}-alice",
            "email_local": "volunteer-alice",
            "first_name": "Alice",
            "last_name": "Local",
            "must_change_password": False,  # nosec B105
            "phone": "+33620000001",
            "city": "Paris",
            "availability": [(date(2026, 3, 10), time(9, 0), time(12, 0))],
            "max_colis_vol": 4,
        },
        {
            "username": f"volunteer-{namespace.slug}-bruno",
            "email_local": "volunteer-bruno",
            "first_name": "Bruno",
            "last_name": "Local",
            "must_change_password": True,  # nosec B105
            "phone": "+33620000002",
            "city": "Lyon",
            "availability": [(date(2026, 3, 11), time(14, 0), time(18, 0))],
            "max_colis_vol": 2,
        },
        {
            "username": f"volunteer-{namespace.slug}-claire",
            "email_local": "volunteer-claire",
            "first_name": "Claire",
            "last_name": "Local",
            "must_change_password": False,  # nosec B105
            "phone": "+33620000003",
            "city": "Marseille",
            "availability": [(date(2026, 3, 12), time(8, 0), time(16, 0))],
            "max_colis_vol": 6,
        },
    )
    for spec in volunteer_specs:
        user = _upsert_user(
            username=spec["username"],
            email=_scenario_email(spec["email_local"], namespace),
        )
        user.first_name = spec["first_name"]
        user.last_name = spec["last_name"]
        user.save(update_fields=["first_name", "last_name"])
        profile, _ = VolunteerProfile.objects.update_or_create(
            user=user,
            defaults={
                "phone": spec["phone"],
                "city": spec["city"],
                "country": "France",
                "must_change_password": spec["must_change_password"],
                "is_active": True,
            },
        )
        VolunteerConstraint.objects.update_or_create(
            volunteer=profile,
            defaults={"max_colis_vol": spec["max_colis_vol"]},
        )
        profile.availabilities.all().delete()
        for availability_date, start_time, end_time in spec["availability"]:
            VolunteerAvailability.objects.create(
                volunteer=profile,
                date=availability_date,
                start_time=start_time,
                end_time=end_time,
            )
        VolunteerUnavailability.objects.update_or_create(
            volunteer=profile,
            date=date(2026, 3, 15),
        )


def _seed_e2e_baseline(
    namespace: LocalExhaustiveSeedNamespace,
    *,
    association_profile: AssociationProfile,
    location: Location,
    product: Product,
    created_by,
) -> None:
    e2e_lot, _ = ProductLot.objects.update_or_create(
        product=product,
        lot_code=f"{namespace.upper_slug}-E2E-01",
        defaults={
            "status": ProductLotStatus.AVAILABLE,
            "quantity_on_hand": 12,
            "quantity_reserved": 0,
            "location": location,
        },
    )
    IntegrationEvent.objects.update_or_create(
        source="wms.email",
        target="mailer",
        event_type="send_email",
        external_id=f"{namespace.slug}-e2e-baseline",
        defaults={
            "direction": IntegrationDirection.OUTBOUND,
            "payload": {
                "scenario": namespace.slug,
                "kind": "e2e_baseline",
                "association": association_profile.contact.name,
                "lot": e2e_lot.lot_code,
            },
            "status": IntegrationStatus.PROCESSED,
            "processed_at": timezone.now() - timedelta(minutes=5),
            "error_message": "",
        },
    )
    _upsert_user(
        username=f"e2e-{namespace.slug}-staff",
        email=_scenario_email("e2e-staff", namespace),
        is_staff=True,
    )
    del created_by


def _seed_planning_recipe(namespace: LocalExhaustiveSeedNamespace, *, solve: bool) -> None:
    seed_recipe_dataset(
        scenario_slug=f"{namespace.slug}-recipe",
        solve=solve,
    )


def _upsert_shipment(
    *,
    reference: str,
    namespace: LocalExhaustiveSeedNamespace,
    status: str,
    association_profile: AssociationProfile,
    recipient: AssociationRecipient,
    destination: Destination,
    created_by,
    closed_by=None,
    closed_delta_hours: int | None = None,
    is_disputed: bool = False,
) -> Shipment:
    recipient_contact = recipient.synced_contact
    correspondent = destination.correspondent_contact
    shipment, _ = Shipment.objects.update_or_create(
        reference=reference,
        defaults={
            "status": status,
            "shipper_name": association_profile.contact.name,
            "shipper_contact_ref": association_profile.contact,
            "shipper_contact": association_profile.contact.name,
            "recipient_name": recipient.get_display_name(),
            "recipient_contact_ref": recipient_contact,
            "recipient_contact": recipient.get_contact_display_name(),
            "correspondent_name": getattr(correspondent, "name", ""),
            "correspondent_contact_ref": correspondent,
            "destination": destination,
            "destination_address": recipient.address_line1,
            "destination_country": destination.country,
            "created_by": created_by,
            "is_disputed": is_disputed,
            "qr_code_image": f"qr_codes/shipments/{reference.lower()}.png",
            "party_snapshot": {
                "scenario": namespace.slug,
                "association": association_profile.contact.name,
                "recipient": recipient.get_display_name(),
            },
        },
    )
    update_fields = ["ready_at", "closed_at", "closed_by", "is_disputed", "status"]
    shipment.ready_at = timezone.now() - timedelta(days=1)
    shipment.closed_at = None
    shipment.closed_by = None
    if closed_delta_hours is not None and closed_by is not None:
        shipment.closed_at = timezone.now() - timedelta(hours=closed_delta_hours)
        shipment.closed_by = closed_by
    shipment.save(update_fields=update_fields)
    return shipment


def _upsert_order(
    namespace: LocalExhaustiveSeedNamespace,
    *,
    reference: str,
    association_profile: AssociationProfile,
    recipient: AssociationRecipient,
    created_by,
    status: str,
    review_status: str,
    public_link,
) -> Order:
    return Order.objects.update_or_create(
        reference=reference,
        defaults={
            "status": status,
            "review_status": review_status,
            "public_link": public_link,
            "association_contact": association_profile.contact,
            "shipper_name": association_profile.contact.name,
            "recipient_name": recipient.get_display_name(),
            "shipper_contact": association_profile.contact,
            "recipient_contact": recipient.synced_contact,
            "correspondent_contact": recipient.destination.correspondent_contact,
            "correspondent_name": recipient.destination.correspondent_contact.name,
            "destination_address": recipient.address_line1,
            "destination_city": recipient.city,
            "destination_country": recipient.country,
            "created_by": created_by,
            "notes": f"{namespace.label} order {reference}",
        },
    )[0]


def _seed_tracking_events(user, shipment: Shipment, specs: list[tuple[str, int]]) -> None:
    shipment.tracking_events.all().delete()
    for status, hours_ago in specs:
        event = ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=status,
            actor_name="Local Ops",
            actor_structure="ASF",
            comments=f"{status} for {shipment.reference}",
            created_by=user,
        )
        _set_timestamp(event, created_at=timezone.now() - timedelta(hours=hours_ago))


def _seed_carton(
    namespace: LocalExhaustiveSeedNamespace,
    *,
    code: str,
    lot: ProductLot,
    quantity: int,
    status: str,
    shipment: Shipment | None,
    destination: Destination,
    user,
) -> Carton:
    carton, _ = Carton.objects.update_or_create(
        code=f"{namespace.upper_slug}-{code.upper()}",
        defaults={
            "status": CartonStatus.DRAFT,
            "current_location": lot.location,
            "shipment": shipment,
            "preassigned_destination": destination,
            "prepared_by": user,
            "notes": f"{namespace.label} carton {code}",
        },
    )
    carton.shipment = shipment
    carton.current_location = lot.location
    carton.preassigned_destination = destination
    carton.prepared_by = user
    carton.save(
        update_fields=[
            "shipment",
            "current_location",
            "preassigned_destination",
            "prepared_by",
        ]
    )
    carton.status_events.all().delete()
    if carton.status != CartonStatus.DRAFT:
        carton.status = CartonStatus.DRAFT
        carton.save(update_fields=["status"])
    CartonItem.objects.update_or_create(
        carton=carton,
        product_lot=lot,
        defaults={"quantity": quantity},
    )

    transitions = {
        CartonStatus.DRAFT: [],
        CartonStatus.PICKING: [CartonStatus.PICKING],
        CartonStatus.PACKED: [CartonStatus.PICKING, CartonStatus.PACKED],
        CartonStatus.ASSIGNED: [
            CartonStatus.PICKING,
            CartonStatus.PACKED,
            CartonStatus.ASSIGNED,
        ],
        CartonStatus.LABELED: [
            CartonStatus.PICKING,
            CartonStatus.PACKED,
            CartonStatus.ASSIGNED,
            CartonStatus.LABELED,
        ],
        CartonStatus.SHIPPED: [
            CartonStatus.PICKING,
            CartonStatus.PACKED,
            CartonStatus.ASSIGNED,
            CartonStatus.LABELED,
            CartonStatus.SHIPPED,
        ],
    }
    for new_status in transitions.get(status, []):
        set_carton_status(
            carton=carton,
            new_status=new_status,
            user=user,
            reason=f"seed_local_exhaustive_{namespace.slug}",
        )
    return carton


def _seed_queue_backlog(namespace: LocalExhaustiveSeedNamespace) -> None:
    backlog_specs = [
        (
            "wms.email",
            "mailer",
            "send_email",
            IntegrationStatus.PENDING,
            "",
            None,
        ),
        (
            "wms.email",
            "mailer",
            "send_email",
            IntegrationStatus.PROCESSING,
            "",
            timezone.now() - timedelta(minutes=20),
        ),
        (
            "wms.email",
            "mailer",
            "send_email",
            IntegrationStatus.FAILED,
            "SMTP timeout",
            timezone.now() - timedelta(hours=2),
        ),
        (
            "wms.email",
            "mailer",
            "send_email",
            IntegrationStatus.PROCESSED,
            "",
            timezone.now() - timedelta(minutes=30),
        ),
        (
            DOCUMENT_SCAN_QUEUE_SOURCE,
            DOCUMENT_SCAN_QUEUE_TARGET,
            DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
            IntegrationStatus.PENDING,
            "",
            None,
        ),
        (
            DOCUMENT_SCAN_QUEUE_SOURCE,
            DOCUMENT_SCAN_QUEUE_TARGET,
            DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
            IntegrationStatus.PROCESSING,
            "",
            timezone.now() - timedelta(hours=20),
        ),
        (
            DOCUMENT_SCAN_QUEUE_SOURCE,
            DOCUMENT_SCAN_QUEUE_TARGET,
            DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
            IntegrationStatus.FAILED,
            "OCR parse error",
            timezone.now() - timedelta(hours=3),
        ),
        (
            DOCUMENT_SCAN_QUEUE_SOURCE,
            DOCUMENT_SCAN_QUEUE_TARGET,
            DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
            IntegrationStatus.PROCESSED,
            "",
            timezone.now() - timedelta(minutes=40),
        ),
    ]
    for index, (source, target, event_type, status, error_message, processed_at) in enumerate(
        backlog_specs,
        start=1,
    ):
        event, _ = IntegrationEvent.objects.update_or_create(
            source=source,
            target=target,
            event_type=event_type,
            external_id=f"{namespace.slug}-{source}-{index}",
            defaults={
                "direction": IntegrationDirection.OUTBOUND,
                "payload": {"scenario": namespace.slug, "index": index},
                "status": status,
                "error_message": error_message,
            },
        )
        IntegrationEvent.objects.filter(pk=event.pk).update(processed_at=processed_at)


def _set_timestamp(instance, **updates) -> None:
    instance.__class__.objects.filter(pk=instance.pk).update(**updates)
    instance.refresh_from_db()


def _upsert_account_document(
    *,
    association_contact,
    account_request,
    doc_type: str,
    status: str,
    uploaded_by,
    filename: str,
    content: bytes,
    scan_status: str = DocumentScanStatus.CLEAN,
) -> AccountDocument:
    document = (
        AccountDocument.objects.filter(
            association_contact=association_contact,
            account_request=account_request,
            doc_type=doc_type,
        )
        .order_by("id")
        .first()
    )
    if document is None:
        document = AccountDocument(
            association_contact=association_contact,
            account_request=account_request,
            doc_type=doc_type,
        )
    document.status = status
    document.scan_status = scan_status
    document.scan_message = f"{scan_status} seeded for {filename}"
    document.scan_updated_at = timezone.now()
    document.uploaded_by = uploaded_by
    document.file.save(filename, ContentFile(content), save=False)
    document.save()
    return document


def _upsert_order_document(
    *,
    order: Order,
    doc_type: str,
    status: str,
    uploaded_by,
    filename: str,
    content: bytes,
    scan_status: str = DocumentScanStatus.CLEAN,
) -> OrderDocument:
    document = OrderDocument.objects.filter(order=order, doc_type=doc_type).order_by("id").first()
    if document is None:
        document = OrderDocument(order=order, doc_type=doc_type)
    document.status = status
    document.scan_status = scan_status
    document.scan_message = f"{scan_status} seeded for {filename}"
    document.scan_updated_at = timezone.now()
    document.uploaded_by = uploaded_by
    document.file.save(filename, ContentFile(content), save=False)
    document.save()
    return document
