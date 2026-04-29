# Shipment Prepared Without Cartons and Batch Creation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let scan operators create single or batch shipment dossiers with planned carton counts, print paper dossiers and preparatory labels before real cartons are selected, and keep stock/readiness truth tied only to real cartons.

**Architecture:** Add a planned carton count to `Shipment` and keep it separate from real `Carton` rows. Extend the existing legacy Django scan shipment handlers, templates, print-context builders, and print bundle routes; avoid fake cartons and avoid changing readiness semantics. Add a batch line-builder flow that creates document-first shipments all-or-nothing and routes operators to a print summary.

**Tech Stack:** Django models/forms/views/templates, legacy scan JavaScript, Django test runner, existing print context and bundle routes.

---

**Execution rules**

- Use `@test-driven-development`: write the failing test before production code for each task.
- Use `@verification-before-completion`: run the listed targeted tests before calling a task done.
- Use `@systematic-debugging` for any unexpected test failure.
- Commit steps below are checkpoints only. In this repo, do not execute `git commit` without explicit user approval.
- If shared scan JS/CSS changes affect cached assets, bump the scan service worker version in both `wms/views_scan_misc.py` and `templates/scan/base.html`.

### Task 1: Add planned carton count to the shipment model

**Files:**
- Modify: `wms/models_domain/shipment.py`
- Create: `wms/migrations/<next>_shipment_planned_carton_count.py`
- Test: `wms/tests/core/tests_models_methods.py`
- Test: `wms/tests/shipment/tests_shipment_status.py`

**Step 1: Write the failing model test**

Add a test that proves the field defaults to `0` and does not create real cartons:

```python
def test_shipment_planned_carton_count_defaults_to_zero(self):
    shipment = Shipment.objects.create(
        shipper_name="ASF",
        recipient_name="Hopital",
        destination_address="Abidjan",
        destination_country="Cote d'Ivoire",
    )

    self.assertEqual(shipment.planned_carton_count, 0)
    self.assertEqual(shipment.carton_set.count(), 0)
```

Add a readiness guard if the current tests do not already cover zero-real-carton confirmation:

```python
def test_planned_carton_count_does_not_make_shipment_ready(self):
    shipment = Shipment.objects.create(
        shipper_name="ASF",
        recipient_name="Hopital",
        destination_address="Abidjan",
        destination_country="Cote d'Ivoire",
        planned_carton_count=10,
    )

    self.assertFalse(shipment_can_be_confirmed_ready(shipment))
```

**Step 2: Run tests to verify failure**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.core.tests_models_methods \
  wms.tests.shipment.tests_shipment_status \
  -v 2
```

Expected: FAIL because `planned_carton_count` does not exist.

**Step 3: Implement the field and migration**

In `wms/models_domain/shipment.py`:

```python
planned_carton_count = models.PositiveIntegerField(default=0)
```

Create the migration with:

```bash
./.venv/bin/python manage.py makemigrations wms
```

Review that the migration only adds `planned_carton_count` with default `0`.

**Step 4: Run targeted tests**

Run the same command from Step 2.

Expected: PASS.

**Step 5: Checkpoint**

```bash
git add wms/models_domain/shipment.py wms/migrations/<migration>.py wms/tests/core/tests_models_methods.py wms/tests/shipment/tests_shipment_status.py
git commit -m "feat: add planned carton count to shipments"
```

Do not run the commit without explicit approval.

### Task 2: Add print helpers for planned counts and virtual carton slots

**Files:**
- Modify: `wms/print_context.py`
- Modify: `wms/views_print_docs.py`
- Test: `wms/tests/print/tests_print_context.py`
- Test: `wms/tests/views/tests_views_print_docs.py`

**Step 1: Write failing print-context tests**

Add tests that lock the count behavior:

```python
def test_shipment_document_context_uses_planned_count_without_cartons(self):
    shipment = Shipment.objects.create(
        shipper_name="ASF",
        recipient_name="Hopital",
        destination_address="Abidjan",
        destination_country="Cote d'Ivoire",
        planned_carton_count=10,
    )

    context = build_shipment_document_context(shipment, "shipment_note")

    self.assertEqual(context["carton_count"], 10)
    self.assertEqual(context["carton_rows"], [])
```

Add a test for mixed real and virtual slots:

```python
def test_preparatory_label_slots_fill_missing_planned_positions(self):
    shipment = Shipment.objects.create(
        shipper_name="ASF",
        recipient_name="Hopital",
        destination_address="Abidjan",
        destination_country="Cote d'Ivoire",
        planned_carton_count=3,
    )
    carton = Carton.objects.create(code="MM-1", shipment=shipment, status=CartonStatus.ASSIGNED)

    slots = build_shipment_preparatory_label_slots(shipment)

    self.assertEqual([slot.position for slot in slots], [1, 2, 3])
    self.assertEqual(slots[0].carton, carton)
    self.assertEqual(slots[1].code, f"{shipment.reference}-P02")
    self.assertTrue(slots[1].is_virtual)
```

**Step 2: Run tests to verify failure**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.print.tests_print_context \
  wms.tests.views.tests_views_print_docs \
  -v 2
```

Expected: FAIL because the helpers do not exist and `carton_count` is still `len(cartons)`.

**Step 3: Implement minimal helpers**

In `wms/print_context.py`, add small helpers:

```python
def effective_shipment_carton_count(shipment, cartons=None):
    real_count = len(cartons) if cartons is not None else shipment.carton_set.count()
    planned_count = int(getattr(shipment, "planned_carton_count", 0) or 0)
    return max(real_count, planned_count)
```

Use it in `build_shipment_document_context` for `carton_count`.

Add a light data structure for virtual slots:

```python
@dataclass(frozen=True)
class ShipmentLabelSlot:
    position: int
    total: int
    code: str
    carton: Carton | None = None
    is_virtual: bool = False
```

Build slots by ordered real cartons first, then virtual positions up to the effective count.

**Step 4: Wire preparatory label rendering**

In `wms/views_print_docs.py`, add a builder parallel to `_build_shipment_carton_document_pages`, but using slots and omitting carton packing lists for virtual slots:

```python
def _build_shipment_preparatory_label_pages(request, shipment):
    shipment.ensure_qr_code(request=request)
    donation_context = build_shipment_document_context(shipment, "donation_certificate")
    pages = []
    for slot in build_shipment_preparatory_label_slots(shipment):
        pages.append({
            "page_id": f"shipment-preparatory-label-page-{slot.position}",
            "slot": slot,
            "donation_html": ...,
            "shipment_label_html": ...,
            "contact_html": ...,
        })
    return pages
```

Add a new bundle key such as `preparatory_labels` and render it with the existing A4 carton document template only if the template can tolerate missing packing blocks; otherwise create a dedicated print template in Task 5.

**Step 5: Run targeted tests**

Run the command from Step 2.

Expected: PASS.

**Step 6: Checkpoint**

```bash
git add wms/print_context.py wms/views_print_docs.py wms/tests/print/tests_print_context.py wms/tests/views/tests_views_print_docs.py
git commit -m "feat: add planned shipment print slots"
```

Do not run the commit without explicit approval.

### Task 3: Add single shipment creation modes and post-create redirect choice

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/scan_shipment_handlers.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `templates/scan/shipment_create.html`
- Modify: `templates/scan/includes/shipment_create_details_panel.html`
- Modify: `templates/scan/includes/shipment_create_intro.html`
- Modify: `wms/static/scan/scan.js`
- Test: `wms/tests/forms/tests_forms.py`
- Test: `wms/tests/scan/tests_scan_shipment_handlers.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write failing handler tests**

Add tests for without-cartons mode:

```python
def test_handle_shipment_create_post_prepares_without_cartons(self):
    request = self._request({
        "creation_mode": "without_cartons",
        "planned_carton_count": "10",
        "post_create_action": "show_dossier",
    })
    form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=0))

    with mock.patch("wms.scan_shipment_handlers.Shipment.objects.create") as create_mock:
        response, carton_count, line_values, line_errors = handle_shipment_create_post(
            request,
            form=form,
            available_carton_ids=set(),
        )

    self.assertEqual(carton_count, 0)
    self.assertEqual(line_values, [])
    self.assertEqual(line_errors, {})
    self.assertEqual(create_mock.call_args.kwargs["planned_carton_count"], 10)
```

Add a validation test:

```python
def test_handle_shipment_create_post_requires_planned_count_without_cartons(self):
    request = self._request({"creation_mode": "without_cartons", "planned_carton_count": ""})
    form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=0))

    response, *_ = handle_shipment_create_post(
        request,
        form=form,
        available_carton_ids=set(),
    )

    self.assertIsNone(response)
    self.assertIn(("planned_carton_count", "Nombre de colis prevus requis."), form.errors)
```

**Step 2: Run tests to verify failure**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.scan.tests_scan_shipment_handlers \
  wms.tests.forms.tests_forms \
  wms.tests.views.tests_views_scan_shipments \
  -v 2
```

Expected: FAIL because the new mode fields are absent.

**Step 3: Implement form fields**

Add constants in `wms/scan_shipment_handlers.py` or a small local module:

```python
CREATE_MODE_WITH_CARTONS = "with_cartons"
CREATE_MODE_WITHOUT_CARTONS = "without_cartons"
POST_CREATE_SHOW_DOSSIER = "show_dossier"
POST_CREATE_STAY = "stay"
```

In `ScanShipmentForm`, add non-model fields:

```python
creation_mode = forms.ChoiceField(...)
planned_carton_count = forms.IntegerField(min_value=1, required=False)
post_create_action = forms.ChoiceField(...)
```

Keep defaults:

- `creation_mode=with_cartons`
- `post_create_action=show_dossier`

Validate `planned_carton_count` only when `creation_mode=without_cartons`.

**Step 4: Implement handler branching**

In `handle_shipment_create_post`:

- if mode is `without_cartons`, skip `parse_shipment_lines`;
- create shipment with `planned_carton_count`;
- never attach cartons or call packing helpers;
- call `sync_shipment_ready_state(shipment)` as today, and verify it remains non-ready;
- redirect based on `post_create_action`.

For `stay`, redirect back to `/scan/shipment/` with query parameters for selected parties and a success message, or re-render the form with a clean unbound state and quick links. Prefer redirect to avoid duplicate POST.

**Step 5: Update templates and JS**

Update the details panel:

- add a segmented/radio control for `creation_mode`;
- show planned count only for `without_cartons`;
- show existing carton/product line builder only for `with_cartons`;
- add post-create choice for single creation.

In `wms/static/scan/scan.js`, hide/show sections and allow `0` generated lines when without-cartons mode is selected.

Because `wms/static/scan/scan.js` changes, bump the service worker version in:

- `wms/views_scan_misc.py`
- `templates/scan/base.html`

**Step 6: Run targeted tests**

Run the command from Step 2.

Expected: PASS.

**Step 7: Checkpoint**

```bash
git add wms/forms.py wms/scan_shipment_handlers.py wms/views_scan_shipments.py templates/scan/shipment_create.html templates/scan/includes/shipment_create_details_panel.html templates/scan/includes/shipment_create_intro.html wms/static/scan/scan.js wms/views_scan_misc.py templates/scan/base.html wms/tests/forms/tests_forms.py wms/tests/scan/tests_scan_shipment_handlers.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: add shipment preparation modes"
```

Do not run the commit without explicit approval.

### Task 4: Add batch creation service and all-or-nothing tests

**Files:**
- Create: `wms/shipment_batch_handlers.py`
- Modify: `wms/scan_urls.py`
- Modify: `wms/views.py`
- Modify: `wms/views_scan_shipments.py`
- Test: `wms/tests/scan/tests_shipment_batch_handlers.py`

**Step 1: Write failing service tests**

Create tests for all-or-nothing behavior:

```python
def test_create_prepared_shipment_batch_creates_independent_shipments(self):
    rows = [
        {
            "destination": destination_a,
            "shipper_contact": shipper_a,
            "recipient_contact": recipient_a,
            "planned_carton_count": 10,
        },
        {
            "destination": destination_b,
            "shipper_contact": shipper_b,
            "recipient_contact": recipient_b,
            "planned_carton_count": 5,
        },
    ]

    result = create_prepared_shipment_batch(rows=rows, user=self.user)

    self.assertEqual(len(result.shipments), 2)
    self.assertEqual(result.shipments[0].planned_carton_count, 10)
    self.assertEqual(result.shipments[1].planned_carton_count, 5)
```

```python
def test_create_prepared_shipment_batch_is_all_or_nothing(self):
    rows = [valid_row, {**invalid_row, "planned_carton_count": 0}]

    with self.assertRaises(ShipmentBatchValidationError):
        create_prepared_shipment_batch(rows=rows, user=self.user)

    self.assertEqual(Shipment.objects.count(), 0)
```

**Step 2: Run tests to verify failure**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.scan.tests_shipment_batch_handlers -v 2
```

Expected: FAIL because module/service does not exist.

**Step 3: Implement service**

Create `wms/shipment_batch_handlers.py` with:

- row normalization;
- per-row validation using the same party selection helpers as single shipment creation;
- `transaction.atomic()` around the full batch;
- `Shipment.objects.create(...)` for each row;
- `planned_carton_count` saved per shipment;
- party snapshot payload applied as in single creation.

Keep this service independent from templates so it is testable.

**Step 4: Run targeted test**

Run the command from Step 2.

Expected: PASS.

**Step 5: Checkpoint**

```bash
git add wms/shipment_batch_handlers.py wms/tests/scan/tests_shipment_batch_handlers.py
git commit -m "feat: add prepared shipment batch service"
```

Do not run the commit without explicit approval.

### Task 5: Add batch creation UI and summary page

**Files:**
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/scan_urls.py`
- Modify: `wms/views.py`
- Create: `templates/scan/shipment_batch_create.html`
- Create: `templates/scan/shipment_batch_summary.html`
- Modify: `templates/scan/includes/scan_sidebar_navigation.html`
- Modify: `wms/static/scan/scan.js`
- Test: `wms/tests/views/tests_views_scan_shipments.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write failing view tests**

Add tests:

```python
def test_scan_shipment_batch_create_renders_line_builder(self):
    response = self.client.get(reverse("scan:scan_shipment_batch_create"))

    self.assertEqual(response.status_code, 200)
    self.assertContains(response, 'id="shipment-batch-form"')
    self.assertContains(response, "Ajouter une expedition")
    self.assertContains(response, "Valider le batch")
```

```python
def test_scan_shipment_batch_create_posts_valid_rows_to_summary(self):
    response = self.client.post(
        reverse("scan:scan_shipment_batch_create"),
        {
            "row_count": "2",
            "row_1_destination": str(destination_a.id),
            "row_1_shipper_contact": str(shipper_a.id),
            "row_1_recipient_contact": str(recipient_a.id),
            "row_1_planned_carton_count": "10",
            "row_2_destination": str(destination_b.id),
            "row_2_shipper_contact": str(shipper_b.id),
            "row_2_recipient_contact": str(recipient_b.id),
            "row_2_planned_carton_count": "5",
        },
    )

    self.assertRedirects(response, reverse("scan:scan_shipment_batch_summary"))
```

**Step 2: Run tests to verify failure**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_scan_bootstrap_ui \
  -v 2
```

Expected: FAIL because route/templates do not exist.

**Step 3: Implement views and routes**

Routes:

```python
path("shipment/batch/", views.scan_shipment_batch_create, name="scan_shipment_batch_create")
path("shipment/batch/summary/", views.scan_shipment_batch_summary, name="scan_shipment_batch_summary")
```

Views:

- GET renders one empty row.
- POST parses `row_count` and `row_N_*` fields.
- Valid POST stores created shipment IDs in session, then redirects summary.
- Invalid POST re-renders rows with per-line errors.

Summary:

- loads session shipment IDs;
- filters archived shipments out;
- renders created references and print actions.

**Step 4: Implement row-builder JS**

Add batch-specific JS in `wms/static/scan/scan.js` or a small module loaded by the template:

- add row;
- duplicate row;
- delete row;
- reindex names;
- reuse existing destination/contact JSON filtering where practical.

Because shared scan JS changes, bump service worker versions:

- `wms/views_scan_misc.py`
- `templates/scan/base.html`

**Step 5: Run targeted tests**

Run the command from Step 2.

Expected: PASS.

**Step 6: Checkpoint**

```bash
git add wms/views_scan_shipments.py wms/scan_urls.py wms/views.py templates/scan/shipment_batch_create.html templates/scan/shipment_batch_summary.html templates/scan/includes/scan_sidebar_navigation.html wms/static/scan/scan.js wms/views_scan_misc.py templates/scan/base.html wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add prepared shipment batch UI"
```

Do not run the commit without explicit approval.

### Task 6: Add preparatory label and batch print routes

**Files:**
- Modify: `wms/views_print_docs.py`
- Modify: `wms/scan_urls.py`
- Modify: `wms/views.py`
- Create: `templates/print/shipment_preparatory_labels_a4.html`
- Create: `templates/print/shipment_batch_bundle_a4.html`
- Modify: `wms/shipment_view_helpers.py`
- Test: `wms/tests/views/tests_views_print_docs.py`
- Test: `wms/tests/shipment/tests_shipment_view_helpers.py`

**Step 1: Write failing print route tests**

Add a single-shipment preparatory labels test:

```python
def test_scan_shipment_view_bundle_routes_preparatory_labels(self):
    shipment = Shipment.objects.create(
        shipper_name="ASF",
        recipient_name="Hopital",
        destination_address="Abidjan",
        destination_country="Cote d'Ivoire",
        planned_carton_count=10,
    )

    response = self.client.get(
        reverse("scan:scan_shipment_view_bundle", args=[shipment.id, "preparatory_labels"])
    )

    self.assertContains(response, "EXP")
    self.assertContains(response, "1/10")
    self.assertContains(response, "10/10")
    self.assertContains(response, 'data-print-doc-type="shipment_label"')
    self.assertContains(response, 'data-print-doc-type="contact_label"')
    self.assertContains(response, 'data-print-doc-type="donation_certificate"')
    self.assertNotContains(response, 'data-print-doc-type="packing_list_carton"')
```

Add batch print tests:

```python
def test_scan_shipment_batch_view_bundle_paper_renders_all_shipments(self):
    response = self.client.get(
        reverse("scan:scan_shipment_batch_view_bundle", args=["paper"])
        + f"?shipment_ids={shipment_a.id},{shipment_b.id}"
    )

    self.assertContains(response, shipment_a.reference)
    self.assertContains(response, shipment_b.reference)
```

**Step 2: Run tests to verify failure**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_print_docs \
  wms.tests.shipment.tests_shipment_view_helpers \
  -v 2
```

Expected: FAIL because routes/templates/actions do not exist.

**Step 3: Implement single-shipment preparatory label bundle**

Add `preparatory_labels` to `_shipment_view_bundle_context`.

Create `templates/print/shipment_preparatory_labels_a4.html` using the existing print partials:

- donation certificate body;
- shipment/IATA label body;
- contact label body.

Avoid carton packing list for virtual slots.

**Step 4: Implement batch bundle routes**

Add routes:

```python
path("shipment/batch/print-bundle/<str:bundle_key>/", views.scan_shipment_batch_view_bundle, name="scan_shipment_batch_view_bundle")
```

Supported keys:

- `paper`
- `preparatory_labels`

Fetch shipments from `shipment_ids` query string, active only, ordered by ID. Reject empty or invalid sets with `Http404`.

**Step 5: Update dossier and summary actions**

In `wms/shipment_view_helpers.py`, add preparatory labels to grouped print actions where applicable:

- always show if `planned_carton_count > 0`;
- optionally show for real cartons too if it is useful as a label-only bundle.

On batch summary, add group links using `shipment_ids`.

**Step 6: Run targeted tests**

Run the command from Step 2.

Expected: PASS.

**Step 7: Checkpoint**

```bash
git add wms/views_print_docs.py wms/scan_urls.py wms/views.py templates/print/shipment_preparatory_labels_a4.html templates/print/shipment_batch_bundle_a4.html wms/shipment_view_helpers.py wms/tests/views/tests_views_print_docs.py wms/tests/shipment/tests_shipment_view_helpers.py
git commit -m "feat: add preparatory shipment label bundles"
```

Do not run the commit without explicit approval.

### Task 7: Update docs, FAQ, and changelog

**Files:**
- Modify: `templates/scan/faq.html`
- Modify: `wms/faq_changelog.py`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/03c-impact-shipments.md`
- Modify: `docs/repo-reference/03e-impact-print-documents.md`
- Modify: `docs/repo-reference/04-shared-contracts/05-shipments-tracking.md`
- Modify: `docs/release_checklist.md`
- Test: nearest docs/UI tests if existing assertions cover FAQ/changelog

**Step 1: Write or update tests first**

If existing tests assert FAQ or changelog content, update them before changing docs. If not, add a focused view test:

```python
def test_scan_faq_mentions_prepared_shipments_without_cartons(self):
    response = self.client.get(reverse("scan:scan_faq"))

    self.assertContains(response, "Preparer sans colis")
```

**Step 2: Run test to verify failure**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2
```

Expected: FAIL until FAQ/changelog docs are updated.

**Step 3: Update docs**

Document:

- planned count is not real carton count;
- prepared label bundles use virtual slots;
- readiness/planning still require real cartons;
- batch creation is all-or-nothing;
- batch v1 is document-first, not carton-selection batch.

Add FAQ changelog entry with date `2026-04-29` and placeholder PR number if needed by current convention.

**Step 4: Run docs/UI tests**

Run the command from Step 2 and any nearby FAQ/changelog tests found by `rg "faq_changelog|scan_faq" wms/tests`.

Expected: PASS.

**Step 5: Checkpoint**

```bash
git add templates/scan/faq.html wms/faq_changelog.py docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/03c-impact-shipments.md docs/repo-reference/03e-impact-print-documents.md docs/repo-reference/04-shared-contracts/05-shipments-tracking.md docs/release_checklist.md
git commit -m "docs: document prepared shipment workflow"
```

Do not run the commit without explicit approval.

### Task 8: Final verification

**Files:**
- No expected code changes unless tests reveal gaps.

**Step 1: Run targeted shipment, print, and batch tests**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.forms.tests_forms \
  wms.tests.scan.tests_scan_shipment_handlers \
  wms.tests.scan.tests_shipment_batch_handlers \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_views_print_docs \
  wms.tests.shipment.tests_shipment_view_helpers \
  wms.tests.shipment.tests_shipment_status \
  wms.tests.print.tests_print_context \
  -v 2
```

Expected: PASS.

**Step 2: Run living workflow smoke tests**

Run:

```bash
./.venv/bin/python manage.py test \
  api.tests.tests_ui_e2e_workflows.UiApiE2EWorkflowsTests.test_e2e_scan_workflow_stock_to_close_with_docs_labels_templates \
  wms.tests.core.tests_flow.FlowTests.test_import_to_order_prepare_flow \
  -v 2
```

Expected: PASS.

**Step 3: Run repository-level checks if time allows**

Run:

```bash
make test
```

or the repo's standard CI target if available and practical:

```bash
make ci
```

Expected: PASS.

**Step 4: Manual browser verification**

Start the local Django server if needed, then verify:

- `/scan/shipment/` can create one shipment with `Preparer sans colis`, `10` planned cartons, and "Afficher le dossier cree";
- the dossier shows planned vs associated counts;
- paper dossier prints `10`;
- preparatory labels show positions `1/10` through `10/10`;
- `/scan/shipment/` can create with real cartons through the existing mode;
- `/scan/shipment/batch/` supports adding, duplicating, deleting rows;
- invalid batch rows block all creation;
- valid batch rows create independent shipments and show summary print actions.

**Step 5: Documentation drift check**

Confirm whether the implementation changed:

- user-visible behavior;
- critical shipment routes;
- roles or permissions;
- shipment readiness contracts;
- print/document contracts;
- data model/business rules;
- release/smoke expectations.

Docs update is required for this feature and is covered in Task 7.

**Step 6: Final status**

Report:

- changed files;
- tests run and results;
- documentation updated;
- remaining risks, especially print layout and manual browser checks;
- no commit was created unless explicitly approved.
