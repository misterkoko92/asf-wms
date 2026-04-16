from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse

from .models import Receipt, ReceiptType
from .receipt_view_helpers import build_receipts_view_rows
from .scan_list_urls import build_scan_list_url

RECEIPTS_PAGE_SIZE = 100
DEFAULT_RECEIPTS_SORT = "received_on_desc"

RECEIPT_FILTER_MAP = {
    "pallet": ReceiptType.PALLET,
    "association": ReceiptType.ASSOCIATION,
}

RECEIPT_SORT_CHOICES = [
    ("received_on_desc", "Date decroissante"),
    ("received_on_asc", "Date croissante"),
    ("name_asc", "Nom A -> Z"),
    ("name_desc", "Nom Z -> A"),
]

RECEIPT_SORT_MAP = {
    "received_on_desc": ("-received_on", "-created_at", "-id"),
    "received_on_asc": ("received_on", "created_at", "id"),
    "name_asc": ("source_contact__name", "reference", "id"),
    "name_desc": ("-source_contact__name", "-reference", "-id"),
}


def _resolve_receipts_filter(raw_filter_value):
    filter_value = (raw_filter_value or "all").strip().lower()
    if filter_value in RECEIPT_FILTER_MAP:
        return filter_value
    return "all"


def _resolve_receipts_sort(raw_sort_value):
    sort_value = (raw_sort_value or DEFAULT_RECEIPTS_SORT).strip()
    if sort_value in RECEIPT_SORT_MAP:
        return sort_value
    return DEFAULT_RECEIPTS_SORT


def _build_receipts_queryset(filter_value):
    receipts_qs = Receipt.objects.select_related(
        "source_contact",
        "carrier_contact",
    ).prefetch_related("hors_format_items")
    receipt_type = RECEIPT_FILTER_MAP.get(filter_value)
    if receipt_type:
        receipts_qs = receipts_qs.filter(receipt_type=receipt_type)
    return receipts_qs


def _apply_receipts_sort(receipts_qs, sort_value):
    return receipts_qs.order_by(*RECEIPT_SORT_MAP[sort_value])


def build_receipts_list_context(request):
    base_url = reverse("scan:scan_receipts_view")
    filter_value = _resolve_receipts_filter(request.GET.get("type"))
    query = (request.GET.get("q") or "").strip()
    sort_value = _resolve_receipts_sort(request.GET.get("sort"))
    page_number = (request.GET.get("page") or "1").strip()

    receipts_qs = _build_receipts_queryset(filter_value)
    if query:
        receipts_qs = receipts_qs.filter(
            Q(reference__icontains=query)
            | Q(source_contact__name__icontains=query)
            | Q(carrier_contact__name__icontains=query)
        )
    receipts_qs = _apply_receipts_sort(receipts_qs, sort_value)

    paginator = Paginator(receipts_qs, RECEIPTS_PAGE_SIZE)
    receipts_page = paginator.get_page(page_number)

    page_prev_url = None
    if receipts_page.has_previous():
        page_prev_url = build_scan_list_url(
            base_url,
            request.GET,
            page=receipts_page.previous_page_number(),
        )

    page_next_url = None
    if receipts_page.has_next():
        page_next_url = build_scan_list_url(
            base_url,
            request.GET,
            page=receipts_page.next_page_number(),
        )

    return {
        "filter_value": filter_value,
        "query": query,
        "sort_value": sort_value,
        "sort_choices": RECEIPT_SORT_CHOICES,
        "total_count": paginator.count,
        "page_size": RECEIPTS_PAGE_SIZE,
        "page_obj": receipts_page,
        "receipts_page": receipts_page,
        "receipts": build_receipts_view_rows(receipts_page.object_list),
        "page_prev_url": page_prev_url,
        "page_next_url": page_next_url,
        "reset_url": build_scan_list_url(
            base_url,
            request.GET,
            reset_keys={"page", "q", "sort", "type"},
        ),
    }
