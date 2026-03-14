# Shipment Planning Portal Status Vocabulary Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harmonize visible status vocabulary and status badges across legacy Scan, Portal, and Planning while keeping Portal order status, ASF review status, and shipment status clearly separated.

**Architecture:** Add one shared legacy Django presentation helper for canonical visible status labels and Portal shipment-status projection. Rewire Scan shipment helpers, Portal order payloads/templates, Planning shipment summaries, and badge tone mappings to consume that shared presentation layer instead of scattering visible labels across templates and local helpers.

**Tech Stack:** Django views/templates, legacy WMS helpers, Django template tags, gettext/i18n, Django test runner

---

### Task 1: Add the shared status presentation layer

**Files:**
- Create: `wms/status_presenters.py`
- Create: `wms/tests/core/tests_status_presenters.py`
- Reference: `wms/models_domain/shipment.py`
- Reference: `wms/models_domain/portal.py`

**Step 1: Write the failing presenter tests**

Add tests for a single public presentation layer before creating it. Cover:
- canonical shipment labels:
  - `draft` -> `Brouillon`
  - `picking` -> `En cours`
  - `packed` -> `Disponible`
  - `planned` -> `Planifie`
  - `shipped` -> `Expedie`
  - `received_correspondent` -> `Recu escale`
  - `delivered` -> `Livre`
- canonical Portal order labels:
  - `reserved` -> `Reservee`
  - `preparing` -> `En preparation`
- canonical ASF review labels:
  - `approved` -> `Validee`
  - `changes_requested` -> `Modifications demandees`
- Portal shipment-status projection:
  - returns `-` when an order has no shipment
  - returns `Disponible` when the linked shipment status is `packed`

```python
from types import SimpleNamespace

from django.test import SimpleTestCase

from wms.status_presenters import (
    present_order_review_status,
    present_order_shipment_status,
    present_order_status,
    present_shipment_status,
)


class StatusPresentersTests(SimpleTestCase):
    def test_present_shipment_status_uses_disponible_for_packed(self):
        shipment = SimpleNamespace(status="packed", is_disputed=False)

        payload = present_shipment_status(shipment)

        self.assertEqual(payload["label"], "Disponible")
```

**Step 2: Run the new presenter test file and verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_status_presenters -v 2`

Expected: failure with `ModuleNotFoundError` or missing presenter functions.

**Step 3: Write the minimal shared presenter module**

Create `wms/status_presenters.py` with small, explicit helpers:
- `present_shipment_status(shipment_or_status, *, is_disputed=False)`
- `present_order_status(order_or_status)`
- `present_order_review_status(order_or_status)`
- `present_order_shipment_status(order)`

Return a dict payload with stable keys such as:
- `value`
- `label`
- `domain`
- `is_disputed`

```python
from django.utils.translation import gettext_lazy as _


SHIPMENT_LABELS = {
    "draft": _("Brouillon"),
    "picking": _("En cours"),
    "packed": _("Disponible"),
    "planned": _("Planifie"),
    "shipped": _("Expedie"),
    "received_correspondent": _("Recu escale"),
    "delivered": _("Livre"),
}


def present_shipment_status(shipment_or_status, *, is_disputed=False):
    status_value = getattr(shipment_or_status, "status", shipment_or_status)
    label = SHIPMENT_LABELS.get(status_value, status_value or "-")
    if is_disputed:
        label = _("Litige - %(label)s") % {"label": label}
    return {
        "value": status_value or "",
        "label": str(label),
        "domain": "shipment",
        "is_disputed": bool(is_disputed),
    }
```

Keep this module focused on visible presentation only. Do not move workflow logic into it.

**Step 4: Re-run the presenter tests**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_status_presenters -v 2`

Expected: PASS.

**Step 5: Commit the presenter layer**

```bash
git add wms/status_presenters.py wms/tests/core/tests_status_presenters.py
git commit -m "feat: add shared status presenters"
```

### Task 2: Align shipment labels and badge tones in Scan and Planning

**Files:**
- Modify: `wms/status_badges.py`
- Modify: `wms/shipment_view_helpers.py`
- Modify: `wms/planning/version_dashboard.py`
- Test: `wms/tests/core/tests_status_badges.py`
- Test: `wms/tests/shipment/tests_shipment_view_helpers.py`
- Test: `wms/tests/planning/tests_version_dashboard.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Add failing tests for canonical shipment wording and stronger tone separation**

Cover:
- Scan shipments-ready rows render `Disponible` instead of `Pret` for packed shipments.
- Planning shipment summary rows reuse `Disponible`.
- badge tone mapping differentiates:
  - `planned`
  - `shipped`
  - `received_correspondent`
  from the generic progress tone.

```python
def test_build_shipments_ready_rows_uses_disponible_label_for_packed(self):
    rows = build_shipments_ready_rows([packed_shipment])

    self.assertEqual(rows[0]["status_label"], "Disponible")
```

```python
def test_resolve_status_tone_distinguishes_core_shipment_states(self):
    self.assertNotEqual(resolve_status_tone("planned", domain="shipment"), "progress")
    self.assertNotEqual(resolve_status_tone("shipped", domain="shipment"), "progress")
    self.assertNotEqual(
        resolve_status_tone("received_correspondent", domain="shipment"),
        "progress",
    )
```

**Step 2: Run the focused shipment/planning/status suites and verify the new expectations fail**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_status_badges wms.tests.shipment.tests_shipment_view_helpers wms.tests.planning.tests_version_dashboard wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: failures because current helpers still render `Pret` and current badge tones keep several shipment states in the same progress family.

**Step 3: Rewire Scan and Planning to the shared presenter vocabulary**

Update:
- `wms/shipment_view_helpers.py`
  - replace local `Pret` wording with `present_shipment_status(...)`
  - keep the derived progress behavior, but emit canonical labels
- `wms/planning/version_dashboard.py`
  - use canonical shipment labels for shipment rows and summary rows sourced from shipment lifecycle data
- `wms/status_badges.py`
  - introduce distinct tones for `planned`, `shipped`, and `received_correspondent`

```python
from .status_presenters import present_shipment_status


def _shipment_status_label(shipment, progress_label):
    if shipment.status == ShipmentStatus.DRAFT:
        return present_shipment_status("draft")["label"]
    if shipment.status in STATUS_LOCKED_SHIPMENT:
        return present_shipment_status(
            shipment,
            is_disputed=getattr(shipment, "is_disputed", False),
        )["label"]
    if progress_label == _("Pret"):
        return present_shipment_status("packed")["label"]
    return progress_label
```

Use a minimal mapping in `wms/status_badges.py`, for example:
- `planned` -> `warning`
- `shipped` -> `progress`
- `received_correspondent` -> `ready`

If a new internal tone token is truly needed, add it deliberately and cover it with UI tests. Prefer reusing existing tone families unless the UI layer already supports more.

**Step 4: Re-run the focused shipment/planning/status suites**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_status_badges wms.tests.shipment.tests_shipment_view_helpers wms.tests.planning.tests_version_dashboard wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS.

**Step 5: Commit the Scan and Planning status alignment**

```bash
git add wms/status_badges.py wms/shipment_view_helpers.py wms/planning/version_dashboard.py \
  wms/tests/core/tests_status_badges.py wms/tests/shipment/tests_shipment_view_helpers.py \
  wms/tests/planning/tests_version_dashboard.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: align shipment status vocabulary"
```

### Task 3: Expose separate order, review, and shipment statuses in Portal

**Files:**
- Modify: `wms/views_portal_orders.py`
- Modify: `templates/portal/dashboard.html`
- Modify: `templates/portal/order_detail.html`
- Test: `wms/tests/views/tests_views_portal.py`
- Test: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Add failing Portal tests for the separated status model**

Cover:
- dashboard column headers show `Statut commande` and `Statut expedition`
- dashboard rows show:
  - canonical order-status label
  - canonical shipment-status label when shipment exists
  - `-` when shipment is absent
- order detail shows three separate visible fields:
  - `Statut commande`
  - `Validation ASF`
  - `Statut expedition`
- detail uses canonical review wording such as `Validee`

```python
def test_portal_dashboard_exposes_order_and_shipment_statuses(self):
    response = self.client.get(reverse("portal:portal_dashboard"))

    self.assertContains(response, "Statut commande")
    self.assertContains(response, "Statut expedition")
    self.assertContains(response, "Reservee")
    self.assertContains(response, "Disponible")
```

**Step 2: Run the focused Portal suites and verify they fail**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.views.tests_portal_bootstrap_ui -v 2`

Expected: failures because Portal still renders one generic `Statut` column and still uses the raw model-display wording for order review.

**Step 3: Build Portal payloads from the shared presenter layer**

Update `wms/views_portal_orders.py` so dashboard/detail context exposes explicit payloads:
- `order_status_display`
- `review_status_display`
- `shipment_status_display`

Use the shared presenter helpers instead of raw `get_status_display()` values for these visible fields.

```python
from .status_presenters import (
    present_order_review_status,
    present_order_shipment_status,
    present_order_status,
)


order_status_display = present_order_status(order)
review_status_display = present_order_review_status(order)
shipment_status_display = present_order_shipment_status(order)
```

Update:
- `templates/portal/dashboard.html`
  - rename the existing status column to `Statut commande`
  - add a new `Statut expedition` column
- `templates/portal/order_detail.html`
  - replace raw status lines with the three explicit labels

Keep document review tables and unrelated portal badges unchanged in this task.

**Step 4: Re-run the focused Portal suites**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.views.tests_portal_bootstrap_ui -v 2`

Expected: PASS.

**Step 5: Commit the Portal status split**

```bash
git add wms/views_portal_orders.py templates/portal/dashboard.html templates/portal/order_detail.html \
  wms/tests/views/tests_views_portal.py wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "feat: split portal order and shipment statuses"
```

### Task 4: Update translations and English rendering coverage

**Files:**
- Modify: `locale/en/LC_MESSAGES/django.po`
- Test: `wms/tests/views/tests_i18n_language_switch.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Add failing English-rendering assertions for the new wording**

Cover:
- Portal dashboard English page renders natural English labels for the new columns:
  - `Order status`
  - `Shipment status`
- Portal detail English page renders:
  - `Order status`
  - `ASF review`
  - `Shipment status`
- Scan shipment English page no longer exposes `Ready` if the chosen English term becomes `Available`

```python
def test_portal_dashboard_and_order_detail_render_new_status_labels_in_english(self):
    self._activate_english()
    self.client.force_login(self.portal_user)

    dashboard = self.client.get(reverse("portal:portal_dashboard"))
    self.assertContains(dashboard, "Order status")
    self.assertContains(dashboard, "Shipment status")
```

**Step 2: Run the i18n-focused suites and verify they fail**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch wms.tests.views.tests_views_scan_shipments -v 2`

Expected: failure because the new French source labels and canonical status wording are not yet translated in `locale/en/LC_MESSAGES/django.po`.

**Step 3: Update translation entries and compile messages**

Add or update English translations for the new visible labels and canonical wording in `locale/en/LC_MESSAGES/django.po`, including:
- `Statut commande`
- `Statut expedition`
- `Validation ASF`
- `Disponible`
- `Reservee`
- `En preparation`
- `Validee`
- `Modifications demandees`

Then run:

```bash
./.venv/bin/python manage.py compilemessages -v 1 --ignore='.venv' --ignore='.venv/*' --ignore='.worktrees' --ignore='.worktrees/*' --ignore='frontend-next' --ignore='frontend-next/*'
```

**Step 4: Re-run the i18n-focused suites**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_i18n_language_switch wms.tests.views.tests_views_scan_shipments -v 2`

Expected: PASS.

**Step 5: Commit the translation updates**

```bash
git add locale/en/LC_MESSAGES/django.po wms/tests/views/tests_i18n_language_switch.py \
  wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: translate harmonized status vocabulary"
```

### Task 5: Run the cross-surface regression suite and prepare the branch for review

**Files:**
- Verify only: `wms/status_presenters.py`
- Verify only: `wms/status_badges.py`
- Verify only: `wms/shipment_view_helpers.py`
- Verify only: `wms/views_portal_orders.py`
- Verify only: `wms/planning/version_dashboard.py`
- Verify only: `templates/portal/dashboard.html`
- Verify only: `templates/portal/order_detail.html`

**Step 1: Run the focused combined regression suite**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.core.tests_status_presenters \
  wms.tests.core.tests_status_badges \
  wms.tests.shipment.tests_shipment_view_helpers \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.views.tests_i18n_language_switch \
  wms.tests.planning.tests_version_dashboard -v 1
```

Expected: PASS.

**Step 2: Run a quick manual QA on the impacted pages**

Check:
- `/scan/shipments-ready/`
- `/portal/`
- `/portal/order/<id>/`
- Planning version detail page

Verify:
- `Disponible` is used consistently for shipment lifecycle
- Portal clearly separates order, review, and shipment statuses
- shipment badge tones are visually distinguishable

**Step 3: Inspect the diff before review**

Run:

```bash
git status --short
git diff --stat main...HEAD
```

Expected: only the planned status vocabulary files and tests are included.

**Step 4: Create the final branch commit if follow-up fixes were needed**

```bash
git add -A
git commit -m "feat: harmonize status vocabulary across shipment surfaces"
```

Only do this if the implementation required a final cleanup commit after the task commits above.

**Step 5: Prepare the PR**

```bash
git push -u origin codex/shipment-planning-portal-status-vocabulary
gh pr create --base main --head codex/shipment-planning-portal-status-vocabulary
```

Use a PR summary that calls out:
- shared status presenter layer
- Portal split between order status and shipment status
- `Disponible` as the canonical visible shipment wording
- Planning and Scan alignment on the same shipment vocabulary
