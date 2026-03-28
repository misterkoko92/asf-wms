# Shipment Note And Customs Layout Adjustments Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ajuster le bon d'expédition et le document douane pour appliquer le nouveau header, la suppression du footer, l'italique anglais et la nouvelle structure du bloc `Origine`.

**Architecture:** Les deux templates partagent une structure HTML/CSS parallèle avec des classes communes locales. Le footer est désactivé au niveau du contexte shipment pour éviter un masquage uniquement visuel. Les tests valident d'abord les nouveaux marqueurs de structure, puis le code est adapté au minimum pour les satisfaire.

**Tech Stack:** Django templates, CSS print, tests Django `TestCase`

---

### Task 1: Write failing tests for the new shipment note and customs contract

**Files:**
- Modify: `wms/tests/views/tests_print_strict_fidelity.py`
- Modify: `wms/tests/print/tests_print_context.py`

**Step 1: Write the failing test**

- Add assertions for:
  - `shipment_note` and `customs` rendering a dedicated header block
  - a primary and secondary routing block
  - italic English markers
  - no `print-footer`
  - `hide_footer` true for `shipment_note`

**Step 2: Run test to verify it fails**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_print_strict_fidelity wms.tests.print.tests_print_context -v 1
```

Expected: FAIL on missing structure markers and old footer contract.

### Task 2: Implement the minimal context change

**Files:**
- Modify: `wms/print_context.py`

**Step 1: Write minimal implementation**

- Force `hide_footer` to `True` for `shipment_note` and `customs` shipment contexts.
- Keep existing behaviour unchanged for the other print documents.

**Step 2: Run targeted tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.print.tests_print_context -v 1
```

Expected: PASS for the updated footer contract.

### Task 3: Implement the minimal template changes

**Files:**
- Modify: `templates/print/bon_expedition.html`
- Modify: `templates/print/attestation_douane.html`

**Step 1: Write minimal implementation**

- Add dedicated sheet header with logo + ASF block
- Add `.sheet-en` italics styling
- Split the routing block into primary and secondary sections
- Add highlighted values for the first 2 routing rows
- Align left-column widths across routing and party blocks

**Step 2: Run targeted tests**

Run:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_print_strict_fidelity wms.tests.views.tests_print_templates_rendering -v 1
```

Expected: PASS

### Task 4: Run broader verification

**Files:**
- No code changes

**Step 1: Run focused suites**

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_print_templates_rendering wms.tests.views.tests_views_print_docs wms.tests.views.tests_print_delivery wms.tests.views.tests_print_strict_fidelity -v 1
```

**Step 2: Run full coverage**

```bash
COVERAGE_FAIL_UNDER=93 TEST_PARALLEL=4 uv run make coverage
```

**Step 3: Commit**

```bash
git add docs/plans/2026-03-27-shipment-note-customs-layout-adjustments-design.md docs/plans/2026-03-27-shipment-note-customs-layout-adjustments-implementation-plan.md wms/print_context.py wms/tests/print/tests_print_context.py wms/tests/views/tests_print_strict_fidelity.py templates/print/bon_expedition.html templates/print/attestation_douane.html
git commit -m "feat: tune shipment note and customs print layout"
```
