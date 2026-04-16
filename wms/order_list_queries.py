from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Coalesce, Lower
from django.urls import reverse

from .models import Order, OrderReviewStatus
from .order_view_helpers import build_orders_view_rows
from .scan_list_urls import build_scan_list_url

ORDERS_PAGE_SIZE = 100
DEFAULT_ORDERS_SORT = "created_desc"

ORDER_SORT_CHOICES = [
    ("created_desc", "Plus recentes"),
    ("created_asc", "Plus anciennes"),
    ("contact_asc", "Contact A -> Z"),
    ("contact_desc", "Contact Z -> A"),
]

ORDER_SORT_MAP = {
    "created_desc": ("-created_at", "-id"),
    "created_asc": ("created_at", "id"),
    "contact_asc": ("contact_sort_name", "created_at", "id"),
    "contact_desc": ("-contact_sort_name", "-created_at", "-id"),
}


def build_orders_queryset():
    return (
        Order.objects.select_related(
            "association_contact",
            "recipient_contact",
            "created_by",
            "shipment",
            "inbound_delivery__receipt",
        )
        .prefetch_related(
            "documents",
            "shipment_links__shipment",
            "inbound_delivery__receipt__shipper_cartons",
        )
        .annotate(
            contact_sort_name=Lower(
                Coalesce(
                    "association_contact__name",
                    "recipient_contact__name",
                    "recipient_name",
                    "reference",
                    Value(""),
                )
            )
        )
    )


def _resolve_orders_sort(raw_sort_value):
    sort_value = (raw_sort_value or DEFAULT_ORDERS_SORT).strip()
    if sort_value in ORDER_SORT_MAP:
        return sort_value
    return DEFAULT_ORDERS_SORT


def _apply_orders_sort(orders_qs, sort_value):
    return orders_qs.order_by(*ORDER_SORT_MAP[sort_value])


def _apply_orders_search(orders_qs, query):
    if not query:
        return orders_qs
    return orders_qs.filter(
        Q(reference__icontains=query)
        | Q(association_contact__name__icontains=query)
        | Q(recipient_contact__name__icontains=query)
        | Q(recipient_name__icontains=query)
        | Q(shipper_name__icontains=query)
        | Q(created_by__username__icontains=query)
        | Q(created_by__first_name__icontains=query)
        | Q(created_by__last_name__icontains=query)
        | Q(created_by__email__icontains=query)
    )


def _build_orders_summary_cards(orders_qs):
    return [
        {
            "id": "to-validate",
            "label": "À valider",
            "value": orders_qs.filter(review_status=OrderReviewStatus.PENDING).count(),
            "help": "Commandes en attente de revue",
            "tone": "warn",
        },
        {
            "id": "changes-requested",
            "label": "Modifications demandées",
            "value": orders_qs.filter(review_status=OrderReviewStatus.CHANGES_REQUESTED).count(),
            "help": "Relance opérateur",
            "tone": "warn",
        },
        {
            "id": "approved-without-shipment",
            "label": "Validées",
            "value": orders_qs.filter(review_status=OrderReviewStatus.APPROVED).count(),
            "help": "Commandes pouvant créer un dossier",
            "tone": "success",
        },
        {
            "id": "rejected-orders",
            "label": "Refusées",
            "value": orders_qs.filter(review_status=OrderReviewStatus.REJECTED).count(),
            "help": "Décisions à expliciter si besoin",
            "tone": "danger",
        },
    ]


def build_orders_list_context(request):
    base_url = reverse("scan:scan_orders_view")
    query = (request.GET.get("q") or "").strip()
    sort_value = _resolve_orders_sort(request.GET.get("sort"))
    page_number = (request.GET.get("page") or "1").strip()

    orders_qs = _apply_orders_search(build_orders_queryset(), query)
    summary_cards = _build_orders_summary_cards(orders_qs)
    orders_qs = _apply_orders_sort(orders_qs, sort_value)

    paginator = Paginator(orders_qs, ORDERS_PAGE_SIZE)
    orders_page = paginator.get_page(page_number)

    page_prev_url = None
    if orders_page.has_previous():
        page_prev_url = build_scan_list_url(
            base_url,
            request.GET,
            page=orders_page.previous_page_number(),
        )

    page_next_url = None
    if orders_page.has_next():
        page_next_url = build_scan_list_url(
            base_url,
            request.GET,
            page=orders_page.next_page_number(),
        )

    return {
        "query": query,
        "sort_value": sort_value,
        "sort_choices": ORDER_SORT_CHOICES,
        "summary_cards": summary_cards,
        "total_count": paginator.count,
        "page_size": ORDERS_PAGE_SIZE,
        "page_obj": orders_page,
        "orders_page": orders_page,
        "orders": build_orders_view_rows(orders_page.object_list),
        "page_prev_url": page_prev_url,
        "page_next_url": page_next_url,
        "reset_url": build_scan_list_url(
            base_url,
            request.GET,
            reset_keys={"page", "q", "sort"},
        ),
    }
