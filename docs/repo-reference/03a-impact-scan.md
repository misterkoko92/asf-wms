# Scan Impact Map

Use this file when touching any internal operational `/scan/` surface.

Read this file for changes involving:

- warehouse workflows
- stock movements
- receipts
- shipment preparation
- shipment creation/edit from scan
- carton operations
- dashboards
- billing screens
- admin scan tools
- scan search / lists / filters
- operator productivity flows
- scan shared JS/CSS assets
- barcode / camera / OCR flows
- scan printing actions
- operational settings exposed in scan

`/scan/` is the main internal execution surface. Small UX regressions can create daily friction.

---

## Also Read

Depending on the change, also read:

- `03c-impact-shipments.md` — shipment/carton lifecycle
- `03d-impact-parties.md` — contacts / selectors / actor assignment
- `03e-impact-print-documents.md` — labels / documents / print actions
- `03f-impact-planning.md` — preparation handoff / planning visibility
- `03g-impact-shared-ui-api.md` — shared UI / mirrored API cockpits
- `03h-impact-email-events.md` — notifications triggered internally
- `04-shared-contracts.md` — shared list/filter/UI contracts

If unsure, read more than one file.

---

## Critical Invariants

These rules must remain true unless explicitly redesigned.

### Operator Speed

- common actions must stay fast
- extra clicks require strong justification
- repetitive tasks must remain optimized

### Warehouse Accuracy

- stock movements must remain traceable
- counts must remain coherent
- destructive actions require clear intent

### Navigation Stability

- filters, sort, page state should survive normal actions
- operators should return to expected context after actions

### Shared Asset Stability

Stable shared entrypoints must remain valid:

- `scan.js`
- `scan.css`
- `scan-bootstrap.css`

### Permission Safety

Internal tools with elevated powers must not widen access accidentally.

---

## Always Check

### URL / Runtime Sources

- `wms/scan_urls.py`
- relevant `wms/views_scan_*.py`
- `wms/views.py` export surface
- nearest `*_handlers.py`

### Main Runtime Clusters

- `wms/views_scan_stock.py`
- `wms/views_scan_shipments.py`
- `wms/views_scan_shipments_support.py`
- `wms/views_scan_receipts.py`
- `wms/views_scan_orders.py`
- `wms/views_scan_admin.py`
- `wms/views_scan_dashboard.py`
- `wms/views_scan_billing.py`
- `wms/views_scan_misc.py`
- `wms/views_scan_preparation.py`

### Templates

- `templates/scan/`

### Static Assets

- root legacy asset surface: `wms/static/scan/`
- modular JS slices: `wms/static/scan/modules/`
- extracted CSS slices: `wms/static/scan/css/partials/`

### Tests

- `wms/tests/views/`

---

## Ask Yourself

### UX Questions

- did this add friction to a daily workflow?
- did clicks / scroll / page loads increase?
- is the primary action still obvious?
- can keyboard-heavy users still work efficiently?

### Data Questions

- do counts/badges still reflect truth?
- did a bulk action become unsafe?
- can duplicate submissions happen?

### Navigation Questions

- do filters survive after save/delete/close?
- does pagination still preserve context?
- do back-links return correctly?

### Operational Questions

- does this slow warehouse throughput?
- does this increase training burden?
- can volunteers understand it quickly?

### Cross-Surface Questions

- is the same data shown in API or planning?
- do print actions still work?
- do shipment side effects still trigger?

---

## Precision Checks

### If Editing Shared Assets

Also verify:

- `templates/scan/base.html`
- `templates/portal/base.html`
- `templates/planning/base.html`

Do not break stable shared asset filenames.

### If Editing Lists / Search

Also verify:

- `wms/scan_list_urls.py`
- `templates/scan/includes/scan_list_pagination.html`
- `wms/templatetags/wms_dates.py`
- `04-shared-contracts.md`

### If Editing Camera / Barcode / OCR

Also verify:

- camera permission flows
- mobile usability
- barcode scan speed
- fallback manual entry

### If Editing Bulk Actions

Also verify:

- confirmation UX
- idempotency
- selected-row integrity
- permission boundaries

### If Editing Preparation Flows

Also verify:

- handoff to shipment creation
- reservation logic
- status transitions
- planning visibility after confirmation

---

## Run First

Choose nearest tests.

### High Value

- nearest tests in `wms/tests/views/`
- `wms/tests/core/tests_flow.py`

### If Shared UI Changed

- bootstrap UI tests
- cross-surface UI tests

### If Shipment Behavior Changed

- shipment tests
- API E2E workflow tests

### If Preparation Changed

- preparation tests
- planning smoke tests

---

## Known Traps

### Friction Trap

Tiny UI changes multiplied by daily usage create large hidden cost.

### Badge Drift Trap

Counts on dashboards/lists no longer match reality.

### Double Submit Trap

Slow pages create duplicate actions.

### Filter Loss Trap

Operators repeatedly lose list context.

### Mobile Trap

Camera or scan flows regress on phones/tablets.

### Permission Trap

Admin-only action becomes visible wider than intended.

### Legacy Asset Trap

Refactor breaks shared CSS/JS consumed by other surfaces.

---

## Docs To Update

If behavior changed, review:

- `docs/mvp_spec.md`
- `docs/operations.md`
- `docs/release_checklist.md`
- `docs/repo-reference/02-key-flows-and-living-tests.md`
- `docs/repo-reference/04-shared-contracts.md`

---

## Final Rule

If changing `/scan/`, optimize for operator throughput, clarity, and safety — not elegance alone.
