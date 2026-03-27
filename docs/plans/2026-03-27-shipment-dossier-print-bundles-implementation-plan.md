# Shipment Dossier Print Bundles Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn `Expéditions > Dossiers` into the main shipment-print cockpit, with grouped internal print actions by physical support, carton-level reprints, and explicit PDF exports for external sharing.

**Architecture:** Keep the legacy Django stack. Replace the creation-era document panel inside the dossier with a dossier-specific panel backed by explicit print-action groups. Reuse existing shipment print routes where they already fit, add missing HTML-first routes for grouped bundles and carton-level label documents, and keep PDF as an explicit export layer rather than the default internal interaction.

**Tech Stack:** Django views, Django templates, legacy scan routes, shipment print helpers, Django tests

---

### Task 1: Add a dossier-specific print action contract and panel skeleton

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/templates/scan/includes/shipment_dossier_documents_panel.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/scan/shipment_dossier.html`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/shipment_view_helpers.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_scan_shipments.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/shipment/tests_shipment_view_helpers.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_scan_shipments.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views.py`

**Step 1: Write the failing tests**

Add helper and dossier-page assertions that lock the new UI contract:

```python
actions = build_shipment_dossier_print_actions(shipment)

self.assertEqual(
    [item["label"] for item in actions["grouped_print_actions"]],
    [
        "Imprimer tous les documents d'expédition",
        "Imprimer dossier papier",
        "Imprimer toutes les listes colisage carton",
        "Imprimer toutes les étiquettes standard",
    ],
)
```

```python
response = self.client.get(reverse("scan:scan_shipment_edit", args=[shipment.id]))

self.assertContains(response, "Imprimer tous les documents d'expédition")
self.assertContains(response, "Documents papier")
self.assertContains(response, "Par colis")
self.assertContains(response, "Exports PDF")
self.assertNotContains(response, "Documents générés")
self.assertNotContains(response, "Feuille contact")
```

Also assert the carton-row action labels:

```python
self.assertContains(response, "Liste colisage")
self.assertContains(response, "Étiquette colis")
self.assertContains(response, "Étiquette contact")
self.assertContains(response, "Attestation donation")
```

**Step 2: Run tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.shipment.tests_shipment_view_helpers \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_views \
  -v 2
```

Expected:
- failure because the dossier still renders `shipment_create_generated_documents_panel.html`
- failure because no dossier-specific action contract exists yet

**Step 3: Implement the minimal action contract and panel**

In `/Users/EdouardGonnu/asf-wms/wms/shipment_view_helpers.py`, add a dedicated builder such as:

```python
def build_shipment_dossier_print_actions(shipment):
    return {
        "grouped_print_actions": [...],
        "paper_print_actions": [...],
        "carton_print_rows": [...],
        "pdf_export_actions": [...],
    }
```

Use the current shipment/carton order by `code`. Keep the builder declarative and URL-focused.

Then:
- create `/Users/EdouardGonnu/asf-wms/templates/scan/includes/shipment_dossier_documents_panel.html`
- switch `/Users/EdouardGonnu/asf-wms/templates/scan/shipment_dossier.html` to include that new partial instead of the creation-era generated-documents panel
- expose the action payload from `/Users/EdouardGonnu/asf-wms/wms/views_scan_shipments.py`

At this stage, it is acceptable for some URLs to target route skeletons that will be filled in the next tasks, as long as the dossier contract is stable.

**Step 4: Run tests to verify they pass**

Run the same command.

Expected:
- dossier helper tests pass
- dossier template tests pass

**Step 5: Commit**

```bash
git add templates/scan/includes/shipment_dossier_documents_panel.html templates/scan/shipment_dossier.html wms/shipment_view_helpers.py wms/views_scan_shipments.py wms/tests/shipment/tests_shipment_view_helpers.py wms/tests/views/tests_views_scan_shipments.py wms/tests/views/tests_views.py
git commit -m "feat: add shipment dossier print action panel"
```

### Task 2: Add HTML-first paper print surfaces and the paper bundle route

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/scan_urls.py`
- Create: `/Users/EdouardGonnu/asf-wms/templates/print/shipment_paper_bundle.html`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_print_delivery.py`

**Step 1: Write the failing tests**

Add view tests that assert:
- `scan_shipment_view_document` renders HTML directly for:
  - `shipment_note`
  - `customs`
  - `packing_list`
- a new HTML bundle route renders the paper lot

Example:

```python
response = self.client.get(
    reverse("scan:scan_shipment_view_document", kwargs={"shipment_id": shipment.id, "document_key": "shipment_note"})
)
self.assertContains(response, 'data-print-surface="document"')
```

```python
response = self.client.get(
    reverse("scan:scan_shipment_view_bundle", kwargs={"shipment_id": shipment.id, "bundle_key": "paper"})
)
self.assertContains(response, 'id="shipment-paper-bundle"')
self.assertContains(response, "Bon d'expédition")
self.assertContains(response, "Document douane")
self.assertContains(response, "Liste générale")
```

Also lock delivery behavior:

```python
self.assertTrue(response["Content-Type"].startswith("text/html"))
```

**Step 2: Run tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_print_docs \
  wms.tests.views.tests_print_delivery \
  -v 2
```

Expected:
- failure because no HTML bundle route exists yet
- failure because the view-document path still falls back to the XLSX/PDF pipeline for these keys

**Step 3: Implement the minimal paper surfaces**

In `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`:
- keep `scan_shipment_view_document` as the dossier-facing document route
- render `shipment_note`, `customs`, and `packing_list` directly through HTML templates
- add a new route handler such as `scan_shipment_view_bundle` for `bundle_key == "paper"`

In `/Users/EdouardGonnu/asf-wms/templates/print/shipment_paper_bundle.html`:
- render the three paper documents in order
- use explicit anchors / wrappers so tests can assert the bundle structure
- keep it browser-print-friendly

Expose the new route through:
- `/Users/EdouardGonnu/asf-wms/wms/scan_urls.py`
- `/Users/EdouardGonnu/asf-wms/wms/views.py`
- `/Users/EdouardGonnu/asf-wms/wms/views_print.py`

Do not remove the existing PDF bundle route in this task.

**Step 4: Run tests to verify they pass**

Run the same command.

Expected:
- HTML paper-document assertions pass
- the new paper-bundle route passes

**Step 5: Commit**

```bash
git add wms/views_print_docs.py wms/views_print.py wms/views.py wms/scan_urls.py templates/print/shipment_paper_bundle.html wms/tests/views/tests_views_print_docs.py wms/tests/views/tests_print_delivery.py
git commit -m "feat: add html-first shipment paper print bundle"
```

### Task 3: Replace the contact sheet with a per-carton contact label and add carton-level donation routes

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/print_context.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/shipment_view_helpers.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_labels.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/scan_urls.py`
- Create: `/Users/EdouardGonnu/asf-wms/templates/print/etiquette_contact.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/print/attestation_donation.html`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/print/tests_print_context.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_labels.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_print_strict_fidelity.py`

**Step 1: Write the failing tests**

Add print-context tests for a carton-scoped contact label payload:

```python
context = build_carton_contact_label_context(shipment, carton)

self.assertEqual(context["shipment_ref"], shipment.reference)
self.assertEqual(context["carton_code"], carton.code)
self.assertIn("shipper_info", context)
self.assertIn("recipient_info", context)
```

Add route tests for:
- `scan_shipment_contact_label`
- `scan_shipment_donation_certificate`

Example:

```python
response = self.client.get(
    reverse("scan:scan_shipment_contact_label", kwargs={"shipment_id": shipment.id, "carton_id": carton.id})
)
self.assertContains(response, 'id="contact-label"')
self.assertContains(response, carton.code)
```

```python
response = self.client.get(
    reverse("scan:scan_shipment_donation_certificate", kwargs={"shipment_id": shipment.id, "carton_id": carton.id})
)
self.assertContains(response, 'id="donation-certificate-title"')
self.assertContains(response, "ATTESTATION DE DONATION")
```

Keep the existing strict-fidelity assertions for the donation wording and stable template anchors.

**Step 2: Run tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.print.tests_print_context \
  wms.tests.views.tests_views_print_docs \
  wms.tests.views.tests_views_print_labels \
  wms.tests.views.tests_print_strict_fidelity \
  -v 2
```

Expected:
- failure because there is no carton-level contact-label context or route
- failure because donation is not yet exposed as a carton-level HTML print action

**Step 3: Implement the minimal carton-level label/certificate surfaces**

In `/Users/EdouardGonnu/asf-wms/wms/print_context.py`:
- add a narrow `build_carton_contact_label_context(shipment, carton)` helper
- if needed, add a carton-aware donation helper that reuses the locked shipment data while surfacing carton metadata

Create `/Users/EdouardGonnu/asf-wms/templates/print/etiquette_contact.html` as a dedicated print label.

Then add carton-level routes and render helpers for:
- contact label
- donation certificate

Keep the donation template locked:
- preserve the required wording
- preserve the stable DOM anchors already asserted in tests

**Step 4: Run tests to verify they pass**

Run the same command.

Expected:
- carton-level contact label renders cleanly
- carton-level donation route passes
- strict donation fidelity tests remain green

**Step 5: Commit**

```bash
git add wms/print_context.py wms/shipment_view_helpers.py wms/views_print_docs.py wms/views_print_labels.py wms/views.py wms/scan_urls.py templates/print/etiquette_contact.html templates/print/attestation_donation.html wms/tests/print/tests_print_context.py wms/tests/views/tests_views_print_docs.py wms/tests/views/tests_views_print_labels.py wms/tests/views/tests_print_strict_fidelity.py
git commit -m "feat: add carton contact and donation print surfaces"
```

### Task 4: Add grouped carton-list and standard-label bundles plus the global orchestrator page

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_labels.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/scan_urls.py`
- Create: `/Users/EdouardGonnu/asf-wms/templates/print/shipment_carton_lists_bundle.html`
- Create: `/Users/EdouardGonnu/asf-wms/templates/print/shipment_standard_labels_bundle.html`
- Create: `/Users/EdouardGonnu/asf-wms/templates/scan/shipment_print_bundle.html`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_labels.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing tests**

Add tests for:
- `scan_shipment_view_bundle(..., bundle_key="carton_lists")`
- `scan_shipment_view_bundle(..., bundle_key="standard_labels")`
- `scan_shipment_view_bundle(..., bundle_key="all")`

Lock the expected order:

```python
response = self.client.get(
    reverse("scan:scan_shipment_view_bundle", kwargs={"shipment_id": shipment.id, "bundle_key": "standard_labels"})
)
content = response.content.decode()
self.assertLess(content.index("Étiquette colis"), content.index("Étiquette contact"))
self.assertLess(content.index("Étiquette contact"), content.index("Attestation donation"))
```

Lock the orchestrator-page structure:

```python
self.assertContains(response, 'id="shipment-print-bundle"')
self.assertContains(response, "Lot papier A4")
self.assertContains(response, "Lot rouleau continu")
self.assertContains(response, "Lot étiquettes standard")
```

**Step 2: Run tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_print_docs \
  wms.tests.views.tests_views_print_labels \
  wms.tests.views.tests_views_scan_shipments \
  -v 2
```

Expected:
- failure because these bundle routes and templates do not exist yet

**Step 3: Implement the grouped bundles**

Add three HTML bundle surfaces:

- `/Users/EdouardGonnu/asf-wms/templates/print/shipment_carton_lists_bundle.html`
  - one carton packing list per carton
- `/Users/EdouardGonnu/asf-wms/templates/print/shipment_standard_labels_bundle.html`
  - for each carton, in order:
    - shipment label
    - contact label
    - donation certificate
- `/Users/EdouardGonnu/asf-wms/templates/scan/shipment_print_bundle.html`
  - orchestrator page with the three lots and clear `Imprimer ce lot` actions

In the view layer:
- make `bundle_key == "all"` render the orchestrator page, not a fake single print artifact
- make `bundle_key == "carton_lists"` and `bundle_key == "standard_labels"` render HTML bundle pages

Keep the global flow explicit:
- browser-driven
- mobile-safe
- no silent print assumptions

**Step 4: Run tests to verify they pass**

Run the same command.

Expected:
- bundle pages render in the validated order
- dossier-linked grouped actions now point to working HTML surfaces

**Step 5: Commit**

```bash
git add wms/views_print_docs.py wms/views_print_labels.py wms/views.py wms/scan_urls.py templates/print/shipment_carton_lists_bundle.html templates/print/shipment_standard_labels_bundle.html templates/scan/shipment_print_bundle.html wms/tests/views/tests_views_print_docs.py wms/tests/views/tests_views_print_labels.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: add shipment print bundle surfaces"
```

### Task 5: Add explicit PDF exports and restrict helper interception to PDF actions only

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/wms/shipment_view_helpers.py`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/scan/includes/shipment_dossier_documents_panel.html`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_print_delivery.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`

**Step 1: Write the failing tests**

Lock the final helper-scoping rule on the dossier page:

```python
response = self.client.get(reverse("scan:scan_shipment_edit", args=[shipment.id]))

self.assertContains(
    response,
    'href="/scan/shipment/.../view-bundle-pdf/..." data-local-document-helper-link="1"',
)
self.assertNotContains(
    response,
    'Imprimer dossier papier" target="_blank" rel="noopener" data-local-document-helper-link="1"',
)
```

Also add PDF export assertions such as:

```python
response = self.client.get(
    reverse("scan:scan_shipment_view_bundle_pdf", kwargs={"shipment_id": shipment.id, "bundle_key": "a4"})
)
self.assertTrue(response["Content-Type"].startswith("application/pdf"))
```

The explicit dossier actions should include:
- `Télécharger dossier papier (PDF)`
- `Télécharger bon d'expédition (PDF)`
- `Télécharger document douane (PDF)`
- `Télécharger liste générale (PDF)`
- `Télécharger attestation donation (PDF)` when available

**Step 2: Run tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views \
  wms.tests.views.tests_print_delivery \
  wms.tests.views.tests_views_print_docs \
  -v 2
```

Expected:
- failure because helper interception still sits on the old dossier links
- failure because the new PDF export block is not wired yet

**Step 3: Implement explicit exports and helper scoping**

In `/Users/EdouardGonnu/asf-wms/wms/shipment_view_helpers.py`:
- build PDF export actions separately from internal print actions
- reuse the existing explicit PDF endpoints where possible:
  - `scan_shipment_view_bundle_pdf` for the paper bundle
  - legacy direct routes with `?delivery=pdf` for individual exports

In `/Users/EdouardGonnu/asf-wms/templates/scan/includes/shipment_dossier_documents_panel.html`:
- attach `data-local-document-helper-link="1"` only to PDF export actions
- keep internal `Imprimer ...` actions as normal browser-print links

Do not change the legacy compatibility routes in this task beyond what is required to serve explicit PDF export actions.

**Step 4: Run tests to verify they pass**

Run the same command.

Expected:
- only PDF links are helper-intercepted
- HTML print buttons are browser-native
- explicit PDF exports pass

**Step 5: Commit**

```bash
git add wms/shipment_view_helpers.py templates/scan/includes/shipment_dossier_documents_panel.html wms/tests/views/tests_views.py wms/tests/views/tests_print_delivery.py wms/tests/views/tests_views_print_docs.py
git commit -m "feat: scope shipment helper flows to explicit pdf exports"
```

## Final Verification

Run the focused suite:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.shipment.tests_shipment_view_helpers \
  wms.tests.print.tests_print_context \
  wms.tests.views.tests_print_delivery \
  wms.tests.views.tests_print_strict_fidelity \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_views_print_docs \
  wms.tests.views.tests_views_print_labels \
  wms.tests.views.tests_views \
  -v 1
```

Then run:

```bash
git diff --check
```

## Expected Outcome

When the plan is complete:
- `Expéditions > Dossiers` is the primary shipment-print cockpit
- the dossier uses a dedicated document panel instead of the creation-era panel
- internal print actions are grouped by support
- the global print button orchestrates multiple lots instead of hiding support differences
- carton-level reprints are available for carton packing list, shipment label, contact label, and donation certificate
- explicit PDF exports remain available for external sharing
- helper interception is limited to explicit PDF actions
