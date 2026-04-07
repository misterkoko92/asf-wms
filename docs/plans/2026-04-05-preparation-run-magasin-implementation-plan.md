# Preparation Run Magasin Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a new warehouse `run magasin` flow that proposes mixed or ASF-stock shipments, reserves stock during operator review, converts accepted proposals into real `Shipment` rows in `PICKING`, and keeps the existing `planning vols` flow separate.

**Architecture:** Add a dedicated warehouse-preparation domain and services layer under `wms/preparation/`, expose the operator flow from the legacy `scan` surface, and treat the existing planning-vols stack as a constraint source only. Keep the run frozen after generation, create a new run on recalculation, and reuse the lot-level reservation principle already used elsewhere in the repo.

**Tech Stack:** Django models/views/forms/templates, legacy scan JS, Django test runner, migrations, existing stock and planning helpers.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`, `@repo-reference-governance`.

### Task 1: Add warehouse-preparation domain models

**Files:**
- Create: `wms/models_domain/preparation.py`
- Modify: `wms/models.py`
- Create: `wms/migrations/<next>_preparation_run_magasin.py`
- Create: `wms/tests/preparation/tests_models.py`

**Step 1: Write the failing test**

Add model tests that verify:
- parameter sets can be created
- shipper rules and destination rules are unique per scope
- recurring needs are unique per `(shipper, recipient_organization, destination)`
- shipment proposals stay unique per `(run, shipper, recipient_organization, destination, sequence)`
- reservations and decision logs persist required audit fields

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_models -v 2`
Expected: FAIL because the module and models do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- `PreparationParameterSet`
- `PreparationDestinationRule`
- `PreparationShipperRule`
- `RecurringPreparationNeed`
- `PreparationRun`
- `PreparationRunNeedSnapshot`
- `PreparationShipmentProposal`
- `PreparationCartonProposal`
- `PreparationReservation`
- `PreparationDecisionLog`
- export wiring in `wms/models.py`
- migration

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_models -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/models_domain/preparation.py wms/models.py wms/migrations/*.py wms/tests/preparation/tests_models.py
git commit -m "feat: add preparation run domain models"
```

### Task 2: Add preference resolution with category fallback

**Files:**
- Modify: `wms/recipient_product_preferences.py`
- Create: `wms/tests/preparation/tests_preference_resolution.py`

**Step 1: Write the failing test**

Add tests that verify:
- exact product preference wins over category preference
- more specific category wins over broader category
- category-level `requested` and `allowed` are supported
- category-level `refused` is rejected
- kits resolve by kit product id and do not inspect components

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_preference_resolution -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Extend the shared preference resolver so it can:
- resolve product-level preferences first
- resolve category-level preferences by specificity second
- return `unspecified` last
- keep category-level `refused` invalid

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_preference_resolution -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/recipient_product_preferences.py wms/tests/preparation/tests_preference_resolution.py
git commit -m "feat: add category-aware recipient preference resolution"
```

### Task 3: Add run-demand snapshotting

**Files:**
- Create: `wms/preparation/needs.py`
- Create: `wms/tests/preparation/tests_needs.py`

**Step 1: Write the failing test**

Add tests that verify:
- active recurring needs are copied into run snapshots at generation time
- later edits to the recurring need do not mutate the run snapshot
- run-local overrides adjust only the snapshot

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_needs -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement snapshot helpers that:
- select active recurring needs
- copy them into `PreparationRunNeedSnapshot`
- support local override fields on the snapshot

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_needs -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/preparation/needs.py wms/tests/preparation/tests_needs.py
git commit -m "feat: snapshot recurring preparation needs into runs"
```

### Task 4: Add stock reservation services for run proposals

**Files:**
- Create: `wms/preparation/reservations.py`
- Create: `wms/tests/preparation/tests_reservations.py`

**Step 1: Write the failing test**

Add tests that verify:
- generation reserves stock against `ProductLot.quantity_reserved`
- reject/delete releases reservation rows and lot reservations
- conversion consumes reserved quantities
- urgent override can reclaim reserved stock and marks the proposal for recalculation
- urgent reserve reduces run-usable stock

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_reservations -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement reservation helpers that:
- allocate FEFO stock into `PreparationReservation`
- update lot `quantity_reserved`
- release or consume reservations
- support explicit urgent override with audit logging

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_reservations -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/preparation/reservations.py wms/tests/preparation/tests_reservations.py
git commit -m "feat: add preparation run stock reservation services"
```

### Task 5: Add candidate builders for deposited and ASF-stock cartons

**Files:**
- Create: `wms/preparation/candidates.py`
- Create: `wms/tests/preparation/tests_candidates.py`

**Step 1: Write the failing test**

Add tests that verify:
- deposited cartons are read only from the exact `shipper + recipient + destination`
- deposited cartons are never reallocated across recipients
- ASF-stock candidates are mono-product only
- kit candidates are allowed as mono-product candidates
- mixed proposals can include deposited cartons plus generated ASF-stock cartons

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_candidates -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement candidate-building helpers that:
- gather deposited cartons already bound to the target recipient/destination
- build mono-product ASF-stock carton candidates
- keep kit products as mono-product planning candidates
- expose a source type flag for scoring

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_candidates -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/preparation/candidates.py wms/tests/preparation/tests_candidates.py
git commit -m "feat: build deposited and ASF-stock preparation candidates"
```

### Task 6: Add scoring and fairness helpers

**Files:**
- Create: `wms/preparation/scoring.py`
- Create: `wms/tests/preparation/tests_scoring.py`

**Step 1: Write the failing test**

Add tests that verify:
- `requested` scores above `allowed`
- `unspecified` is excluded by default but remains parameter-driven
- need coverage deducts all relevant `PACKED` and `PLANNED` shipments
- fairness uses only ASF-stock or mixed history
- deposited-only history does not affect fairness
- non-ASF shippers beat ASF at equal conditions because of the ASF penalty

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_scoring -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement scoring helpers that:
- compute remaining need
- compute fairness by `(destination, L2/L3 category)` on `PACKED/PLANNED` history
- apply shipper coefficient and ASF penalty
- generate human-readable score reasons

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_scoring -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/preparation/scoring.py wms/tests/preparation/tests_scoring.py
git commit -m "feat: add preparation run scoring and fairness"
```

### Task 7: Add run generation orchestration and flight fallback

**Files:**
- Create: `wms/preparation/generation.py`
- Create: `wms/tests/preparation/tests_generation.py`

**Step 1: Write the failing test**

Add tests that verify:
- generation snapshots needs and parameters
- generation builds shipment proposals and carton proposals
- target shipment size, tolerance, and minimum threshold are respected
- too-small proposals fall back to backlog
- flight API failure falls back to the last exploitable batch
- fallback source and freshness are persisted in the run snapshot

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_generation -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement a generator that:
- loads run inputs
- loads flight constraints from the planning-vols side
- applies fallback flight sourcing when needed
- builds candidates, scores them, assembles proposals, and reserves stock

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_generation -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/preparation/generation.py wms/tests/preparation/tests_generation.py
git commit -m "feat: generate warehouse preparation proposals"
```

### Task 8: Add run obsolescence and explicit recalculation behavior

**Files:**
- Create: `wms/preparation/obsolescence.py`
- Create: `wms/tests/preparation/tests_obsolescence.py`

**Step 1: Write the failing test**

Add tests that verify:
- manual shipment creation affecting coverage marks impacted proposals `needs_recalc`
- manual stock consumption affecting reservation viability marks impacted proposals `needs_recalc`
- open runs do not silently mutate their proposal contents
- explicit recalculation creates a new run instead of mutating the old one

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_obsolescence -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement helpers that:
- mark proposals stale after manual impacts
- keep the run frozen
- create a new run on recalculation

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_obsolescence -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/preparation/obsolescence.py wms/tests/preparation/tests_obsolescence.py
git commit -m "feat: track preparation proposal obsolescence"
```

### Task 9: Add scan routes, forms, and views for run creation and review

**Files:**
- Modify: `wms/scan_urls.py`
- Create: `wms/forms_preparation.py`
- Create: `wms/views_scan_preparation.py`
- Create: `wms/tests/views/tests_views_scan_preparation.py`

**Step 1: Write the failing test**

Add tests that verify:
- staff can open the preparation-run list and create page
- the create form exposes run inputs
- generation creates a reviewable run
- the review page shows proposal rows, score reasons, fallback-flight warnings, and stale markers

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_preparation -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement:
- scan URL entries
- run create form
- run list/detail/review views
- minimal context for operator review

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_preparation -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/scan_urls.py wms/forms_preparation.py wms/views_scan_preparation.py wms/tests/views/tests_views_scan_preparation.py
git commit -m "feat: add scan preparation run review surface"
```

### Task 10: Add templates and operator actions for accept/refuse/partial validation

**Files:**
- Create: `templates/scan/preparation_run_list.html`
- Create: `templates/scan/preparation_run_create.html`
- Create: `templates/scan/preparation_run_detail.html`
- Modify: `wms/views_scan_preparation.py`
- Test: `wms/tests/views/tests_views_scan_preparation.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Add tests that verify:
- proposal rows expose shipment- and carton-level checkboxes
- operators can accept all, accept partial, refuse keep draft, and refuse delete
- needs-recalc proposals are clearly marked
- templates preserve scan bootstrap contracts

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_preparation wms.tests.views.tests_scan_bootstrap_ui -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement:
- list/create/detail templates
- checkbox-based actions
- bulk operator action handling
- display of score reasons and reservation state

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_preparation wms.tests.views.tests_scan_bootstrap_ui -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add templates/scan/preparation_run_list.html templates/scan/preparation_run_create.html templates/scan/preparation_run_detail.html wms/views_scan_preparation.py wms/tests/views/tests_views_scan_preparation.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat: add preparation run operator review actions"
```

### Task 11: Add conversion from accepted proposals to real shipments and cartons

**Files:**
- Create: `wms/preparation/conversion.py`
- Modify: `wms/views_scan_preparation.py`
- Create: `wms/tests/preparation/tests_conversion.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Add tests that verify:
- accepted proposals create `Shipment` rows in `ShipmentStatus.PICKING`
- accepted deposited cartons are assigned to the new shipment without reallocation logic
- accepted ASF-stock carton proposals create real cartons through the stock-packing path
- partial acceptance creates reduced shipments only for the accepted cartons
- rejected cartons release their reservations

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_conversion wms.tests.views.tests_views_scan_shipments -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement conversion helpers that:
- create the shipment in `PICKING`
- assign accepted deposited cartons
- create accepted ASF-stock cartons through the packing service
- consume or release reservations accordingly
- link the proposal back to the created shipment/cartons

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_conversion wms.tests.views.tests_views_scan_shipments -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/preparation/conversion.py wms/views_scan_preparation.py wms/tests/preparation/tests_conversion.py wms/tests/views/tests_views_scan_shipments.py
git commit -m "feat: convert accepted preparation proposals into shipments"
```

### Task 12: Add final operator confirmation gate before `PACKED`

**Files:**
- Modify: `wms/views_scan_shipments.py`
- Modify: `wms/carton_handlers.py` or nearest status helper module
- Create: `wms/tests/preparation/tests_ready_gate.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`
- Test: `wms/tests/planning/tests_run_preparation.py`

**Step 1: Write the failing test**

Add tests that verify:
- converted shipments stay in `PICKING` until explicit operator confirmation
- even mixed shipments with already deposited cartons do not enter `PACKED` automatically
- the planning-vols source query still ignores not-yet-packed converted shipments

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_ready_gate wms.tests.views.tests_views_scan_shipments wms.tests.planning.tests_run_preparation -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement the final gate that:
- keeps converted shipments in `PICKING`
- requires explicit operator action to promote them to `PACKED`
- preserves the existing planning-vols eligibility contract

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.preparation.tests_ready_gate wms.tests.views.tests_views_scan_shipments wms.tests.planning.tests_run_preparation -v 2`
Expected: PASS

**Step 5: Commit**

```bash
git add wms/views_scan_shipments.py wms/carton_handlers.py wms/tests/preparation/tests_ready_gate.py wms/tests/views/tests_views_scan_shipments.py wms/tests/planning/tests_run_preparation.py
git commit -m "feat: gate converted preparation shipments behind final ready confirmation"
```

### Task 13: Add docs and repo-reference propagation

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/03-impact-map.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Modify: `docs/operations.md`
- Modify: `docs/release_checklist.md`

**Step 1: Write the failing doc checklist**

List the exact contracts that changed:
- scan operator surface now includes `run magasin`
- preference resolution now supports category fallback
- stock reservations now include warehouse-run reservations
- planning-vols remains separate and still consumes only `PACKED/PLANNED`

**Step 2: Verify current docs are incomplete**

Run: `rg -n "run magasin|preparation run|category preference|needs_recalc|fallback flight" docs/repo-reference docs/operations.md docs/release_checklist.md`
Expected: missing or outdated references.

**Step 3: Write minimal documentation updates**

Update the repo reference and ops docs so they describe:
- the new scan run-magasin flow
- the frozen-run and stale-proposal behavior
- urgent override of reserved stock
- fallback flight sourcing

**Step 4: Verify the docs mention the new contracts**

Run: `rg -n "run magasin|fallback flight|needs_recalc|PACKED/PLANNED" docs/repo-reference docs/operations.md docs/release_checklist.md`
Expected: the new references are present.

**Step 5: Commit**

```bash
git add docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/03-impact-map.md docs/repo-reference/04-shared-contracts.md docs/operations.md docs/release_checklist.md
git commit -m "docs: record preparation run magasin contracts"
```

### Task 14: Run the targeted regression suite

**Files:**
- Test: `wms/tests/preparation/`
- Test: `wms/tests/views/tests_views_scan_preparation.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/planning/tests_run_preparation.py`

**Step 1: Run the focused suite**

Run: `./.venv/bin/python manage.py test wms.tests.preparation wms.tests.views.tests_views_scan_preparation wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_scan_bootstrap_ui wms.tests.planning.tests_run_preparation -v 2`
Expected: PASS

**Step 2: Fix any failures**

Apply only the minimal changes needed to satisfy the failing contract.

**Step 3: Re-run the same suite**

Run: `./.venv/bin/python manage.py test wms.tests.preparation wms.tests.views.tests_views_scan_preparation wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_scan_bootstrap_ui wms.tests.planning.tests_run_preparation -v 2`
Expected: PASS

**Step 4: Run a final smoke subset**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_flow api.tests.tests_ui_e2e_workflows -v 2`
Expected: PASS or explicit evidence of unrelated pre-existing failures.

**Step 5: Commit**

```bash
git add -A
git commit -m "test: verify preparation run magasin feature set"
```
