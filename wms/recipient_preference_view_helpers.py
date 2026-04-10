from urllib.parse import urlencode

from django.utils.translation import gettext_lazy as _

from .models import (
    Product,
    RecipientProductPreference,
    RecipientProductPreferencePeriodUnit,
    RecipientProductPreferenceStatus,
)
from .order_helpers import estimate_units_per_carton
from .portal_helpers import get_default_carton_format
from .product_category_filters import build_category_filter_context
from .recipient_product_preferences import (
    UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS,
    list_effective_recipient_product_preferences,
    list_recipient_product_coverages,
)
from .view_utils import sorted_choices

PREFERENCE_QUERY_PARAM = "preference_q"
PREFERENCE_CATEGORY_PARAM = "preference_category"
PREFERENCE_SORT_PARAM = "preference_sort"

PREFERENCE_SORT_NAME = "name"
PREFERENCE_SORT_BRAND = "brand"
PREFERENCE_SORT_UNITS = "units_per_carton_estimate"
PREFERENCE_SORT_CHOICES = sorted_choices(
    (
        (PREFERENCE_SORT_BRAND, _("Marque")),
        (PREFERENCE_SORT_NAME, _("Nom du produit")),
        (PREFERENCE_SORT_UNITS, _("Qté estimée par colis")),
    )
)
DEFAULT_PREFERENCE_SORT = PREFERENCE_SORT_NAME
ALLOWED_PREFERENCE_SORTS = {choice[0] for choice in PREFERENCE_SORT_CHOICES}


def get_recipient_preference_filter_state(request):
    query = (
        request.GET.get(PREFERENCE_QUERY_PARAM) or request.POST.get(PREFERENCE_QUERY_PARAM) or ""
    ).strip()
    category_id = (
        request.GET.get(PREFERENCE_CATEGORY_PARAM)
        or request.POST.get(PREFERENCE_CATEGORY_PARAM)
        or ""
    ).strip()
    raw_sort = (
        request.GET.get(PREFERENCE_SORT_PARAM)
        or request.POST.get(PREFERENCE_SORT_PARAM)
        or DEFAULT_PREFERENCE_SORT
    ).strip()
    sort = raw_sort if raw_sort in ALLOWED_PREFERENCE_SORTS else DEFAULT_PREFERENCE_SORT
    return {
        "query": query,
        "category_id": category_id,
        "sort": sort,
    }


def build_recipient_preference_filter_url(base_url, *, query="", category_id="", sort=""):
    params = {}
    if query:
        params[PREFERENCE_QUERY_PARAM] = query
    if category_id:
        params[PREFERENCE_CATEGORY_PARAM] = category_id
    if sort and sort != DEFAULT_PREFERENCE_SORT:
        params[PREFERENCE_SORT_PARAM] = sort
    if not params:
        return base_url
    return f"{base_url}?{urlencode(params)}"


def build_recipient_preference_catalog_context(
    *,
    recipient_organization,
    filter_state,
    build_form_data,
    preference_form_data_by_product_id=None,
):
    query = (filter_state or {}).get("query", "")
    category_id = (filter_state or {}).get("category_id", "")
    sort = (filter_state or {}).get("sort", DEFAULT_PREFERENCE_SORT)
    category_filter_context = build_category_filter_context(selected_category_id=category_id)

    products = list(
        Product.objects.filter(is_active=True).select_related("category").order_by("name", "id")
    )
    if query:
        query_key = query.casefold()
        products = [
            product for product in products if query_key in str(product.name or "").casefold()
        ]
    if category_filter_context["descendant_category_ids"]:
        descendant_ids = set(category_filter_context["descendant_category_ids"])
        products = [
            product
            for product in products
            if getattr(product, "category_id", None) in descendant_ids
        ]

    recipient_preferences = list(
        RecipientProductPreference.objects.filter(recipient_organization=recipient_organization)
        .select_related("product")
        .order_by("product__name", "id")
    )
    effective_preferences = list_effective_recipient_product_preferences(
        recipient_organization=recipient_organization,
        products=products,
    )
    quantitative_products = [
        effective_preference.product
        for effective_preference in effective_preferences
        if effective_preference.status
        in {
            RecipientProductPreferenceStatus.REQUESTED,
            RecipientProductPreferenceStatus.ALLOWED,
        }
    ]
    coverages_by_product_id = {
        coverage.product.pk: coverage
        for coverage in list_recipient_product_coverages(
            recipient_organization=recipient_organization,
            products=quantitative_products,
        )
    }
    carton_format = get_default_carton_format()
    rows = [
        {
            "product": effective_preference.product,
            "preference": effective_preference.preference,
            "status": effective_preference.status,
            "is_explicit": effective_preference.is_explicit,
            "form_data": (preference_form_data_by_product_id or {}).get(
                effective_preference.product.pk,
                build_form_data(effective_preference),
            ),
            "coverage": coverages_by_product_id.get(effective_preference.product.pk),
            "units_per_carton_estimate": estimate_units_per_carton(
                product=effective_preference.product,
                carton_format=carton_format,
            ),
        }
        for effective_preference in effective_preferences
    ]
    rows = _sort_recipient_preference_rows(rows, sort=sort)
    return {
        "recipient_preferences": recipient_preferences,
        "recipient_product_rows": rows,
        "recipient_preference_coverage_rows": [
            {
                "preference": preference,
                "coverage": coverages_by_product_id.get(preference.product_id),
            }
            for preference in recipient_preferences
            if coverages_by_product_id.get(preference.product_id) is not None
        ],
        "preference_products": products,
        "preference_query": query,
        "preference_category_id": category_id,
        "preference_sort": sort,
        "preference_sort_choices": PREFERENCE_SORT_CHOICES,
        "preference_status_choices": sorted_choices(
            [
                (UNSPECIFIED_RECIPIENT_PRODUCT_PREFERENCE_STATUS, _("Non précisé")),
                *list(RecipientProductPreferenceStatus.choices),
            ]
        ),
        "preference_period_choices": sorted_choices(RecipientProductPreferencePeriodUnit.choices),
        **category_filter_context,
    }


def _sort_recipient_preference_rows(rows, *, sort):
    normalized_sort = sort if sort in ALLOWED_PREFERENCE_SORTS else DEFAULT_PREFERENCE_SORT

    def _name_key(row):
        product = row["product"]
        return (
            str(product.name or "").casefold(),
            str(product.brand or "").casefold(),
            product.id,
        )

    def _brand_key(row):
        product = row["product"]
        return (
            str(product.brand or "").casefold(),
            str(product.name or "").casefold(),
            product.id,
        )

    def _units_key(row):
        product = row["product"]
        estimate = row.get("units_per_carton_estimate")
        return (
            estimate is None,
            estimate if estimate is not None else 0,
            str(product.name or "").casefold(),
            product.id,
        )

    key_map = {
        PREFERENCE_SORT_NAME: _name_key,
        PREFERENCE_SORT_BRAND: _brand_key,
        PREFERENCE_SORT_UNITS: _units_key,
    }
    return sorted(rows, key=key_map[normalized_sort])
