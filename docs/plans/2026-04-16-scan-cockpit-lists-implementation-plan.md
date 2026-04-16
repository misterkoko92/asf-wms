# Scan Cockpit Lists Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Standardize the main legacy Django `scan/` cockpit lists around server-side filters, sorting, pagination, short date formatting, and explicit `list -> cockpit` navigation without creating new helper monoliths.

**Architecture:** Keep shared behavior limited to small mechanism helpers: date formatting tags, querystring/pagination URL helpers, and a shared pagination partial. Keep queryset composition, row presentation, and mutation logic local to each domain (`receipts`, `orders`, `shipments`). Introduce a receipt cockpit, align the orders list with the same rules, and retrofit shipments tracking to use the shared paging/date conventions while keeping shipment-specific actions local.

**Tech Stack:** Django templates, Django views, Django paginator, existing `scan/` Bootstrap layer, repository view tests, template-tag tests.

---

### Task 1: Add Shared Short Date Helpers For Scan Lists

**Files:**
- Create: `wms/templatetags/wms_dates.py`
- Test: `wms/tests/templatetags/tests_wms_dates.py`
- Modify later callers in:
  - `templates/scan/receipts_view.html`
  - `templates/scan/orders_view.html`
  - `templates/scan/shipments_tracking.html`

**Step 1: Write the failing test**

```python
from datetime import date, datetime

from django.template import Context, Template
from django.test import SimpleTestCase


class WmsDatesTemplateTagsTests(SimpleTestCase):
    def test_scan_date_short_formats_date(self):
        html = Template(
            "{% load wms_dates %}{{ value|scan_date_short }}"
        ).render(Context({"value": date(2026, 4, 16)}))
        self.assertEqual(html, "16/04/26")

    def test_scan_datetime_short_formats_datetime(self):
        html = Template(
            "{% load wms_dates %}{{ value|scan_datetime_short }}"
        ).render(Context({"value": datetime(2026, 4, 16, 14, 5)}))
        self.assertEqual(html, "16/04/26 14h05")

    def test_scan_date_weekday_short_formats_weekday_prefix(self):
        html = Template(
            "{% load wms_dates %}{{ value|scan_date_weekday_short }}"
        ).render(Context({"value": date(2026, 4, 16)}))
        self.assertEqual(html, "Jeu 16/04/26")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.templatetags.tests_wms_dates -v 2`

Expected: FAIL because `wms_dates` does not exist yet.

**Step 3: Write minimal implementation**

```python
from django import template
from django.utils import timezone

register = template.Library()

WEEKDAY_LABELS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


def _normalize_value(value):
    if value is None:
        return None
    if hasattr(value, "hour"):
        return timezone.localtime(value) if timezone.is_aware(value) else value
    return value


@register.filter
def scan_date_short(value):
    value = _normalize_value(value)
    return value.strftime("%d/%m/%y") if value else "-"


@register.filter
def scan_datetime_short(value):
    value = _normalize_value(value)
    return value.strftime("%d/%m/%y %Hh%M") if value else "-"


@register.filter
def scan_date_weekday_short(value):
    value = _normalize_value(value)
    if not value:
        return "-"
    return f"{WEEKDAY_LABELS[value.weekday()]} {value.strftime('%d/%m/%y')}"
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.templatetags.tests_wms_dates -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/templatetags/wms_dates.py wms/tests/templatetags/tests_wms_dates.py
git commit -m "feat: add scan list date formatting tags"
```

### Task 2: Add Shared Querystring And Pagination Building Blocks

**Files:**
- Create: `wms/scan_list_urls.py`
- Create: `templates/scan/includes/scan_list_pagination.html`
- Test: `wms/tests/views/tests_scan_list_urls.py`

**Step 1: Write the failing test**

```python
from django.http import QueryDict
from django.test import SimpleTestCase

from wms.scan_list_urls import build_scan_list_url


class ScanListUrlTests(SimpleTestCase):
    def test_build_scan_list_url_preserves_filters_and_replaces_page(self):
        params = QueryDict("q=compresse&type=association&page=3", mutable=True)
        self.assertEqual(
            build_scan_list_url("/scan/receipts/", params, page=2),
            "/scan/receipts/?q=compresse&type=association&page=2",
        )

    def test_build_scan_list_url_drops_page_when_target_is_first_page(self):
        params = QueryDict("q=compresse&sort=name&page=4", mutable=True)
        self.assertEqual(
            build_scan_list_url("/scan/receipts/", params, page=1),
            "/scan/receipts/?q=compresse&sort=name",
        )

    def test_build_scan_list_url_can_reset_specific_keys(self):
        params = QueryDict("q=compresse&sort=name&page=4", mutable=True)
        self.assertEqual(
            build_scan_list_url("/scan/receipts/", params, reset_keys={"q", "sort", "page"}),
            "/scan/receipts/",
        )
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_list_urls -v 2`

Expected: FAIL because `wms.scan_list_urls` does not exist yet.

**Step 3: Write minimal implementation**

```python
from urllib.parse import urlencode


def build_scan_list_url(base_url, params, *, page=None, updates=None, reset_keys=None):
    query = params.copy()
    for key in reset_keys or set():
        query.pop(key, None)
    for key, value in (updates or {}).items():
        if value in (None, "", False):
            query.pop(key, None)
        else:
            query[key] = str(value)
    if page is None or page <= 1:
        query.pop("page", None)
    else:
        query["page"] = str(page)
    encoded = query.urlencode()
    return f"{base_url}?{encoded}" if encoded else base_url
```

Create the pagination partial so every cockpit list can reuse:

```django
{% if page_obj.has_other_pages %}
  <div class="scan-filter-actions ui-comp-actions d-flex flex-wrap gap-2 align-items-center mt-3">
    <span class="scan-help ui-comp-note">
      Page {{ page_obj.number }} / {{ page_obj.paginator.num_pages }}
    </span>
    {% if page_prev_url %}<a class="btn btn-tertiary btn-sm" href="{{ page_prev_url }}">Page précédente</a>{% endif %}
    {% if page_next_url %}<a class="btn btn-tertiary btn-sm" href="{{ page_next_url }}">Page suivante</a>{% endif %}
  </div>
{% endif %}
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_list_urls -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/scan_list_urls.py templates/scan/includes/scan_list_pagination.html wms/tests/views/tests_scan_list_urls.py
git commit -m "feat: add shared scan list pagination helpers"
```

### Task 3: Add A Receipt Cockpit Before Refactoring The Receipt List

**Files:**
- Create: `templates/scan/receipt_detail.html`
- Create: `wms/receipt_detail_helpers.py`
- Modify: `wms/scan_urls.py`
- Modify: `wms/views_scan_receipts.py`
- Test: `wms/tests/views/tests_views_scan_receipts.py`
- Bootstrap regression: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

```python
def test_scan_receipt_detail_renders_summary_lines_and_back_link(self):
    receipt = Receipt.objects.create(
        receipt_type=ReceiptType.ASSOCIATION,
        warehouse=self.warehouse,
    )
    response = self.client.get(reverse("scan:scan_receipt_detail", args=[receipt.id]))
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, reverse("scan:scan_receipts_view"))
    self.assertContains(response, receipt.reference or f"Réception {receipt.id}")
```

Add a second safety test:

```python
def test_scan_receipt_detail_exposes_legacy_edit_shortcuts(self):
    receipt = self._create_receipt(ReceiptType.ASSOCIATION)
    response = self.client.get(reverse("scan:scan_receipt_detail", args=[receipt.id]))
    self.assertContains(
        response,
        f"{reverse('scan:scan_receive_association')}?receipt_id={receipt.id}",
    )
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_receipts -v 2`

Expected: FAIL because `scan_receipt_detail` does not exist yet.

**Step 3: Write minimal implementation**

Create a helper that builds a small receipt cockpit payload:

```python
def build_receipt_detail_payload(receipt):
    return {
        "receipt": receipt,
        "receipt_lines": list(receipt.lines.select_related("product", "location").all()),
        "hors_format_items": list(receipt.hors_format_items.all()),
        "shipment_allocations": list(receipt.shipment_allocations.select_related("shipment").all()),
        "back_url": reverse("scan:scan_receipts_view"),
        "edit_url": _receipt_edit_url(receipt),
    }
```

Wire a new route/view:

```python
@scan_staff_required
@require_http_methods(["GET"])
def scan_receipt_detail(request, receipt_id):
    receipt = get_object_or_404(
        Receipt.objects.select_related("source_contact", "carrier_contact", "warehouse")
        .prefetch_related("lines__product", "lines__location", "hors_format_items", "shipment_allocations__shipment"),
        id=receipt_id,
    )
    return render(
        request,
        "scan/receipt_detail.html",
        {
            "active": ACTIVE_RECEIPTS_VIEW,
            "detail": build_receipt_detail_payload(receipt),
        },
    )
```

**Step 4: Run tests to verify they pass**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_receipts -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS on the new route assertions and card-shell/layout assertions.

**Step 5: Commit**

```bash
git add wms/scan_urls.py wms/views_scan_receipts.py wms/receipt_detail_helpers.py templates/scan/receipt_detail.html wms/tests/views/tests_views_scan_receipts.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add receipt cockpit detail page"
```

### Task 4: Convert The Receipt List To Server-Side Search/Sort/Pagination

**Files:**
- Create: `wms/receipt_list_queries.py`
- Modify: `wms/receipt_view_helpers.py`
- Modify: `wms/views_scan_receipts.py`
- Modify: `templates/scan/receipts_view.html`
- Test: `wms/tests/views/tests_views_scan_receipts.py`
- Bootstrap regression: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

```python
def test_scan_receipts_view_searches_across_full_dataset_not_current_page_only(self):
    for index in range(105):
        source = Contact.objects.create(
            name=f"Association pagination {index:03d}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            warehouse=self.warehouse,
            source_contact=source,
        )

    target_source = Contact.objects.create(
        name="Association compresse cible",
        contact_type=ContactType.ORGANIZATION,
        is_active=True,
    )
    Receipt.objects.create(
        receipt_type=ReceiptType.ASSOCIATION,
        warehouse=self.warehouse,
        source_contact=target_source,
    )

    response = self.client.get(reverse("scan:scan_receipts_view"), {"q": "compresse"})

    self.assertEqual(response.status_code, 200)
    self.assertContains(response, "Association compresse cible")
    self.assertEqual(response.context["receipts_page"].number, 1)
```

Add a pagination test:

```python
def test_scan_receipts_view_paginates_at_one_hundred_rows(self):
    for index in range(105):
        self._create_receipt(ReceiptType.PALLET)
    response = self.client.get(reverse("scan:scan_receipts_view"))
    self.assertEqual(len(response.context["receipts"]), 100)
    self.assertTrue(response.context["receipts_page"].has_next())
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_receipts -v 2`

Expected: FAIL because the view currently has no server-side `q`, `sort`, or pagination behavior.

**Step 3: Write minimal implementation**

Create a small query builder:

```python
RECEIPTS_PAGE_SIZE = 100


def build_receipts_list_context(request):
    filter_value = _resolve_receipts_filter(request.GET.get("type"))
    query = (request.GET.get("q") or "").strip()
    sort_value = (request.GET.get("sort") or "received_on_desc").strip()
    page_number = (request.GET.get("page") or "1").strip()

    receipts_qs = _build_receipts_queryset(filter_value)
    if query:
        receipts_qs = receipts_qs.filter(
            Q(reference__icontains=query)
            | Q(source_contact__name__icontains=query)
            | Q(carrier_contact__name__icontains=query)
        )
    receipts_qs = _apply_receipt_sort(receipts_qs, sort_value)

    paginator = Paginator(receipts_qs, RECEIPTS_PAGE_SIZE)
    receipts_page = paginator.get_page(page_number)
    rows = build_receipts_view_rows(receipts_page.object_list)
```

Update the presenter so each row also carries:

```python
{
    "open_url": reverse("scan:scan_receipt_detail", args=[receipt.id]),
    "open_label": "Ouvrir",
}
```

Update the template to:
- load `wms_dates`,
- add `q` and `sort` controls,
- render the `Ouvrir` action,
- use `{% include "scan/includes/scan_list_pagination.html" %}`.

**Step 4: Run tests to verify they pass**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_receipts -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS with new search/sort/pagination behavior.

**Step 5: Commit**

```bash
git add wms/receipt_list_queries.py wms/receipt_view_helpers.py wms/views_scan_receipts.py templates/scan/receipts_view.html wms/tests/views/tests_views_scan_receipts.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: standardize receipt cockpit list behavior"
```

### Task 5: Align Orders View With The Shared Cockpit List Rules

**Files:**
- Create: `wms/order_list_queries.py`
- Modify: `wms/order_view_helpers.py`
- Modify: `wms/views_scan_orders.py`
- Modify: `templates/scan/orders_view.html`
- Test: `wms/tests/views/tests_views_scan_orders.py`
- Bootstrap regression: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

```python
def test_scan_orders_view_searches_all_rows_then_resets_to_page_one(self):
    for index in range(105):
        contact = Contact.objects.create(
            name=f"Association orders {index:03d}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        Order.objects.create(
            association_contact=contact,
            shipper_name=contact.name,
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            review_status=OrderReviewStatus.PENDING,
        )

    target_contact = Contact.objects.create(
        name="Association compresse orders",
        contact_type=ContactType.ORGANIZATION,
        is_active=True,
    )
    Order.objects.create(
        association_contact=target_contact,
        shipper_name=target_contact.name,
        recipient_name="Recipient",
        destination_address="1 Rue Test",
        destination_country="France",
        review_status=OrderReviewStatus.PENDING,
    )

    response = self.client.get(reverse("scan:scan_orders_view"), {"q": "compresse"})

    self.assertContains(response, "Association compresse orders")
    self.assertEqual(response.context["orders_page"].number, 1)
```

Add a pagination test:

```python
def test_scan_orders_view_paginates_after_one_hundred_rows(self):
    # create 105 orders
    response = self.client.get(reverse("scan:scan_orders_view"))
    self.assertEqual(len(response.context["orders"]), 100)
    self.assertTrue(response.context["orders_page"].has_next())
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_orders -v 2`

Expected: FAIL because there is no server-side `q`, `sort`, or pagination context.

**Step 3: Write minimal implementation**

Create a query builder that owns:
- free-text search across reference, association name, recipient name, and creator info where relevant,
- list sort keys,
- pagination,
- next/prev/reset URLs.

Example core:

```python
ORDERS_PAGE_SIZE = 100


def build_orders_list_context(request):
    query = (request.GET.get("q") or "").strip()
    sort_value = (request.GET.get("sort") or "created_desc").strip()
    page_number = (request.GET.get("page") or "1").strip()

    orders_qs = _build_orders_queryset()
    if query:
        orders_qs = orders_qs.filter(
            Q(reference__icontains=query)
            | Q(association_contact__name__icontains=query)
            | Q(recipient_name__icontains=query)
        )
    orders_qs = _apply_order_sort(orders_qs, sort_value)
    paginator = Paginator(orders_qs, ORDERS_PAGE_SIZE)
```

Keep `order_view_helpers.py` focused on row payloads and dossier payloads; do not move filter parsing there.

**Step 4: Run tests to verify they pass**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_orders -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS with the same visual shell and the new list behavior.

**Step 5: Commit**

```bash
git add wms/order_list_queries.py wms/order_view_helpers.py wms/views_scan_orders.py templates/scan/orders_view.html wms/tests/views/tests_views_scan_orders.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: standardize orders cockpit list behavior"
```

### Task 6: Retrofit Shipments Tracking To The Shared Paging/Date Conventions

**Files:**
- Modify: `wms/views_scan_shipments_support.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/shipment_view_helpers.py`
- Modify: `templates/scan/shipments_tracking.html`
- Test: `wms/tests/views/tests_views_scan_shipments.py`
- Test: `wms/tests/views/tests_views_scan_shipments_support.py`
- Bootstrap regression: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

```python
def test_scan_shipments_tracking_paginates_filtered_results(self):
    for index in range(105):
        shipment = self._make_tracking_shipment(reference=f"EXP-{index:03d}")
        self._mark_shipment_planned(shipment)

    target = self._make_tracking_shipment(reference="EXP-COMPRESSE")
    self._mark_shipment_planned(target)

    response = self.client.get(
        reverse("scan:scan_shipments_tracking"),
        {"q": "COMPRESSE"},
    )

    self.assertContains(response, "EXP-COMPRESSE")
    self.assertEqual(response.context["shipments_page"].number, 1)
```

Add a filter-preservation test:

```python
def test_scan_shipments_tracking_page_urls_preserve_filters(self):
    response = self.client.get(
        reverse("scan:scan_shipments_tracking"),
        {"planned_week": "2026-W16", "closed": "all", "dispute": "open"},
    )
    self.assertIn("planned_week=2026-W16", response.context["page_next_url"])
    self.assertIn("closed=all", response.context["page_next_url"])
    self.assertIn("dispute=open", response.context["page_next_url"])
```

**Step 2: Run test to verify it fails**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments_support -v 2`

Expected: FAIL because the tracking list does not paginate yet and does not expose shared page URLs.

**Step 3: Write minimal implementation**

Extend the support/query layer, not the row presenter, with pagination concerns:

```python
SHIPMENTS_TRACKING_PAGE_SIZE = 100


def build_shipments_tracking_list_context(request):
    planned_week_value, planned_week_start, planned_week_end = _parse_planned_week(...)
    closed_filter = _normalize_closed_filter(...)
    dispute_filter = _normalize_dispute_filter(...)
    query = (request.GET.get("q") or "").strip()
    page_number = (request.GET.get("page") or "1").strip()

    shipments_qs = _build_shipments_tracking_queryset()
    shipments_qs = _apply_tracking_filters(...)
    if query:
        shipments_qs = shipments_qs.filter(
            Q(reference__icontains=query)
            | Q(shipper_contact_ref__name__icontains=query)
            | Q(recipient_contact_ref__name__icontains=query)
        )
    paginator = Paginator(shipments_qs, SHIPMENTS_TRACKING_PAGE_SIZE)
```

Update the template to:
- load `wms_dates`,
- add the search box,
- include shared pagination,
- keep `Suivi/MAJ` as the primary cockpit action,
- keep `Clore le dossier` as a documented secondary exception.

**Step 4: Run tests to verify they pass**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments_support -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS with preserved filters and paged list behavior.

**Step 5: Commit**

```bash
git add wms/views_scan_shipments_support.py wms/views_scan_shipments.py wms/shipment_view_helpers.py templates/scan/shipments_tracking.html wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_views_scan_shipments_support.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: standardize shipment tracking cockpit list behavior"
```

### Task 7: Update UI Governance Docs And Shared-Contract References

**Files:**
- Modify: `templates/scan/ui_lab.html`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Modify: `docs/repo-reference/03-impact-map.md`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add assertions that the shared contract is still reflected in the UI regression suite:

```python
def test_scan_cockpit_lists_render_shared_pagination_and_open_actions(self):
    for route_name in [
        "scan:scan_receipts_view",
        "scan:scan_orders_view",
        "scan:scan_shipments_tracking",
    ]:
        response = self.client.get(reverse(route_name))
        self.assertContains(response, "Page")
        self.assertContains(response, "Ouvrir")
```

Adjust the assertions so they no longer rely on `data-table-tools="1"` for the migrated screens if
the implementation removes that client-side mechanism there.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: FAIL until the new list contract is documented and reflected in the regression suite.

**Step 3: Write minimal implementation**

Update:
- the UI Lab table/cockpit guidance text so it documents server-side cockpit lists,
- `04-shared-contracts.md` with the new cockpit-list rules,
- `03-impact-map.md` with propagation reminders for shared list behavior.

Do not promote `Table` to `Core stable`; document it as a strengthened `En convergence` contract.

**Step 4: Run the final proof suite**

Run:
- `./.venv/bin/python manage.py test wms.tests.templatetags.tests_wms_dates -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_scan_list_urls -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_receipts -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_orders -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments_support -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS across the shared contract and the three migrated lists.

**Step 5: Commit**

```bash
git add templates/scan/ui_lab.html docs/repo-reference/04-shared-contracts.md docs/repo-reference/03-impact-map.md wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "docs: codify scan cockpit list contract"
```
