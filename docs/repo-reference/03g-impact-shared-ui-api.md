# Shared UI & API Impact Map

Use this file when touching shared UI primitives, reusable templates, common CSS/JS contracts, or API payloads that mirror user-facing screens.

Read this file for changes involving:

- shared components
- template tags
- reusable form controls
- common tables / pagination
- shared CSS utilities
- shared JS helpers
- UI behavior reused across surfaces
- mirrored HTML/API payloads
- dashboard API endpoints
- common selectors
- base templates
- cross-surface navigation contracts
- public import surfaces (`__init__.py`)
- type-check boundaries for extracted layers

Shared changes have broad blast radius. Small edits can break many surfaces at once.

---

## Also Read

Depending on the change, also read:

- `03a-impact-scan.md` — internal UI consumers
- `03b-impact-portal.md` — external UI consumers
- `03f-impact-planning.md` — planning shell consumers
- `03c-impact-shipments.md` — workflow payload consumers
- `04-shared-contracts.md` — canonical cross-surface UI rules

If unsure, read more than one file.

---

## Critical Invariants

These rules must remain true unless explicitly redesigned.

### Cross-Surface Consistency

Shared components should behave consistently across scan, portal, planning, admin, and volunteer surfaces where intended.

### Contract Stability

Common payload fields, pagination params, sort keys, selectors, and naming should remain stable unless versioned intentionally.

### Adapter Thinness

Where HTML pages and API endpoints mirror the same cockpit, shared application sources should own composition logic.

### Public Import Stability

Package-root `__init__.py` surfaces should remain safe import points for agents and future refactors.

### Type Gate Integrity

Structural typing boundaries should continue validating intended layers.

---

## Always Check

### Shared UI Sources

- `wms/templatetags/wms_ui.py`
- `templates/wms/components/`
- `templates/scan/ui_lab.html`

### Shared Assets

- `wms/static/scan/scan-bootstrap.css`
- `wms/static/scan/scan.js`
- `wms/static/scan/modules/core.js`

### Base Templates / Consumers

- `templates/scan/base.html`
- `templates/portal/base.html`
- `templates/planning/base.html`

### API Sources

- `api/v1/urls.py`
- `api/v1/ui_views.py`

### Shared Application Sources

- `wms/application/*`

### Public Import Surfaces

- `wms/application/__init__.py`
- `wms/events/__init__.py`
- `wms/jobs/__init__.py`
- `wms/parties/__init__.py`
- `wms/artifacts/__init__.py`

### Type Boundaries

- `mypy.ini`
- `pyrightconfig.json`

---

## Ask Yourself

### UI Questions

- does this component still behave the same everywhere?
- did one surface drift visually or functionally?
- did keyboard/mobile behavior regress?

### API Questions

- does HTML output still match mirrored API payload truth?
- did field names change silently?
- did pagination/filter semantics drift?

### Architecture Questions

- is logic duplicated in views and API again?
- should composition move into `wms/application/*`?
- did a shared primitive become too local?

### Import Questions

- did moving files break public imports?
- are stable package facades still valid?

### Upgrade Questions

- will this force touching many templates later?
- is backward compatibility needed?

---

## Precision Checks

### If Editing Shared Tables / Lists

Also verify:

- `q`
- `sort`
- `page`

remain consistent across surfaces.

Check:

- shared pagination includes
- empty states
- retained filters after actions

### If Editing Shared Inputs

Also verify:

- select ordering
- grouped options
- caret spacing
- fixed-width classes
- validation states

### If Editing Shared Date / Number Inputs

Also verify:

- enhancement JS hooks
- mobile behavior
- browser fallback behavior

### If Editing Mirrored Cockpit Payloads

Also verify both:

- HTML page rendering
- API endpoint payload

Prefer same shared source under `wms/application/*`.

### If Editing Public Import Surfaces

Also verify:

- package `__init__.py`
- dependent imports
- type checks
- contract tests

---

## Run First

Choose nearest tests.

### High Value

- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`

### API

- nearest tests under `api/tests/`

### Structural

- mypy
- pyright

### Manual Verification Often Needed

- inspect scan page
- inspect portal page
- inspect planning page
- compare API payload with rendered page

---

## Known Traps

### One Surface Break Trap

Shared change tested on scan but breaks portal.

### Silent Payload Drift Trap

API consumers break after field rename.

### Duplicate Logic Trap

Views and API recompute same logic differently.

### CSS Cascade Trap

Minor utility change breaks spacing everywhere.

### Import Trap

Refactor breaks package-root imports used elsewhere.

### Nice Refactor Trap

Cleaner structure but worse compatibility.

---

## Docs To Update

If behavior changed, review:

- `docs/repo-reference/04-shared-contracts.md`
- `docs/repo-reference/02-key-flows-and-living-tests.md`
- relevant UI governance docs

---

## Final Rule

If changing shared UI or API contracts, optimize for consistency, stability, and low blast radius.
