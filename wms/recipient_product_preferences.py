from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.utils import timezone

from .models import (
    CartonItem,
    RecipientProductPreference,
    RecipientProductPreferenceStatus,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
)

UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS = "unspecified"
UNSPECIFIED_RECIPIENT_PREFERENCE_STATUS = UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS


@dataclass(frozen=True, slots=True)
class EffectiveRecipientProductPreference:
    recipient_organization: ShipmentRecipientOrganization
    product: object
    status: str
    quantity_target: int | None
    period_unit: str | None
    preference: RecipientProductPreference | None = None

    @property
    def is_explicit(self) -> bool:
        return self.preference is not None

    @property
    def scope(self) -> str:
        if self.preference is None:
            return "unspecified"
        if getattr(self.preference, "category_id", None):
            return "category"
        return "product"

    @property
    def matched_preference_id(self) -> int | None:
        return getattr(self.preference, "id", None)


@dataclass(frozen=True, slots=True)
class CartonProductQuantity:
    product: object
    quantity: int


@dataclass(frozen=True, slots=True)
class RecipientProductRefusalConflict:
    recipient_organization: ShipmentRecipientOrganization
    product: object
    quantity: int | None
    preference: RecipientProductPreference


@dataclass(frozen=True, slots=True)
class RecipientProductCoverage:
    recipient_organization: ShipmentRecipientOrganization
    product: object
    status: str
    target_quantity: int | None
    period_unit: str | None
    period_start: object | None
    period_end: object | None
    delivered_quantity: int | None
    pipeline_quantity: int | None
    remaining_need: int | None
    preference: RecipientProductPreference | None = None


@dataclass(frozen=True, slots=True)
class RecipientCartonCompatibility:
    recipient_organization: ShipmentRecipientOrganization
    carton: object
    bucket: str
    score: int
    explanation: str


def _normalize_as_of(as_of=None):
    if as_of is None:
        return timezone.now()
    if timezone.is_naive(as_of):
        return timezone.make_aware(as_of, timezone.get_current_timezone())
    return as_of


def _resolve_period_window(*, as_of, period_unit):
    local_as_of = timezone.localtime(
        _normalize_as_of(as_of),
        timezone.get_current_timezone(),
    )
    period_start = local_as_of.replace(hour=0, minute=0, second=0, microsecond=0)
    if period_unit == "week":
        period_start = period_start - timedelta(days=period_start.weekday())
        return period_start, period_start + timedelta(days=7)
    if period_unit == "month":
        period_start = period_start.replace(day=1)
        if period_start.month == 12:
            return period_start, period_start.replace(
                year=period_start.year + 1,
                month=1,
            )
        return period_start, period_start.replace(month=period_start.month + 1)
    return None, None


def _category_lineage(category):
    lineage = []
    current = category
    while current is not None:
        lineage.append(current)
        current = current.parent
    return lineage


def _recipient_contact_ids(*, recipient_organization):
    contact_ids = set(
        ShipmentRecipientContact.objects.filter(
            recipient_organization=recipient_organization,
            is_active=True,
        ).values_list("contact_id", flat=True)
    )
    if recipient_organization.organization_id:
        contact_ids.add(recipient_organization.organization_id)
    return contact_ids


def _iter_recipient_shipment_product_rows(*, recipient_organization, product):
    contact_ids = _recipient_contact_ids(recipient_organization=recipient_organization)
    if not contact_ids:
        return []
    carton_items = (
        CartonItem.objects.filter(
            product_lot__product=product,
            carton__shipment__isnull=False,
            carton__shipment__destination=recipient_organization.destination,
            carton__shipment__recipient_contact_ref_id__in=contact_ids,
        )
        .select_related("carton__shipment")
        .order_by("carton__shipment_id", "pk")
    )
    for item in carton_items:
        shipment = item.carton.shipment
        try:
            projection = shipment.workflow_projection
        except ObjectDoesNotExist:
            projection = None
        yield int(item.quantity or 0), shipment, projection


def _effective_preference_from_row(
    *,
    recipient_organization: ShipmentRecipientOrganization,
    product,
    preference: RecipientProductPreference | None,
) -> EffectiveRecipientProductPreference:
    if preference is None:
        return EffectiveRecipientProductPreference(
            recipient_organization=recipient_organization,
            product=product,
            status=UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS,
            quantity_target=None,
            period_unit=None,
            preference=None,
        )

    quantity_target = preference.quantity_target
    period_unit = preference.period_unit
    if preference.status == RecipientProductPreferenceStatus.REFUSED:
        quantity_target = None
        period_unit = None

    return EffectiveRecipientProductPreference(
        recipient_organization=recipient_organization,
        product=product,
        status=preference.status,
        quantity_target=quantity_target,
        period_unit=period_unit,
        preference=preference,
    )


def _resolve_preference_for_product(
    *,
    recipient_organization,
    product,
    preferences_by_product_id: dict[int, RecipientProductPreference],
    preferences_by_category_id: dict[int, RecipientProductPreference],
):
    product_preference = preferences_by_product_id.get(product.pk)
    if product_preference is not None:
        return product_preference

    category = getattr(product, "category", None)
    if category is None:
        return None

    for current in _category_lineage(category):
        category_preference = preferences_by_category_id.get(current.id)
        if category_preference is not None:
            return category_preference
    return None


def _collect_preference_maps(*, recipient_organization, product_list):
    product_ids = [
        product.pk for product in product_list if getattr(product, "pk", None) is not None
    ]
    category_ids = {
        category.id
        for product in product_list
        for category in _category_lineage(getattr(product, "category", None))
    }
    if not product_ids and not category_ids:
        return {}, {}

    preferences = (
        RecipientProductPreference.objects.filter(
            recipient_organization=recipient_organization,
        )
        .filter(Q(product_id__in=product_ids) | Q(category_id__in=category_ids))
        .select_related("product", "category")
    )

    preferences_by_product_id = {}
    preferences_by_category_id = {}
    for preference in preferences:
        if preference.product_id:
            preferences_by_product_id[preference.product_id] = preference
        if getattr(preference, "category_id", None):
            preferences_by_category_id[preference.category_id] = preference
    return preferences_by_product_id, preferences_by_category_id


def recipient_has_explicit_refused_preferences(*, recipient_organization) -> bool:
    return RecipientProductPreference.objects.filter(
        recipient_organization=recipient_organization,
        status=RecipientProductPreferenceStatus.REFUSED,
    ).exists()


def resolve_effective_recipient_product_preference(*, recipient_organization, product):
    preferences_by_product_id, preferences_by_category_id = _collect_preference_maps(
        recipient_organization=recipient_organization,
        product_list=[product],
    )
    preference = _resolve_preference_for_product(
        recipient_organization=recipient_organization,
        product=product,
        preferences_by_product_id=preferences_by_product_id,
        preferences_by_category_id=preferences_by_category_id,
    )
    return _effective_preference_from_row(
        recipient_organization=recipient_organization,
        product=product,
        preference=preference,
    )


def list_effective_recipient_product_preferences(
    *,
    recipient_organization,
    products: Iterable,
) -> list[EffectiveRecipientProductPreference]:
    product_list = list(products)
    if not product_list:
        return []

    preferences_by_product_id, preferences_by_category_id = _collect_preference_maps(
        recipient_organization=recipient_organization,
        product_list=product_list,
    )
    return [
        _effective_preference_from_row(
            recipient_organization=recipient_organization,
            product=product,
            preference=_resolve_preference_for_product(
                recipient_organization=recipient_organization,
                product=product,
                preferences_by_product_id=preferences_by_product_id,
                preferences_by_category_id=preferences_by_category_id,
            ),
        )
        for product in product_list
    ]


def list_carton_product_quantities(*, carton) -> list[CartonProductQuantity]:
    product_quantities: OrderedDict[int, CartonProductQuantity] = OrderedDict()
    carton_items = getattr(carton, "cartonitem_set", None)
    if carton_items is None or not hasattr(carton_items, "all"):
        return []
    for item in carton_items.all():
        product = item.product_lot.product
        if product.pk in product_quantities:
            existing = product_quantities[product.pk]
            product_quantities[product.pk] = CartonProductQuantity(
                product=product,
                quantity=existing.quantity + int(item.quantity or 0),
            )
            continue
        product_quantities[product.pk] = CartonProductQuantity(
            product=product,
            quantity=int(item.quantity or 0),
        )
    return list(product_quantities.values())


def list_recipient_refusal_conflicts_for_products(
    *,
    recipient_organization,
    products: Iterable,
) -> list[RecipientProductRefusalConflict]:
    product_list = list(products)
    if not product_list:
        return []

    effective_preferences = list_effective_recipient_product_preferences(
        recipient_organization=recipient_organization,
        products=product_list,
    )
    return [
        RecipientProductRefusalConflict(
            recipient_organization=recipient_organization,
            product=effective_preference.product,
            quantity=None,
            preference=effective_preference.preference,
        )
        for effective_preference in effective_preferences
        if effective_preference.status == RecipientProductPreferenceStatus.REFUSED
        and effective_preference.preference is not None
    ]


def list_recipient_refusal_conflicts_for_carton(
    *,
    recipient_organization,
    carton,
) -> list[RecipientProductRefusalConflict]:
    carton_product_quantities = list_carton_product_quantities(carton=carton)
    if not carton_product_quantities:
        return []

    effective_preferences = list_effective_recipient_product_preferences(
        recipient_organization=recipient_organization,
        products=[row.product for row in carton_product_quantities],
    )
    quantities_by_product_id = {row.product.pk: row.quantity for row in carton_product_quantities}
    return [
        RecipientProductRefusalConflict(
            recipient_organization=recipient_organization,
            product=effective_preference.product,
            quantity=quantities_by_product_id.get(effective_preference.product.pk),
            preference=effective_preference.preference,
        )
        for effective_preference in effective_preferences
        if effective_preference.status == RecipientProductPreferenceStatus.REFUSED
        and effective_preference.preference is not None
    ]


def resolve_recipient_product_coverage(
    *,
    recipient_organization,
    product,
    as_of=None,
):
    effective_preference = resolve_effective_recipient_product_preference(
        recipient_organization=recipient_organization,
        product=product,
    )
    if effective_preference.status not in {
        RecipientProductPreferenceStatus.REQUESTED,
        RecipientProductPreferenceStatus.ALLOWED,
    }:
        return RecipientProductCoverage(
            recipient_organization=recipient_organization,
            product=product,
            status=effective_preference.status,
            target_quantity=None,
            period_unit=None,
            period_start=None,
            period_end=None,
            delivered_quantity=None,
            pipeline_quantity=None,
            remaining_need=None,
            preference=effective_preference.preference,
        )

    period_start, period_end = _resolve_period_window(
        as_of=as_of,
        period_unit=effective_preference.period_unit,
    )
    delivered_quantity = 0
    pipeline_quantity = 0
    for quantity, shipment, projection in _iter_recipient_shipment_product_rows(
        recipient_organization=recipient_organization,
        product=product,
    ):
        delivered_at = getattr(projection, "delivered_at", None)
        if delivered_at and period_start <= delivered_at < period_end:
            delivered_quantity += quantity
            continue
        if delivered_at is None and not shipment.closed_at:
            pipeline_quantity += quantity

    remaining_need = max(
        int(effective_preference.quantity_target or 0) - delivered_quantity - pipeline_quantity,
        0,
    )
    return RecipientProductCoverage(
        recipient_organization=recipient_organization,
        product=product,
        status=effective_preference.status,
        target_quantity=effective_preference.quantity_target,
        period_unit=effective_preference.period_unit,
        period_start=period_start,
        period_end=period_end,
        delivered_quantity=delivered_quantity,
        pipeline_quantity=pipeline_quantity,
        remaining_need=remaining_need,
        preference=effective_preference.preference,
    )


def list_recipient_product_coverages(
    *,
    recipient_organization,
    products: Iterable,
    as_of=None,
) -> list[RecipientProductCoverage]:
    return [
        resolve_recipient_product_coverage(
            recipient_organization=recipient_organization,
            product=product,
            as_of=as_of,
        )
        for product in list(products)
    ]


def score_recipient_carton_compatibility(
    *,
    recipient_organization,
    carton,
    as_of=None,
):
    refusal_conflicts = list_recipient_refusal_conflicts_for_carton(
        recipient_organization=recipient_organization,
        carton=carton,
    )
    if refusal_conflicts:
        refused_labels = ", ".join(
            getattr(conflict.product, "name", str(conflict.product))
            for conflict in refusal_conflicts
        )
        return RecipientCartonCompatibility(
            recipient_organization=recipient_organization,
            carton=carton,
            bucket="incompatibles",
            score=-1000,
            explanation=f"Contient un produit refuse: {refused_labels}",
        )

    carton_product_quantities = list_carton_product_quantities(carton=carton)
    coverages = list_recipient_product_coverages(
        recipient_organization=recipient_organization,
        products=[row.product for row in carton_product_quantities],
        as_of=as_of,
    )
    coverage_by_product_id = {coverage.product.pk: coverage for coverage in coverages}

    requested_useful = 0
    allowed_useful = 0
    requested_excess = 0
    allowed_excess = 0
    unspecified_units = 0
    for product_row in carton_product_quantities:
        coverage = coverage_by_product_id.get(product_row.product.pk)
        if coverage is None:
            unspecified_units += product_row.quantity
            continue
        if coverage.status == RecipientProductPreferenceStatus.REQUESTED:
            if coverage.remaining_need:
                requested_useful += min(product_row.quantity, coverage.remaining_need)
            else:
                requested_excess += product_row.quantity
            continue
        if coverage.status == RecipientProductPreferenceStatus.ALLOWED:
            if coverage.remaining_need:
                allowed_useful += min(product_row.quantity, coverage.remaining_need)
            else:
                allowed_excess += product_row.quantity
            continue
        if coverage.status == UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS:
            unspecified_units += product_row.quantity

    score = (
        requested_useful * 100
        + allowed_useful * 30
        + unspecified_units
        - requested_excess * 20
        - allowed_excess * 5
    )
    if requested_useful > 0:
        bucket = "tres_adaptes"
        explanation = "Couvre un besoin demande actif"
    elif allowed_useful > 0:
        bucket = "compatibles"
        explanation = "Couvre un besoin autorise actif"
    elif requested_excess > 0 or allowed_excess > 0:
        bucket = "a_eviter"
        explanation = "Produits explicites sans besoin actif"
    else:
        bucket = "compatibles"
        explanation = "Aucun refus explicite, sans besoin exprime"

    return RecipientCartonCompatibility(
        recipient_organization=recipient_organization,
        carton=carton,
        bucket=bucket,
        score=score,
        explanation=explanation,
    )
