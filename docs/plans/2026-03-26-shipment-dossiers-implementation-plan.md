# Shipment Dossiers UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the legacy shipment list into a searchable `Dossiers` page, keep `Suivi des expéditions` unchanged, and make existing shipments open into a dossier-first cockpit on the legacy Django stack.

**Architecture:** Keep shipment creation on the current creation route and templates, but reframe existing-shipment management around two legacy surfaces: `shipments_ready` becomes the `Dossiers` list and `scan_shipment_edit` renders a dossier-first page for existing shipments. Reuse current legacy handlers, document panels, and tracking logic; add only the minimal routing, template, and queryset changes needed to separate list-vs-cockpit responsibilities cleanly.

**Tech Stack:** Django views/templates, Django ORM query filtering, legacy Bootstrap scan templates, Django test suite via `manage.py test`

---

### Task 1: Rework shipment navigation into an `Expéditions` group

**Files:**
- Modify: `templates/scan/includes/scan_sidebar_navigation.html`
- Modify: `wms/views_scan_shipments_support.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing tests**

Add sidebar assertions for the new shipment group shell and active states.

```python
def test_scan_nav_renders_shipments_group_instead_of_single_link(self):
    response = self.client.get(reverse("scan:scan_shipments_ready"))
    self.assertContains(response, 'id="scan-sidebar-shipments-toggle"')
    self.assertContains(response, 'id="scan-sidebar-shipments-group"')
    self.assertContains(response, "Dossiers")
    self.assertContains(response, "Suivi des expéditions")
    self.assertNotContains(response, 'id="scan-sidebar-shipments"')

def test_scan_shipments_ready_marks_shipments_dossiers_active(self):
    response = self.client.get(reverse("scan:scan_shipments_ready"))
    self.assertEqual(response.context_data["active"], "shipments_dossiers")
```

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_nav_renders_shipments_group_instead_of_single_link \
  wms.tests.views.tests_views_scan_shipments.ScanShipmentViewsTests.test_scan_shipments_ready_marks_shipments_dossiers_active -v 2
```

Expected:
- FAIL because the sidebar still renders `scan-sidebar-shipments`
- FAIL because the list view still uses `active == "shipments_ready"`

**Step 3: Write minimal implementation**

- add a dedicated shipment-group toggle and collapse block in `templates/scan/includes/scan_sidebar_navigation.html`
- add child links for:
  - `scan:scan_shipments_ready` labeled `Dossiers`
  - `scan:scan_shipments_tracking` labeled `Suivi des expéditions`
- introduce `ACTIVE_SHIPMENTS_DOSSIERS = "shipments_dossiers"` in `wms/views_scan_shipments_support.py`
- update list and edit views to use the new active key when the dossier context is shown

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add templates/scan/includes/scan_sidebar_navigation.html wms/views_scan_shipments_support.py wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: group shipment navigation around dossiers"
```

### Task 2: Add searchable dossier-list query support and row metadata

**Files:**
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/shipment_view_helpers.py`
- Test: `wms/tests/views/tests_views.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`
- Test: `wms/tests/shipment/tests_shipment_view_helpers.py`

**Step 1: Write the failing tests**

Cover search behavior and row metadata needed by the lighter dossier list.

```python
def test_scan_shipments_ready_filters_by_reference_shipper_recipient_and_destination(self):
    destination = Destination.objects.create(city="Dakar", iata_code="DKR", country="Senegal", correspondent_contact=self.contact)
    Shipment.objects.create(reference="EXP-001", shipper_name="ASF Paris", recipient_name="Dispensaire A", destination=destination, destination_address="x")
    Shipment.objects.create(reference="EXP-002", shipper_name="ASF Lyon", recipient_name="Hopital B", destination_address="x")

    response = self.client.get(reverse("scan:scan_shipments_ready"), {"q": "Dakar"})

    self.assertContains(response, "EXP-001")
    self.assertNotContains(response, "EXP-002")
    self.assertEqual(response.context_data["search_query"], "Dakar")

def test_build_shipments_ready_rows_exposes_document_summary_counts(self):
    shipment = self._create_shipment()
    Document.objects.create(shipment=shipment, doc_type=DocumentType.ADDITIONAL)
    rows = build_shipments_ready_rows([shipment])
    self.assertEqual(rows[0]["additional_document_count"], 1)
    self.assertGreater(rows[0]["generated_document_count"], 0)
```

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.views.tests_views.ScanViewsTests.test_scan_shipments_ready_filters_by_reference_shipper_recipient_and_destination \
  wms.tests.shipment.tests_shipment_view_helpers.ShipmentViewHelpersTests.test_build_shipments_ready_rows_exposes_document_summary_counts -v 2
```

Expected:
- FAIL because `q` filtering is not implemented
- FAIL because dossier-list row metadata does not include document summary counts

**Step 3: Write minimal implementation**

In `wms/views_scan_shipments.py`:
- read `q = (request.GET.get("q") or "").strip()`
- apply a `Q(...)` filter over:
  - `reference__icontains=q`
  - `shipper_name__icontains=q`
  - `recipient_name__icontains=q`
  - `destination__city__icontains=q`
  - `destination__country__icontains=q`
  - `destination__iata_code__icontains=q`
  - optional contact-ref names if needed for parity with displayed labels
- call `.distinct()` after the search filter
- expose `search_query` in the template context

In `wms/shipment_view_helpers.py`:
- enrich each dossier row with:
  - `generated_document_count`
  - `additional_document_count`
  - a compact `documents_summary` string or equivalent display value

Use the current generated-document contract as the source of truth, not a hardcoded legacy list or the old row dropdown order.
After merge `79145519`, that source of truth now includes the current shipment document helpers and print strategy:
- `build_shipment_document_links(...)`
- `SHIPMENT_DOCUMENT_TEMPLATES`
- `wms/print_document_strategy.py`

Do not hardcode a static document count in the final implementation, because the current contract now includes the HTML-first contact sheet path and can evolve independently of the dossier UI.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add wms/views_scan_shipments.py wms/shipment_view_helpers.py wms/tests/views/tests_views.py wms/tests/views/tests_views_scan_shipments.py wms/tests/shipment/tests_shipment_view_helpers.py
git commit -m "feat: add shipment dossier search filters"
```

### Task 3: Convert `shipments_ready` into the lighter `Dossiers` list

**Files:**
- Modify: `templates/scan/shipments_ready.html`
- Test: `wms/tests/views/tests_views_scan_shipments.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views.py`

**Step 1: Write the failing tests**

Lock the new UI contract for the list page.

```python
def test_scan_shipments_ready_renders_dossiers_title_and_search_form(self):
    response = self.client.get(reverse("scan:scan_shipments_ready"))
    self.assertContains(response, "Dossiers")
    self.assertContains(response, 'name="q"')
    self.assertContains(response, "Rechercher une expédition")

def test_scan_shipments_ready_uses_single_open_action_per_row(self):
    shipment = Shipment.objects.create(...)
    response = self.client.get(reverse("scan:scan_shipments_ready"))
    self.assertContains(response, "Ouvrir")
    self.assertNotContains(response, ">Suivi<")
    self.assertNotContains(response, ">Modifier<")
    self.assertNotContains(response, "scan-doc-menu")
```

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments.ScanShipmentViewsTests.test_scan_shipments_ready_renders_dossiers_title_and_search_form \
  wms.tests.views.tests_views.ScanViewsTests.test_scan_shipments_ready_uses_single_open_action_per_row \
  wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_shipments_ready_uses_split_numero_expedition_header_copy -v 2
```

Expected:
- FAIL because the page still renders `Vue Expéditions`
- FAIL because row-level tracking, edit, and document-launch actions still exist

**Step 3: Write minimal implementation**

Update `templates/scan/shipments_ready.html` to:
- rename the page to `Dossiers`
- render a `GET` search form with a single `q` field
- keep the stale-draft archive action above the table
- remove the row-level document dropdown
- replace row actions with a single `Ouvrir` button linking to `scan:scan_shipment_edit`
- keep the current status pill and core list columns
- render the new document summary field instead of document action buttons

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add templates/scan/shipments_ready.html wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_views.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: simplify shipment dossiers list"
```

### Task 4: Render existing shipments as a dossier-first cockpit

**Files:**
- Create: `templates/scan/shipment_dossier.html`
- Create: `templates/scan/includes/shipment_dossier_header.html`
- Create: `templates/scan/includes/shipment_dossier_summary.html`
- Modify: `templates/scan/includes/shipment_create_intro.html`
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/views_scan_shipments_support.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`
- Test: `wms/tests/views/tests_views.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing tests**

Capture the dossier contract on the existing shipment route.

```python
def test_scan_shipment_edit_renders_dossier_template_for_existing_shipment(self):
    shipment = Shipment.objects.create(...)
    response = self.client.get(reverse("scan:scan_shipment_edit", args=[shipment.id]))
    self.assertTemplateUsed(response, "scan/shipment_dossier.html")
    self.assertContains(response, f"Dossier expédition {shipment.reference}")
    self.assertContains(response, "Administratif")
    self.assertContains(response, "Documents")
    self.assertContains(response, "Suivi")
    self.assertContains(response, "Modifier")

def test_scan_shipment_edit_marks_locked_shipment_as_read_only(self):
    shipment = Shipment.objects.create(status=ShipmentStatus.PLANNED, ...)
    response = self.client.get(reverse("scan:scan_shipment_edit", args=[shipment.id]))
    self.assertNotContains(response, 'type="submit" class="scan-submit btn btn-primary"')
    self.assertContains(response, "Expédition verrouillée")
```

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments.ScanShipmentViewsTests.test_scan_shipment_edit_renders_dossier_template_for_existing_shipment \
  wms.tests.views.tests_views.ScanViewsTests.test_scan_shipment_edit_marks_locked_shipment_as_read_only -v 2
```

Expected:
- FAIL because `scan_shipment_edit` still renders `scan/shipment_create.html`
- FAIL because no dossier-first summary shell exists

**Step 3: Write minimal implementation**

In `wms/views_scan_shipments.py`:
- add `TEMPLATE_SHIPMENT_DOSSIER = "scan/shipment_dossier.html"`
- let `_render_shipment_form(...)` accept an optional `template_name`
- keep `scan_shipment_create` on `scan/shipment_create.html`
- make `scan_shipment_edit` render `scan/shipment_dossier.html`
- keep current POST handling and form context intact
- add dossier summary context fields:
  - `is_locked`
  - `is_closed`
  - `can_edit`
  - `return_to`

In the new dossier template:
- show a dossier header with reference, status, destination, and key dates
- show grouped actions near the top:
  - `Modifier` when allowed
  - `Ouvrir suivi`
  - `Clore le dossier` only when eligible or a clear blocked state if not
- reuse current tracking, generated-document, additional-document, and receipt-allocation panels
- place shipment form controls in an explicit edit section so the page remains consultation-first

Document-link constraint after merge `79145519`:
- do not introduce dossier-specific document endpoints
- reuse the current print routes and helpers so the new HTML-vs-PDF delivery behavior in `wms/views_print_docs.py` and `wms/views_print_labels.py` remains intact
- if a dossier action needs browser-print behavior, pass through the existing route contract instead of rendering documents directly from the dossier view

Update `templates/scan/includes/shipment_create_intro.html` so creation keeps `Créer une expédition` wording and dossier pages no longer inherit the old `Modifier l'expédition` page title.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add templates/scan/shipment_dossier.html templates/scan/includes/shipment_dossier_header.html templates/scan/includes/shipment_dossier_summary.html templates/scan/includes/shipment_create_intro.html wms/views_scan_shipments.py wms/views_scan_shipments_support.py wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_views.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: render existing shipments as dossiers"
```

### Task 5: Align tracking return targets and FAQ copy with `Dossiers`

**Files:**
- Modify: `wms/views_scan_shipments_support.py`
- Modify: `templates/scan/faq.html`
- Modify: `wms/views_scan_shipments.py`
- Test: `wms/tests/views/tests_views.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing tests**

Protect backward-compatible return handling and updated help copy.

```python
def test_scan_shipment_track_uses_dossiers_return_target_in_link(self):
    shipment, _carton = self._create_shipment_with_carton()
    response = self.client.get(
        f"{reverse('scan:scan_shipment_track', args=[shipment.tracking_token])}?return_to=shipments_dossiers"
    )
    self.assertContains(response, f'href="{reverse("scan:scan_shipments_ready")}"')

def test_scan_faq_uses_dossiers_vocabulary_for_shipment_list(self):
    response = self.client.get(reverse("scan:scan_faq"))
    self.assertContains(response, "Dossiers")
    self.assertNotContains(response, "Vue Expéditions")
```

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.views.tests_views.ScanViewsTests.test_scan_shipment_track_uses_dossiers_return_target_in_link \
  wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_faq_uses_dossiers_vocabulary_for_shipment_list -v 2
```

Expected:
- FAIL because `shipments_dossiers` is not yet a recognized `return_to` key
- FAIL because FAQ copy still uses `Vue Expéditions`

**Step 3: Write minimal implementation**

In `wms/views_scan_shipments_support.py`:
- add `RETURN_TO_SHIPMENTS_DOSSIERS = "shipments_dossiers"`
- map both `shipments_dossiers` and legacy `shipments_ready` to `scan:scan_shipments_ready`
- default dossier-origin links to `shipments_dossiers`

In `templates/scan/faq.html`:
- rename the list page section to `Dossiers`
- keep `Suivi des expéditions` wording unchanged
- update explanatory bullets so the new split is explicit:
  - `Dossiers` for consultation and opening
  - `Suivi des expéditions` for transversal milestone follow-up

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add wms/views_scan_shipments_support.py wms/views_scan_shipments.py templates/scan/faq.html wms/tests/views/tests_views.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: align shipment tracking return flow with dossiers"
```

### Task 6: Run focused regression verification

**Files:**
- Verify only: `wms/tests/views/tests_views_scan_shipments.py`
- Verify only: `wms/tests/views/tests_views.py`
- Verify only: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Verify only: `wms/tests/shipment/tests_shipment_view_helpers.py`

**Step 1: Run the focused shipment regression suite**

Run:

```bash
.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_views \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.shipment.tests_shipment_view_helpers -v 2
```

Expected:
- PASS

**Step 2: Fix any dossier-regression failures**

If a failure appears:
- update the smallest relevant template, helper, or view
- rerun only the failing test class first
- rerun the full command once the fix is green

**Step 3: Commit**

```bash
git add templates/scan/shipments_ready.html templates/scan/shipment_dossier.html templates/scan/includes/scan_sidebar_navigation.html templates/scan/faq.html wms/views_scan_shipments.py wms/views_scan_shipments_support.py wms/shipment_view_helpers.py wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_views.py wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/shipment/tests_shipment_view_helpers.py
git commit -m "test: verify shipment dossier flow regressions"
```
