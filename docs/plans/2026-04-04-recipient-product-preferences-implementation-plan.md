# Recipient Product Preferences Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add destination-scoped recipient product preferences, recipient detail cockpits, refusal-conflict overrides in shipment creation, and a first compatibility/coverage layer for ready parcels.

**Architecture:** Anchor canonical preferences on `ShipmentRecipientOrganization`, keep `unspecified` implicit, edit the same data from portal and scan/admin detail pages, and reuse the existing shipment conflict popup pattern for refused-product overrides. Build the recommendation layer as a lightweight scoring service instead of a global optimizer.

**Tech Stack:** Django models/views/templates, legacy scan JS, Django test runner, migrations.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`, `@repo-reference-governance`.

### Task 1: Add domain models for canonical preferences and overrides

**Files:**
- Modify: `wms/models_domain/shipment_parties.py`
- Modify: `wms/models.py`
- Create: `wms/migrations/<next>_recipient_product_preferences.py`
- Test: `wms/tests/portal/tests_portal_recipient_sync.py`
- Test: `wms/tests/core/tests_models_methods.py`
- Create: `wms/tests/core/tests_recipient_product_preferences.py`

**Step 1: Write the failing test**

Add tests that verify:
- one preference row is unique per `(recipient_organization, product)`
- `requested` requires `quantity_target` and `period_unit`
- `allowed` requires `quantity_target` and `period_unit`
- `refused` rejects quantity fields
- override rows can be created without mutating canonical preferences

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_recipient_product_preferences -v 2`
Expected: FAIL because the models do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- `RecipientProductPreference`
- `ShipmentPreferenceOverride`
- model validation and unique constraints
- `wms/models.py` export wiring
- migration

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_recipient_product_preferences -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/models_domain/shipment_parties.py wms/models.py wms/migrations/*.py wms/tests/core/tests_recipient_product_preferences.py
git commit -m "feat: add recipient product preference domain models"
```

### Task 2: Add preference resolution and implicit `unspecified` behavior

**Files:**
- Create: `wms/recipient_product_preferences.py`
- Test: `wms/tests/core/tests_recipient_product_preferences.py`

**Step 1: Write the failing test**

Add tests that verify:
- missing row resolves to effective status `unspecified`
- explicit rows resolve correctly
- helper returns target quantity and period only for `requested` and `allowed`

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_recipient_product_preferences.RecipientProductPreferenceResolutionTests -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement a small shared helper API, for example:
- `resolve_effective_recipient_product_preference(...)`
- `list_effective_recipient_product_preferences(...)`

Keep `unspecified` implicit and deterministic.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_recipient_product_preferences.RecipientProductPreferenceResolutionTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/recipient_product_preferences.py wms/tests/core/tests_recipient_product_preferences.py
git commit -m "feat: add recipient preference resolution helpers"
```

### Task 3: Add portal recipient detail route and lightweight list entrypoint

**Files:**
- Modify: `wms/portal_urls.py`
- Modify: `wms/views_portal_account.py`
- Modify: `templates/portal/recipients.html`
- Create: `templates/portal/recipient_detail.html`
- Test: `wms/tests/views/tests_views_portal.py`
- Test: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write the failing test**

Add tests that verify:
- the recipients list renders an `Ouvrir` action
- a recipient detail page is reachable only for a recipient owned by the current association profile
- the detail page shows the current recipient identity block and an empty preferences state

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalViewsTests.test_portal_recipients_list_shows_open_action wms.tests.views.tests_views_portal.PortalViewsTests.test_portal_recipient_detail_get_shows_empty_preferences_state -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement:
- a new portal detail route
- `Ouvrir` link on the recipients list
- a recipient detail template with identity/context sections and placeholder preference panel

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalViewsTests.test_portal_recipients_list_shows_open_action wms.tests.views.tests_views_portal.PortalViewsTests.test_portal_recipient_detail_get_shows_empty_preferences_state -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/portal_urls.py wms/views_portal_account.py templates/portal/recipients.html templates/portal/recipient_detail.html wms/tests/views/tests_views_portal.py wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "feat: add portal recipient detail cockpit entrypoint"
```

### Task 4: Add portal CRUD for explicit preference rows

**Files:**
- Modify: `wms/views_portal_account.py`
- Modify: `templates/portal/recipient_detail.html`
- Test: `wms/tests/views/tests_views_portal.py`
- Test: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write the failing test**

Add tests that verify:
- portal can add a `requested` product with weekly target
- portal can add a `refused` product without quantity
- portal can update and delete a preference row
- invalid combinations return errors and keep entered values

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalViewsTests.test_portal_recipient_detail_post_adds_requested_preference wms.tests.views.tests_views_portal.PortalViewsTests.test_portal_recipient_detail_post_rejects_refused_preference_with_quantity -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Add the detail-page POST actions for:
- create preference row
- update preference row
- delete preference row

Use product search/select against the existing catalog and keep the page recipient-scoped.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal.PortalViewsTests.test_portal_recipient_detail_post_adds_requested_preference wms.tests.views.tests_views_portal.PortalViewsTests.test_portal_recipient_detail_post_rejects_refused_preference_with_quantity -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/views_portal_account.py templates/portal/recipient_detail.html wms/tests/views/tests_views_portal.py wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "feat: add portal recipient preference editing"
```

### Task 5: Add scan/admin recipient detail route and canonical preference editing

**Files:**
- Modify: nearest scan/admin contacts route module and view module
- Modify: `templates/scan/includes/admin_contacts_contact_form.html`
- Create: scan/admin recipient detail template(s)
- Test: nearest scan/admin recipient cockpit tests
- Test: `wms/tests/views/tests_views_scan_admin.py`
- Test: `wms/tests/views/tests_views_scan_admin_shipment_parties.py`

**Step 1: Write the failing test**

Add tests that verify:
- scan/admin recipient runtime rows expose an `Ouvrir` action
- the detail page shows current explicit preferences
- staff can create/update/delete canonical preference rows from scan/admin

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_shipment_parties -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement:
- scan/admin recipient detail route
- `Ouvrir` entrypoint from the existing cockpit
- same canonical preference editor on the scan/admin detail page

Do not duplicate business rules already enforced by the shared preference model/service.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_shipment_parties -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add templates/scan/includes/admin_contacts_contact_form.html templates/scan/*.html wms/tests/views/tests_views_scan_admin.py wms/tests/views/tests_views_scan_admin_shipment_parties.py
git commit -m "feat: add scan admin recipient preference editing"
```

### Task 6: Add parcel-content data needed for refusal checks

**Files:**
- Modify: `wms/scan_carton_helpers.py`
- Modify: `wms/shipment_form_helpers.py`
- Test: `wms/tests/scan/tests_scan_carton_helpers.py`
- Test: `wms/tests/shipment/tests_shipment_form_helpers.py`

**Step 1: Write the failing test**

Add tests that verify:
- available parcel JSON now includes product ids/names and quantities for conflict evaluation
- existing parcel label/preassignment fields remain unchanged

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.scan.tests_scan_carton_helpers wms.tests.shipment.tests_shipment_form_helpers -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Extend `build_available_cartons()` so each parcel option carries a compact item payload:
- `products`: list of `{product_id, product_name, quantity}`

Keep the payload small and deterministic.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.scan.tests_scan_carton_helpers wms.tests.shipment.tests_shipment_form_helpers -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/scan_carton_helpers.py wms/shipment_form_helpers.py wms/tests/scan/tests_scan_carton_helpers.py wms/tests/shipment/tests_shipment_form_helpers.py
git commit -m "feat: expose parcel product payload for preference checks"
```

### Task 7: Add refused-product conflict detection in shipment handlers

**Files:**
- Modify: `wms/scan_shipment_handlers.py`
- Create or modify: `wms/recipient_product_preferences.py`
- Test: `wms/tests/scan/tests_scan_shipment_handlers.py`

**Step 1: Write the failing test**

Add tests that verify:
- assigning a ready parcel containing a refused product raises a blocking error until confirmed
- confirming the conflict allows assignment
- confirming writes override rows
- mono-product shipment lines apply the same rule

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.scan.tests_scan_shipment_handlers -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement shared helpers to:
- resolve the effective operational recipient organization for the selected shipment recipient
- inspect parcel or mono-product line items against explicit preferences
- raise a conflict carrying enough detail for the UI layer
- write `ShipmentPreferenceOverride` rows only after user confirmation

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.scan.tests_scan_shipment_handlers -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/scan_shipment_handlers.py wms/recipient_product_preferences.py wms/tests/scan/tests_scan_shipment_handlers.py
git commit -m "feat: block refused recipient products during shipment assignment"
```

### Task 8: Reuse the shipment popup pattern for refused-product overrides

**Files:**
- Modify: `templates/scan/shipment_create.html`
- Modify: `templates/scan/includes/shipment_create_preassignment_overlay.html`
- Modify: `wms/static/scan/scan.js`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add tests that verify:
- the shipment page exposes the data attributes/messages required for refused-product conflicts
- the overlay can render a refused-product message
- confirmed conflicts persist the right hidden form signal

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Reuse the existing overlay pattern:
- add a second conflict template or a generalized conflict payload
- list only refused products in the message
- keep preassignment behavior intact

Avoid adding a separate modal system.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui wms.tests.views.tests_views_scan_shipments -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add templates/scan/shipment_create.html templates/scan/includes/shipment_create_preassignment_overlay.html wms/static/scan/scan.js wms/tests/views/tests_scan_bootstrap_ui.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: reuse shipment conflict popup for refused products"
```

### Task 9: Add weekly/monthly coverage computation

**Files:**
- Modify: `wms/recipient_product_preferences.py`
- Create: `wms/tests/core/tests_recipient_product_preference_coverage.py`

**Step 1: Write the failing test**

Add tests that verify:
- weekly windows use Monday-Sunday boundaries
- monthly windows use calendar month boundaries
- `remaining_need` subtracts delivered and in-pipeline quantities
- `unspecified` and `refused` do not compute quantity coverage

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_recipient_product_preference_coverage -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement a small coverage helper API that returns:
- effective status
- target quantity
- delivered quantity in period
- pipeline quantity in period
- remaining need

Use existing shipment workflow milestone timestamps as the delivery evidence source.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_recipient_product_preference_coverage -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/recipient_product_preferences.py wms/tests/core/tests_recipient_product_preference_coverage.py
git commit -m "feat: add recipient preference coverage metrics"
```

### Task 10: Add ready-parcel compatibility scoring

**Files:**
- Modify: `wms/recipient_product_preferences.py`
- Test: `wms/tests/core/tests_recipient_product_preference_coverage.py`

**Step 1: Write the failing test**

Add tests that verify:
- parcels with refused products are `incompatibles`
- parcels covering active requested need outrank parcels covering only allowed products
- parcels with only unspecified products remain compatible but lower-ranked

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_recipient_product_preference_coverage.RecipientParcelCompatibilityTests -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement a parcel scoring helper returning:
- score
- bucket: `tres_adaptes | compatibles | a_eviter | incompatibles`
- explanation summary for the UI

Keep the algorithm small, explicit, and non-global.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_recipient_product_preference_coverage.RecipientParcelCompatibilityTests -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/recipient_product_preferences.py wms/tests/core/tests_recipient_product_preference_coverage.py
git commit -m "feat: score ready parcels against recipient preferences"
```

### Task 11: Surface coverage and compatibility guidance on recipient and shipment pages

**Files:**
- Modify: portal recipient detail template/view
- Modify: scan/admin recipient detail template/view
- Modify: `wms/views_scan_shipments.py`
- Modify: `templates/scan/shipment_create.html`
- Test: `wms/tests/views/tests_views_portal.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add tests that verify:
- recipient detail pages show coverage summaries for explicit `requested` / `allowed` products
- shipment create page exposes compatibility labels for ready parcels
- refused parcels remain visually identified as conflicting

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.views.tests_views_scan_shipments -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Render:
- per-product coverage summary on recipient detail pages
- compatibility bucket and explanation on ready parcel choices or adjacent guidance blocks

Do not auto-select parcels based on the score.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.views.tests_views_scan_shipments -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/views_portal_account.py wms/views_scan_shipments.py templates/portal/recipient_detail.html templates/scan/shipment_create.html wms/tests/views/tests_views_portal.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: show recipient coverage and parcel compatibility guidance"
```

### Task 12: Update repo-reference governance docs and run the closest regression suites

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/03-impact-map.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`

**Step 1: Write the doc updates**

Document:
- the new recipient preference contract
- the portal and scan/admin recipient detail surfaces
- shipment refused-product override behavior

**Step 2: Run targeted regressions**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_recipient_product_preferences wms.tests.core.tests_recipient_product_preference_coverage wms.tests.portal.tests_portal_recipient_sync wms.tests.views.tests_views_portal wms.tests.views.tests_portal_bootstrap_ui wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_admin_shipment_parties wms.tests.scan.tests_scan_shipment_handlers wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_scan_bootstrap_ui -v 2`
Expected: PASS

**Step 3: Summarize verification evidence**

Capture:
- exact commands run
- whether any nearby tests were skipped
- remaining follow-ups intentionally deferred to V2

**Step 4: Commit**

```bash
git add docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/03-impact-map.md docs/repo-reference/04-shared-contracts.md
git commit -m "docs: record recipient preference workflow contracts"
```
