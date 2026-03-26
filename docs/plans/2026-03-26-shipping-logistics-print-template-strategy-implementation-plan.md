# Shipping Logistics Print Template Strategy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the shipment logistics documents to code-managed source templates that print cleanly from desktop and mobile for internal use while still producing PDF output for external sharing.

**Architecture:** Treat Django HTML/CSS templates as the master source for the shipment logistics documents, with one optional SVG-backed exception for the shipment label if visual fidelity requires it. Keep context building in `wms/print_context.py`, render internal print surfaces directly in legacy Django views, and add PDF delivery as an adapter instead of using Excel as the source template format.

**Tech Stack:** Django views, Django templates, legacy print routes, Django tests

---

### Task 1: Add a shipment print strategy registry with failing tests

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/wms/print_document_strategy.py`
- Create: `/Users/EdouardGonnu/asf-wms/wms/tests/print/tests_print_document_strategy.py`

**Step 1: Write the failing test**

Add a new test module that codifies the validated policy for the seven shipment logistics documents.

Cover assertions such as:

```python
from wms.print_document_strategy import SHIPMENT_LOGISTICS_PRINT_STRATEGY

policy = SHIPMENT_LOGISTICS_PRINT_STRATEGY["donation_certificate"]
self.assertEqual(policy["source_format"], "html")
self.assertEqual(policy["fidelity_tier"], "locked")
self.assertTrue(policy["external_pdf_required"])
```

```python
label_policy = SHIPMENT_LOGISTICS_PRINT_STRATEGY["shipment_label"]
self.assertIn(label_policy["source_format"], {"html", "svg"})
self.assertEqual(label_policy["fidelity_tier"], "visual_identity")
```

```python
packing_policy = SHIPMENT_LOGISTICS_PRINT_STRATEGY["packing_list_carton"]
self.assertEqual(packing_policy["internal_delivery"], "browser_print")
self.assertTrue(packing_policy["external_pdf_required"])
```

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.print.tests_print_document_strategy -v 2
```

Expected:
- failure because the strategy module does not exist yet

**Step 3: Implement the minimal registry**

Create `/Users/EdouardGonnu/asf-wms/wms/print_document_strategy.py` with a simple registry such as:

```python
SHIPMENT_LOGISTICS_PRINT_STRATEGY = {
    "packing_list_carton": {
        "source_format": "html",
        "fidelity_tier": "flexible",
        "internal_delivery": "browser_print",
        "external_pdf_required": True,
    },
    "packing_list_shipment": {
        "source_format": "html",
        "fidelity_tier": "flexible",
        "internal_delivery": "browser_print",
        "external_pdf_required": True,
    },
    "shipment_note": {
        "source_format": "html",
        "fidelity_tier": "flexible",
        "internal_delivery": "browser_print",
        "external_pdf_required": True,
    },
    "customs": {
        "source_format": "html",
        "fidelity_tier": "flexible",
        "internal_delivery": "browser_print",
        "external_pdf_required": True,
    },
    "donation_certificate": {
        "source_format": "html",
        "fidelity_tier": "locked",
        "internal_delivery": "browser_print",
        "external_pdf_required": True,
    },
    "contact_label": {
        "source_format": "html",
        "fidelity_tier": "flexible",
        "internal_delivery": "browser_print",
        "external_pdf_required": True,
    },
    "shipment_label": {
        "source_format": "svg",
        "fidelity_tier": "visual_identity",
        "internal_delivery": "browser_print",
        "external_pdf_required": False,
    },
}
```

Do not add business logic in this first task. Keep it declarative.

**Step 4: Run test to verify it passes**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.print.tests_print_document_strategy -v 2
```

Expected:
- the new strategy-policy tests pass

**Step 5: Commit**

```bash
git add wms/print_document_strategy.py wms/tests/print/tests_print_document_strategy.py
git commit -m "feat: add shipment print strategy registry"
```

### Task 2: Introduce shared internal print surfaces for document and label templates

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/templates/print/base_document.html`
- Create: `/Users/EdouardGonnu/asf-wms/templates/print/base_label.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/print/bon_expedition.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/print/liste_colisage_lot.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/print/liste_colisage_carton.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/print/attestation_douane.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/print/attestation_donation.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/print/etiquette_expedition.html`
- Create: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_print_templates_rendering.py`

**Step 1: Write the failing rendering test**

Add focused rendering tests that assert the existing shipment logistics templates render through shared bases without the A5-only assumptions of `base_a5.html`.

For example:

```python
response = self.client.get(reverse("scan:scan_shipment_document", args=[shipment.id, "shipment_note"]))
self.assertContains(response, 'data-print-surface="document"')
```

```python
response = self.client.get(reverse("scan:scan_shipment_labels", args=[shipment.id]))
self.assertContains(response, 'data-print-surface="label"')
```

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_print_templates_rendering -v 2
```

Expected:
- failure because the new shared base templates do not exist yet

**Step 3: Implement the minimal shared bases**

Create `/Users/EdouardGonnu/asf-wms/templates/print/base_document.html` with:

```html
<!doctype html>
<html lang="{{ LANGUAGE_CODE|default:'fr' }}">
<head>
  <meta charset="utf-8">
  <title>{% block title %}Document{% endblock %}</title>
  <style>
    @page { margin: 10mm; }
    body { margin: 0; font-family: Arial, sans-serif; color: #000; }
  </style>
  {% block extra_style %}{% endblock %}
</head>
<body data-print-surface="document">
  {% block body %}{% endblock %}
</body>
</html>
```

Create `/Users/EdouardGonnu/asf-wms/templates/print/base_label.html` with:

```html
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{% block title %}Label{% endblock %}</title>
  <style>
    @page { margin: 0; }
    body { margin: 0; font-family: Arial, sans-serif; color: #000; }
  </style>
  {% block extra_style %}{% endblock %}
</head>
<body data-print-surface="label">
  {% block body %}{% endblock %}
</body>
</html>
```

Then move the shipment logistics templates onto these bases instead of `base_a5.html`, keeping business content unchanged for now.

**Step 4: Run tests to verify they pass**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_print_templates_rendering -v 2
```

Expected:
- the new shared-base assertions pass

**Step 5: Commit**

```bash
git add templates/print/base_document.html templates/print/base_label.html templates/print/bon_expedition.html templates/print/liste_colisage_lot.html templates/print/liste_colisage_carton.html templates/print/attestation_douane.html templates/print/attestation_donation.html templates/print/etiquette_expedition.html wms/tests/views/tests_print_templates_rendering.py
git commit -m "feat: add shared shipment print surfaces"
```

### Task 3: Migrate the flexible shipment documents to direct HTML/CSS source templates

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/templates/print/bon_expedition.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/print/liste_colisage_lot.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/print/liste_colisage_carton.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/print/attestation_douane.html`
- Create: `/Users/EdouardGonnu/asf-wms/templates/print/feuille_contact.html`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/shipment_view_helpers.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/print_context.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/tests/print/tests_print_context.py`

**Step 1: Write failing tests for the new flexible-template routes**

Add tests that assert:
- shipment note still renders the expected shipment data
- packing list shipment and carton still render rows and summaries
- customs still renders the same business payload
- contact sheet gets a dedicated template instead of depending on the Excel/pack flow

Example:

```python
response = self.client.get(
    reverse("scan:scan_shipment_view_document", kwargs={"shipment_id": shipment.id, "document_key": "contact"})
)
self.assertContains(response, "EXPEDITEUR")
self.assertContains(response, "DESTINATAIRE")
```

**Step 2: Run tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs wms.tests.print.tests_print_context -v 2
```

Expected:
- failure because the new contact-sheet path and flexible-template assumptions are not fully wired

**Step 3: Implement the minimal direct-template path**

In `/Users/EdouardGonnu/asf-wms/wms/shipment_view_helpers.py`, extend:

```python
SHIPMENT_DOCUMENT_TEMPLATES = {
    "donation_certificate": "print/attestation_donation.html",
    "customs": "print/attestation_douane.html",
    "shipment_note": "print/bon_expedition.html",
    "packing_list_shipment": "print/liste_colisage_lot.html",
    "contact_label": "print/feuille_contact.html",
}
```

In `/Users/EdouardGonnu/asf-wms/wms/print_context.py`, add a narrow helper for the contact-sheet context, reusing the existing party information builders.

In `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`, add a route path for the contact document that can render directly from HTML/CSS instead of requiring Excel output.

Do not remove the existing pack routes in this task. Only add or reroute the HTML/CSS path for the flexible documents.

**Step 4: Run targeted tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_views_print_docs wms.tests.print.tests_print_context -v 2
```

Expected:
- the flexible-document tests pass
- no existing shipment document regressions appear

**Step 5: Commit**

```bash
git add templates/print/bon_expedition.html templates/print/liste_colisage_lot.html templates/print/liste_colisage_carton.html templates/print/attestation_douane.html templates/print/feuille_contact.html wms/shipment_view_helpers.py wms/views_print_docs.py wms/print_context.py wms/tests/views/tests_views_print_docs.py wms/tests/print/tests_print_context.py
git commit -m "feat: migrate flexible shipment docs to html source templates"
```

### Task 4: Lock down the strict-fidelity documents

**Files:**
- Modify: `/Users/EdouardGonnu/asf-wms/templates/print/attestation_donation.html`
- Modify: `/Users/EdouardGonnu/asf-wms/templates/print/etiquette_expedition.html`
- Optional Create: `/Users/EdouardGonnu/asf-wms/templates/print/partials/shipment_label_visual.svg`
- Create: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_print_strict_fidelity.py`

**Step 1: Write the failing strict-fidelity tests**

For the donation certificate, assert the exact required wording remains present:

```python
self.assertContains(response, "ATTESTATION DE DONATION")
self.assertContains(response, "Valeur uniquement pour la douane : 1.00 euro")
```

For the shipment label, assert the preserved structure:

```python
self.assertContains(response, 'id="shipment-label-city"')
self.assertContains(response, 'id="shipment-label-iata"')
self.assertContains(response, 'id="shipment-label-footer"')
```

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_print_strict_fidelity -v 2
```

Expected:
- failure because the strict-fidelity coverage does not exist yet

**Step 3: Implement the minimal fidelity locks**

Keep `/Users/EdouardGonnu/asf-wms/templates/print/attestation_donation.html` close to its current wording and layout. Add stable IDs around the critical sections so tests can lock the structure.

For the shipment label, choose one implementation:
- keep HTML/CSS and add stable IDs plus constrained styling
- or embed a reusable SVG partial if that better preserves the current visual identity

Do not redesign these two documents in this task. Preserve them first.

**Step 4: Run tests to verify they pass**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_print_strict_fidelity -v 2
```

Expected:
- strict-fidelity tests pass

**Step 5: Commit**

```bash
git add templates/print/attestation_donation.html templates/print/etiquette_expedition.html templates/print/partials/shipment_label_visual.svg wms/tests/views/tests_print_strict_fidelity.py
git commit -m "test: lock shipment strict-fidelity print docs"
```

### Task 5: Add PDF as an external delivery adapter

**Files:**
- Create: `/Users/EdouardGonnu/asf-wms/wms/print_delivery.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`
- Modify: `/Users/EdouardGonnu/asf-wms/wms/shipment_view_helpers.py`
- Create: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_print_delivery.py`

**Step 1: Write the failing delivery tests**

Add tests that codify:
- internal default response renders HTML
- external PDF can be requested explicitly

Example:

```python
response = self.client.get(
    reverse("scan:scan_shipment_document", kwargs={"shipment_id": shipment.id, "doc_type": "shipment_note"}),
    {"delivery": "pdf"},
)
self.assertEqual(response["Content-Type"], "application/pdf")
```

And:

```python
response = self.client.get(
    reverse("scan:scan_shipment_document", kwargs={"shipment_id": shipment.id, "doc_type": "shipment_note"})
)
self.assertContains(response, 'data-print-surface="document"')
```

**Step 2: Run tests to verify they fail**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_print_delivery -v 2
```

Expected:
- failure because the external delivery adapter does not exist yet

**Step 3: Implement the minimal delivery adapter**

Create `/Users/EdouardGonnu/asf-wms/wms/print_delivery.py` with a small interface such as:

```python
def delivery_mode(request):
    return (request.GET.get("delivery") or "").strip().lower() or "html"
```

```python
def wants_external_pdf(request):
    return delivery_mode(request) == "pdf"
```

Then in `/Users/EdouardGonnu/asf-wms/wms/views_print_docs.py`, branch between:
- HTML render for internal print-first flows
- PDF render for explicit external delivery

If a production PDF renderer is not yet selected, stub the integration behind one function boundary and cover it with mocks in the tests.

**Step 4: Run targeted tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_print_delivery wms.tests.views.tests_views_print_docs -v 2
```

Expected:
- delivery-mode tests pass
- legacy print routes still behave correctly

**Step 5: Commit**

```bash
git add wms/print_delivery.py wms/views_print_docs.py wms/shipment_view_helpers.py wms/tests/views/tests_print_delivery.py
git commit -m "feat: add external pdf delivery adapter"
```

### Task 6: Final verification and cleanup

**Files:**
- Modify: none
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/print/tests_print_document_strategy.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_print_templates_rendering.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_views_print_docs.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_print_strict_fidelity.py`
- Test: `/Users/EdouardGonnu/asf-wms/wms/tests/views/tests_print_delivery.py`

**Step 1: Run the full targeted verification set**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.print.tests_print_document_strategy wms.tests.views.tests_print_templates_rendering wms.tests.views.tests_views_print_docs wms.tests.views.tests_print_strict_fidelity wms.tests.views.tests_print_delivery -v 1
git diff --check
git status --short --branch
```

Expected:
- targeted tests pass
- no diff hygiene issues
- only the intended shipment-print files changed

**Step 2: Manual verification**

Check on desktop and mobile that:
- the flexible documents print cleanly from the browser
- the donation certificate still reads and looks nearly identical
- the shipment label still matches the current visual identity
- explicit PDF delivery works for external sharing

**Step 3: Commit**

```bash
git add -A
git commit -m "docs: finalize shipment logistics print template migration"
```

**Step 4: Stop before removing Excel fallbacks**

Do not delete the Excel print-pack path in the same execution batch. Only remove old fallbacks after the HTML/CSS source path and external PDF adapter are proven on real operational documents.
