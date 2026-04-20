# Preparateur Home And Carton Activity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dedicated preparateur home with bénévole selection, order recommendation, historical “last carton” lookup, durable carton edit tracing, and the updated preparateur success modal.

**Architecture:** Keep the legacy Django scan stack and current preparateur-specific screens, but add one preparateur home view plus small helper modules for session binding, order recommendation, and carton activity logging. Reuse existing carton preparation and order preparation services by threading the selected bénévole identity through them instead of building a parallel workflow.

**Tech Stack:** Django views/templates/models, legacy scan static JS, Django session state, Django test suite via `./.venv/bin/python manage.py test`

---

### Task 1: Lock The Preparateur Home Entry Contract

**Files:**
- Create: `wms/tests/views/tests_views_scan_preparateur.py`
- Modify: `wms/views_scan_dashboard.py`
- Modify: `wms/scan_permissions.py`
- Modify: `wms/scan_urls.py`
- Modify: `wms/views_scan.py`
- Modify: `wms/views.py`

**Step 1: Write the failing test**

Add view coverage for:

- `/scan/` redirecting preparateur users to the new home instead of `scan_pack`
- the new home returning `200`
- home actions staying disabled when no bénévole is selected
- the whitelist still blocking dashboard / broad shipment lists for preparateur users

Example:

```python
response = self.client.get(reverse("scan:scan_root"))
self.assertRedirects(response, reverse("scan:scan_preparateur_home"))

home = self.client.get(reverse("scan:scan_preparateur_home"))
self.assertContains(home, "Choisir un bénévole")
self.assertContains(home, "Préparer une commande")
self.assertContains(home, "Préparer des colis non affectés")
self.assertContains(home, "disabled")
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_preparateur -v 2
```

Expected:
- FAIL because the preparateur home route and redirect do not exist yet

**Step 3: Write minimal implementation**

Implement:

- a new preparateur home route and view
- the `scan_root()` redirect change
- the minimal whitelist updates required to reach the new page
- temporary template rendering sufficient to satisfy the new entry contract

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_scan_preparateur.py wms/views_scan_dashboard.py wms/scan_permissions.py wms/scan_urls.py wms/views_scan.py wms/views.py
git commit -m "feat: add preparateur home entry route"
```

### Task 2: Bind The Active Bénévole In Session And Shell

**Files:**
- Create: `wms/preparateur_session.py`
- Create: `templates/scan/preparateur_home.html`
- Modify: `wms/view_permissions.py`
- Modify: `templates/scan/base.html`
- Modify: `templates/scan/includes/scan_sidebar_navigation.html`
- Modify: `wms/tests/views/tests_views_scan_preparateur.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Extend coverage for:

- bénévole selector labels rendered as `Martin DUPOND`
- selector sorted by surname A-Z
- posting the selector storing the bénévole in session
- `Bonjour Martin` appearing on allowed preparateur pages after selection

Example:

```python
self.assertContains(response, "Martin DUPOND")
self.assertContains(response, "Claire ZOLA")

response = self.client.post(
    reverse("scan:scan_preparateur_home"),
    {"action": "set_active_volunteer", "volunteer_id": volunteer.id},
)
self.assertRedirects(response, reverse("scan:scan_preparateur_home"))

followup = self.client.get(reverse("scan:scan_pack"))
self.assertContains(followup, "Bonjour Martin")
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_preparateur \
  wms.tests.views.tests_views_scan_shipments.ScanShipmentViewsTests \
  -v 2
```

Expected:
- FAIL because the session binder and shell greeting do not exist yet

**Step 3: Write minimal implementation**

Implement:

- session helpers for reading/writing the active `VolunteerProfile`
- request binding in the scan permission wrapper
- the dedicated home template with the selector form
- shell/header rendering for `Bonjour <first_name>`
- reduced preparateur navigation that still highlights correctly

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add wms/preparateur_session.py templates/scan/preparateur_home.html wms/view_permissions.py templates/scan/base.html templates/scan/includes/scan_sidebar_navigation.html wms/tests/views/tests_views_scan_preparateur.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: bind active volunteer in preparateur shell"
```

### Task 3: Lock The Order Recommendation Contract

**Files:**
- Create: `wms/preparateur_home_queries.py`
- Modify: `wms/tests/views/tests_views_scan_preparateur.py`
- Modify: `templates/scan/preparateur_home.html`
- Modify: `wms/views_scan_preparateur.py`

**Step 1: Write the failing test**

Add tests for:

- home order selector rendering two optgroups:
  - `Les 3 commandes les plus critiques`
  - `Toutes les commandes`
- the default selected order being the most critical realizable one
- the second group being sorted by shipper name A-Z
- non-realizable approved orders being excluded from both groups

Example:

```python
self.assertContains(response, "Les 3 commandes les plus critiques")
self.assertContains(response, "Toutes les commandes")
self.assertContains(response, '<option value="%s" selected' % critical_order.id, html=True)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_preparateur -v 2
```

Expected:
- FAIL because the home page does not build grouped realizable-order choices yet

**Step 3: Write minimal implementation**

In `wms/preparateur_home_queries.py`:

- compute advisory realizability without mutating reservations
- treat `RESERVED` and `PREPARING` as realizable
- rank critical orders by requested date, then creation date, then id
- expose grouped choice payloads plus the default selected order

In the home view/template:

- render the grouped selector
- wire the primary CTA to the existing order-preparation action
- keep the CTA disabled when no realizable order exists

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add wms/preparateur_home_queries.py wms/tests/views/tests_views_scan_preparateur.py templates/scan/preparateur_home.html wms/views_scan_preparateur.py
git commit -m "feat: add preparateur order recommendation selector"
```

### Task 4: Add The Carton Volunteer Activity Model And Last-Carton Helper

**Files:**
- Create: `wms/carton_activity.py`
- Create: `wms/tests/shipment/tests_carton_volunteer_activity.py`
- Modify: `wms/models_domain/shipment.py`
- Create: `wms/migrations/0120_cartonvolunteeractivity.py`
- Modify: `wms/preparateur_home_queries.py`
- Modify: `wms/tests/views/tests_views_scan_preparateur.py`

**Step 1: Write the failing test**

Add tests for:

- logging a `prepared` activity and an `edited` activity for the same carton
- preserving the original `prepared_by`
- `Voir dernier carton` preferring the latest non-shipped carton for the selected bénévole

Example:

```python
activity = CartonVolunteerActivity.objects.create(
    carton=carton,
    volunteer=volunteer,
    action=CartonVolunteerActivityAction.EDITED,
    actor=self.preparateur,
)
self.assertEqual(carton.prepared_by, volunteer.user)
self.assertEqual(find_last_carton_for_volunteer(volunteer), expected_carton)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.shipment.tests_carton_volunteer_activity \
  wms.tests.views.tests_views_scan_preparateur \
  -v 2
```

Expected:
- FAIL because the activity model and latest-carton query do not exist yet

**Step 3: Write minimal implementation**

Implement:

- the new carton activity model and migration
- helper functions to record activities
- the home-page “last carton” resolver
- the home action / redirect for `Voir dernier carton`

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add wms/carton_activity.py wms/tests/shipment/tests_carton_volunteer_activity.py wms/models_domain/shipment.py wms/migrations/0120_cartonvolunteeractivity.py wms/preparateur_home_queries.py wms/tests/views/tests_views_scan_preparateur.py
git commit -m "feat: log volunteer carton activity"
```

### Task 5: Thread The Selected Bénévole Through Carton Creation And Edit Paths

**Files:**
- Modify: `wms/domain/stock.py`
- Modify: `wms/domain/orders.py`
- Modify: `wms/order_view_handlers.py`
- Modify: `wms/pack_handlers.py`
- Modify: `wms/views_scan_preparateur.py`
- Modify: `wms/tests/orders/tests_pack_handlers.py`
- Modify: `wms/tests/domain/tests_domain_orders_extra.py`
- Modify: `wms/tests/views/tests_views.py`

**Step 1: Write the failing test**

Add coverage for:

- manual `scan_pack` carton creation storing `prepared_by` as the selected bénévole user
- order-driven preparation storing the selected bénévole user on created cartons
- carton edit adding an `edited` activity without replacing the original `prepared_by`

Example:

```python
self.assertEqual(created_carton.prepared_by, volunteer.user)
self.assertEqual(
    CartonVolunteerActivity.objects.filter(
        carton=carton,
        volunteer=volunteer,
        action=CartonVolunteerActivityAction.EDITED,
    ).count(),
    1,
)
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.orders.tests_pack_handlers \
  wms.tests.domain.tests_domain_orders_extra \
  wms.tests.views.tests_views \
  -v 2
```

Expected:
- FAIL because the current stock / order services only know the authenticated user

**Step 3: Write minimal implementation**

Thread the selected bénévole identity through the affected flows:

- allow carton creation helpers to distinguish:
  - authenticated actor account
  - bénévole user to store in `prepared_by`
  - bénévole profile for activity logging
- update manual pack and order-preparation paths to pass those values
- on carton edit success, append an `edited` activity row only when a real save occurred

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add wms/domain/stock.py wms/domain/orders.py wms/order_view_handlers.py wms/pack_handlers.py wms/views_scan_preparateur.py wms/tests/orders/tests_pack_handlers.py wms/tests/domain/tests_domain_orders_extra.py wms/tests/views/tests_views.py
git commit -m "feat: propagate active volunteer into carton flows"
```

### Task 6: Update The Preparateur Success Modal Chrome And Print Action

**Files:**
- Modify: `templates/scan/includes/pack_success_modal.html`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/static/scan/scan.js`

**Step 1: Write the failing test**

Extend the preparateur modal tests to assert:

- a top-right close button exists in the header
- the footer renders `Imprimer` for one carton
- the footer renders `Imprimer tout` for multiple cartons
- the markup carries the packing-list URLs needed to open one or many documents

Example:

```python
self.assertContains(response, 'data-pack-print-all="1"')
self.assertContains(response, "Imprimer tout")
self.assertContains(response, "btn-close")
```

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments.ScanShipmentViewsTests \
  -v 2
```

Expected:
- FAIL because the modal still exposes only the old footer close button

**Step 3: Write minimal implementation**

Implement:

- Bootstrap-style top-right close control
- footer print button label switching on carton count
- URL payload for one-or-many packing-list opens
- lightweight JS to close the modal and open all listed packing lists

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

**Step 5: Commit**

```bash
git add templates/scan/includes/pack_success_modal.html wms/tests/views/tests_views_scan_shipments.py wms/static/scan/scan.js
git commit -m "feat: improve preparateur success modal actions"
```

### Task 7: Re-Verify The Targeted Flow And Repo-Reference Impact

**Files:**
- Modify if needed: `docs/repo-reference/04-shared-contracts.md`
- Modify if needed: `docs/repo-reference/02-key-flows-and-living-tests.md`

**Step 1: Run focused verification**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_preparateur \
  wms.tests.shipment.tests_carton_volunteer_activity \
  wms.tests.orders.tests_pack_handlers \
  wms.tests.domain.tests_domain_orders_extra \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_views \
  -v 2
```

Expected:
- PASS with the preparateur entry flow, volunteer traceability, and modal behavior covered

**Step 2: Re-check repo reference**

Confirm whether the preparateur navigation contract now needs a short update in:

- `docs/repo-reference/04-shared-contracts.md`
- `docs/repo-reference/02-key-flows-and-living-tests.md`

If yes:

- document the new preparateur home entrypoint
- note the active bénévole shell behavior
- note that carton activity now distinguishes initial preparateur from later edits

**Step 3: Commit**

```bash
git add docs/repo-reference/04-shared-contracts.md docs/repo-reference/02-key-flows-and-living-tests.md
git commit -m "docs: align preparateur flow reference"
```
