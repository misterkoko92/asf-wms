from __future__ import annotations

from dataclasses import dataclass

from .models import RecipientProductPreference, RecipientProductPreferenceStatus

UNSPECIFIED_RECIPIENT_PREFERENCE_STATUS = "unspecified"


@dataclass(frozen=True)
class EffectiveRecipientProductPreference:
    status: str
    quantity_target: int | None
    period_unit: str | None
    scope: str
    matched_preference_id: int | None = None


def _category_lineage(category):
    lineage = []
    current = category
    while current is not None:
        lineage.append(current)
        current = current.parent
    return lineage


def resolve_effective_recipient_product_preference(*, recipient_organization, product):
    product_preference = RecipientProductPreference.objects.filter(
        recipient_organization=recipient_organization,
        product=product,
    ).first()
    if product_preference is not None:
        return EffectiveRecipientProductPreference(
            status=product_preference.status,
            quantity_target=product_preference.quantity_target,
            period_unit=product_preference.period_unit or None,
            scope="product",
            matched_preference_id=product_preference.id,
        )

    category = getattr(product, "category", None)
    if category is not None:
        lineage = _category_lineage(category)
        preferences_by_category_id = {
            preference.category_id: preference
            for preference in RecipientProductPreference.objects.filter(
                recipient_organization=recipient_organization,
                category__in=lineage,
            ).select_related("category")
        }
        for current in lineage:
            category_preference = preferences_by_category_id.get(current.id)
            if category_preference is not None:
                return EffectiveRecipientProductPreference(
                    status=category_preference.status,
                    quantity_target=category_preference.quantity_target,
                    period_unit=category_preference.period_unit or None,
                    scope="category",
                    matched_preference_id=category_preference.id,
                )

    return EffectiveRecipientProductPreference(
        status=UNSPECIFIED_RECIPIENT_PREFERENCE_STATUS,
        quantity_target=None,
        period_unit=None,
        scope="unspecified",
        matched_preference_id=None,
    )


def list_effective_recipient_product_preferences(*, recipient_organization, products):
    return [
        resolve_effective_recipient_product_preference(
            recipient_organization=recipient_organization,
            product=product,
        )
        for product in products
    ]
