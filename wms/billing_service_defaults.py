from .models import BillingServiceCatalogItem


def get_default_pickup_charge_service():
    return (
        BillingServiceCatalogItem.objects.filter(
            use_for_default_pickup_charge=True,
            is_active=True,
        )
        .order_by("display_order", "id")
        .first()
    )
