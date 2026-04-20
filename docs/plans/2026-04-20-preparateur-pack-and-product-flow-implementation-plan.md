# Preparateur Pack And Product Flow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Adapt the legacy Django preparateur shell, add a validated-order selection flow, and let preparateurs create an immediately usable incomplete product with structured location selectors and initial stock directly from the pack page.

**Architecture:** Keep everything on the legacy `scan` stack. Lock the UI and permission changes with focused view tests first, then add the preparateur shell/navigation changes, introduce a preparateur-only order-selection view, add a dedicated pack-side product-creation form plus initial stock creation, and finish by wiring email notifications and repo-reference updates.

**Tech Stack:** Django views/forms/templates/handlers, legacy scan JavaScript/CSS, Django test suite via `./.venv/bin/python manage.py test`

---

### Task 1: Lock The Preparateur Shell Contract With Failing Tests

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add assertions that a preparateur visiting `/scan/pack/` sees:

- no `scan-faq-link`
- no `scan-masthead-account-toggle`
- `Bonjour`
- history buttons in the masthead
- `Choisir une commande`
- `Voir dernier colis`
- `Changer de compte`
- `Déconnexion`
- no `Runs magasin`

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_views_scan_shipments -v 2
```

Expected:
- FAIL because the current preparateur shell still exposes the old masthead/menu contract

**Step 3: Write minimal implementation**

Modify only the scan shell/template/CSS needed to satisfy the new preparateur rendering contract.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 2: Implement The Preparateur Masthead And Menu

**Files:**
- Modify: `templates/scan/base.html`
- Modify: `templates/scan/includes/scan_sidebar_navigation.html`
- Modify: `wms/static/scan/scan-bootstrap.css`

**Step 1: Write the failing test**

Extend the shell tests to assert:

- two-row preparateur masthead structure
- `Menu` rendered on the second row
- brand rendered on the second row
- account actions present in the menu, not the masthead dropdown

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected:
- FAIL because the preparateur layout still uses the generic shell structure

**Step 3: Write minimal implementation**

In the templates/CSS:

- branch the shell for `request.scan_is_preparateur`
- remove FAQ and account dropdown for preparateurs
- render `Bonjour <display name>`
- keep history buttons on row 1
- move `Menu` to row 2
- keep logo + `Messagerie Medicale` on row 2
- replace `Runs magasin` with the new menu items

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 3: Add A Preparateur Validated-Order Selection View

**Files:**
- Modify: `wms/scan_permissions.py`
- Modify: `wms/views.py` if re-export needed
- Modify: `wms/scan_urls.py`
- Modify: `wms/views_scan_orders.py`
- Create: `templates/scan/preparateur_order_select.html`
- Modify: `wms/tests/views/tests_views.py`
- Modify: `wms/tests/views/tests_views_scan_orders.py`

**Step 1: Write the failing test**

Add tests that:

- the preparateur whitelist allows the new route
- the page is accessible to preparateurs
- only approved/validated orders appear
- selecting an order redirects to `scan_pack`
- the full command-creation controls are not rendered

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views \
  wms.tests.views.tests_views_scan_orders -v 2
```

Expected:
- FAIL because the route and filtered preparateur view do not exist yet

**Step 3: Write minimal implementation**

- add a dedicated preparateur order-select route
- filter to validated/approved orders only
- submit selected order id back to `scan_pack`
- keep the UI reduced to selection only

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 4: Add The Last-Carton Shortcut

**Files:**
- Modify: `wms/scan_permissions.py` if needed
- Modify: `wms/scan_urls.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add tests that:

- a preparateur can open the new shortcut
- it redirects to the last carton where `prepared_by=request.user`
- if none exists, it redirects back to `scan_pack` with a user message

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments -v 2
```

Expected:
- FAIL because the route does not exist yet

**Step 3: Write minimal implementation**

- add a preparateur-only shortcut view
- resolve the latest relevant carton by `prepared_by` and `created_at`
- redirect accordingly

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 5: Lock The Pack Unknown-Product Popup Contract With Failing Tests

**Files:**
- Modify: `wms/tests/views/tests_views_scan_shipments.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add coverage for `/scan/pack/` preparateur mode:

- unknown-product creation button or popup trigger is rendered
- popup contains the required fields
- location controls are structured selectors, not free text
- no free-text location field is rendered in the popup

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected:
- FAIL because the popup and structured selectors do not exist yet

**Step 3: Write minimal implementation**

Only add the server-rendered HTML/data contract for the popup and selectors.

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 6: Add The Pack-Side Product Creation Form And View

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/scan_urls.py`
- Modify: `wms/views_scan_shipments.py`
- Modify: `templates/scan/pack.html`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add tests that a preparateur POST can:

- create a product from pack with required fields,
- reject missing name,
- reject missing identifier when barcode/ean/sku are all blank,
- reject missing MM/CN,
- reject missing quantity,
- reject invalid location selection,
- mark the product `is_incomplete=True`.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_shipments -v 2
```

Expected:
- FAIL because the form, action, and validation do not exist yet

**Step 3: Write minimal implementation**

Add a dedicated Django form and handler for pack-side product creation with:

- name
- sku / ean / barcode
- MM/CN choice
- quantity
- warehouse / zone / aisle / shelf selectors
- optional lot / expires_on / brand / notes

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 7: Create Initial Stock Immediately And Rebind The Pack Line

**Files:**
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/domain/stock.py` only if a small helper extraction is really needed
- Modify: `wms/scan_location_helpers.py` if selector payload needs richer data
- Modify: `wms/tests/orders/tests_pack_handlers.py`
- Modify: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add tests that after successful product creation:

- a `Location` selected from the structured selector is used,
- stock is created immediately,
- the new product becomes resolvable by its scanned identifier,
- the pack page comes back with the new product bound to the active line.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.orders.tests_pack_handlers \
  wms.tests.views.tests_views_scan_shipments -v 2
```

Expected:
- FAIL because current pack flow cannot create usable stock for a just-created product

**Step 3: Write minimal implementation**

- resolve the selected `Location`
- create the `Product`
- create the initial stock with existing stock services
- redirect back to `scan_pack` with the active line prefilled by the new identifier

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 8: Notify Admins And Superusers For Review

**Files:**
- Create: `templates/emails/preparateur_product_review_notification.txt`
- Modify: `wms/views_scan_shipments.py` or a small helper module if extraction stays tiny
- Modify: `wms/tests/emailing/tests_notifications_queue.py` or nearest producer test file

**Step 1: Write the failing test**

Add a producer-level test that successful preparateur product creation:

- queues or sends an email notification,
- targets superusers and validation staff without duplicates,
- includes product, preparateur, quantity, and location details.

**Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.emailing.tests_notifications_queue -v 2
```

Expected:
- FAIL because no producer exists yet for this event

**Step 3: Write minimal implementation**

- build the recipient list from `get_admin_emails()` plus the validation group if needed
- use `send_or_enqueue_email_safe`
- render the new text email template

**Step 4: Run test to verify it passes**

Run the same command.

Expected:
- PASS

### Task 9: Add Front-End Popup Behavior And Structured Location Selectors

**Files:**
- Modify: `wms/static/scan/scan.js`
- Modify: `templates/scan/pack.html`
- Modify if needed: `wms/static/scan/scan.css`

**Step 1: Lock the server-rendered contract first**

Re-run the pack view tests from Tasks 5 to 7 before touching JS.

**Step 2: Implement minimal JS**

Add client-side behavior for:

- detecting an unknown scanned product in preparateur pack mode
- opening the popup
- pre-filling the scanned code into barcode/ean/sku helper state
- cascading `warehouse -> zone -> aisle -> shelf`
- closing/resetting the popup cleanly

**Step 3: Verify behavior manually**

Manual flow:

1. Open `/scan/pack/` as preparateur
2. Scan an unknown code
3. Confirm the popup opens
4. Fill the minimum fields and choose location via selectors
5. Submit
6. Confirm the page returns with the product immediately reusable in pack

### Task 10: Update Repo Reference And Shared Contracts

**Files:**
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Modify if needed: `docs/repo-reference/02-key-flows-and-living-tests.md`

**Step 1: Write the doc change**

Update the preparateur navigation contract and any new validated-order selection / unknown-product review contract that is now part of routine maintenance.

**Step 2: Verify docs reflect reality**

Check the updated text against the final implemented routes and templates.

### Task 11: Run The Focused Verification Suite

**Files:**
- No code change

**Step 1: Run focused tests**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.views.tests_scan_bootstrap_ui \
  wms.tests.views.tests_views \
  wms.tests.views.tests_views_scan_orders \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.orders.tests_pack_handlers \
  wms.tests.emailing.tests_notifications_queue -v 2
```

Expected:
- PASS

**Step 2: Fix any regressions**

If failures appear, address them in the smallest possible change and rerun the affected subset first, then the whole focused suite again.

### Task 12: Final Sanity Check

**Files:**
- No code change

**Step 1: Re-check propagation**

Verify:

- preparateur whitelist still blocks non-approved surfaces
- non-preparateur scan shell is unchanged
- pack fallback server validation still reports `Produit introuvable.`
- docs are aligned

**Step 2: Prepare final summary**

Record:

- files changed
- tests run
- any remaining risks

Plan complete and saved to `docs/plans/2026-04-20-preparateur-pack-and-product-flow-implementation-plan.md`. Since subagent delegation was not requested in this thread, I will execute the plan locally in this session.
