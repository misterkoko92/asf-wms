# Shipment Dossier Activity And Carton A4 Bundle Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add reliable dossier activity metadata, refresh the shipment dossier header layout, and add an A4 four-up grouped carton packing-list print mode while preserving the continuous-roll workflow.

**Architecture:** Persist the last dossier activity directly on `Shipment`, update it through the existing shipment handlers, and render it in the dossier header. Extend grouped print helpers and print views with a dedicated A4 carton-list bundle that reuses a shared carton packing-list partial.

**Tech Stack:** Django, legacy server-rendered templates, Django tests, print HTML templates

---

### Task 1: Document the approved design and implementation path

**Files:**
- Create: `docs/plans/2026-03-30-shipment-dossier-activity-and-carton-a4-bundle-design.md`
- Create: `docs/plans/2026-03-30-shipment-dossier-activity-and-carton-a4-bundle-implementation-plan.md`

**Step 1: Save the approved design**

Write the validated design summary, including persisted activity fields, action-row reorder, admin readability adjustment, and the new A4 carton bundle.

**Step 2: Save the implementation plan**

Write the plan with exact file paths, tests, and rollout order.

**Step 3: Verify files exist**

Run: `test -f docs/plans/2026-03-30-shipment-dossier-activity-and-carton-a4-bundle-design.md`

Expected: exit code `0`

**Step 4: Verify plan file exists**

Run: `test -f docs/plans/2026-03-30-shipment-dossier-activity-and-carton-a4-bundle-implementation-plan.md`

Expected: exit code `0`

### Task 2: Add failing shipment dossier tests

**Files:**
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/shipment/tests_shipment_view_helpers.py`

**Step 1: Write a failing dossier header test**

Cover:

- ordered primary actions
- separate close-action row
- rendered `Dernière MAJ` line and label

**Step 2: Write a failing helper test**

Cover:

- existing continuous-roll grouped action still present
- new A4 grouped carton action present in grouped print actions

**Step 3: Run the targeted tests to confirm failure**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments wms.tests.shipment.tests_shipment_view_helpers -v 2`

Expected: FAIL on the new assertions before implementation.

### Task 3: Add failing print bundle tests

**Files:**
- Modify: `wms/tests/views/tests_views_print_docs.py`

**Step 1: Write a failing shipment bundle test**

Cover the new shipment bundle key and assert:

- new bundle page title
- four-up printable surface
- carton codes rendered
- A4-specific layout markers

**Step 2: Run the targeted print-doc tests to confirm failure**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs -v 2`

Expected: FAIL because the new bundle key and template do not exist yet.

### Task 4: Implement persisted dossier activity

**Files:**
- Modify: `wms/models_domain/shipment.py`
- Create: `wms/migrations/0089_shipment_dossier_last_activity.py`
- Modify: `wms/scan_shipment_handlers.py`
- Modify: `wms/shipment_tracking_handlers.py`
- Modify: `wms/shipment_document_handlers.py`
- Modify: `wms/views_scan_shipments.py`

**Step 1: Add shipment fields**

Add:

- `dossier_last_activity_at = models.DateTimeField(null=True, blank=True)`
- `dossier_last_activity_label = models.CharField(max_length=120, blank=True)`

**Step 2: Add a small activity update helper**

Centralize assignment of both fields so handlers can call one function with a label.

**Step 3: Wire shipment edit activity**

Update the shipment edit handler to stamp `Dossier modifié` after a successful dossier update.

**Step 4: Wire tracking and dispute activity**

Update tracking/dispute handlers to stamp the appropriate label after each successful action.

**Step 5: Wire document and close activity**

Update document upload/delete and dossier close to stamp the appropriate label.

**Step 6: Run the targeted tests**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments wms.tests.shipment.tests_shipment_view_helpers -v 2`

Expected: PASS for activity-related assertions.

### Task 5: Refresh the dossier header and administrative card

**Files:**
- Modify: `templates/scan/includes/shipment_dossier_header.html`
- Modify: `templates/scan/includes/shipment_dossier_summary.html`
- Modify: `wms/views_scan_shipments.py`

**Step 1: Expose activity fields to the template**

Pass the persisted activity timestamp and label in the dossier context.

**Step 2: Reorder the primary buttons**

Render:

1. `Voir les colis`
2. `Modifier`
3. `Ouvrir suivi`
4. `Retour aux dossiers`

**Step 3: Move the close action to its own row**

Keep the existing state logic but place it on a second row using `btn btn-secondary`.

**Step 4: Render the new activity line**

Show `Dernière MAJ : <date> · <label>` beneath the creation line only when data exists.

**Step 5: Strengthen administrative labels**

Make the summary labels visually bold without changing the card structure.

**Step 6: Run the dossier tests**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS

### Task 6: Add the new grouped A4 carton-list bundle

**Files:**
- Modify: `wms/shipment_view_helpers.py`
- Modify: `wms/views_print_docs.py`
- Create: `templates/print/partials/packing_list_carton_body.html`
- Modify: `templates/print/liste_colisage_carton.html`
- Create: `templates/print/shipment_carton_lists_a4_four_up.html`

**Step 1: Extend grouped print actions**

Add a second grouped carton-list action label for the A4 four-up workflow.

**Step 2: Extract a shared carton packing-list body partial**

Reuse the same content for single-carton and grouped A4 output.

**Step 3: Add the new shipment bundle key**

Implement a new `bundle_key` in `wms/views_print_docs.py` that renders a printable A4 HTML surface.

**Step 4: Render four slots per page**

Group cartons in chunks of four and render each page with fixed-height label surfaces sized for 190 x 61 mm labels.

**Step 5: Preserve the continuous-roll bundle**

Leave `carton_lists` untouched except for shared helper reuse if needed.

**Step 6: Run the print-doc tests**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs -v 2`

Expected: PASS

### Task 7: Final verification and propagation check

**Files:**
- Review: `docs/repo-reference/03-impact-map.md`

**Step 1: Run the full targeted verification set**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments wms.tests.shipment.tests_shipment_view_helpers wms.tests.views.tests_views_print_docs wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS

**Step 2: Re-check print and shipment impact areas**

Confirm no additional repo-reference docs need updates beyond the saved plan/design docs.

**Step 3: Inspect the diff**

Run: `git diff -- docs/plans wms templates`

Expected: only the intended shipment dossier and print bundle changes.
