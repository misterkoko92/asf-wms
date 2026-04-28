# Shipment Impact Map

Use this file when touching any shipment lifecycle behavior.

Read this file for changes involving:

- shipment creation
- shipment edit
- shipment references
- carton attach/detach
- carton states
- shipment status transitions
- shipment tracking
- shipment close flows
- shipment documents
- shipment lists / filters / pagination
- shipments created from portal flows
- shipments created from warehouse preparation runs
- shipment notifications
- shipment permissions / visibility

Shipment logic is core business logic. Small local changes can create broad operational regressions.

---

## Also Read

Depending on the change, also read:

- `03a-impact-scan.md` — internal operational UI
- `03b-impact-portal.md` — partner-created shipment flows
- `03d-impact-parties.md` — shippers / recipients / correspondents
- `03e-impact-print-documents.md` — labels / customs / PDFs
- `03f-impact-planning.md` — planning eligibility / flight allocation
- `03g-impact-shared-ui-api.md` — mirrored API payloads
- `03h-impact-email-events.md` — notifications / async side effects
- `04-shared-contracts.md` — shared list/filter/UI contracts

If unsure, read more than one file.

---

## Critical Invariants

These rules must remain true unless explicitly redesigned.

### Status Separation

- `PICKING` is not `PACKED`
- planning flows must not treat `PICKING` shipments as physically ready
- only explicit confirmation should promote readiness states

### Planning Visibility

`wms/planning/sources.py` must continue excluding non-ready shipments according to current business rules.

### Carton Consistency

- shipment carton counts must match attached cartons
- carton state transitions must remain coherent with shipment state
- detached cartons must not remain counted

### Reference Integrity

- shipment references must remain unique if current contract requires uniqueness
- printed references must match stored references

### Tracking Integrity

- tracking events must remain chronological
- close/completion must not erase prior evidence/history

### Document Integrity

Printed/exported documents must reflect actual shipment state, parties, carton counts, and references.

---

## Always Check

### Runtime Sources

- `wms/views_scan_shipments.py`
- `wms/views_scan_shipments_support.py`
- `wms/scan_shipment_handlers.py`
- `wms/carton_handlers.py`
- `wms/shipment_tracking_handlers.py`
- `wms/services.py`

### API Surfaces

- `api/v1/ui_views.py`
- shipment-related endpoints under `api/v1/`

### Templates

- shipment pages under `templates/scan/`
- tracking templates
- shipment detail/list templates

### Domain Sources

- `wms/models.py`
- `wms/models_domain/shipment.py`
- related domain modules

### Documents

- `wms/shipment_document_handlers.py`
- shipment document routes exposed via scan views / print actions
- see `03e-impact-print-documents.md` for full document surface mapping

---

## Ask Yourself

### Lifecycle Questions

- does creation still work from all supported entrypoints?
- can shipment still be edited in allowed states?
- did any forbidden transition become possible?
- did any valid transition become blocked?

### Carton Questions

- do carton actions still update shipment totals?
- do grouped carton actions still work?
- are lock states still respected?

### Tracking Questions

- do tracking permissions still match current policy?
- do public/private access flows still work?
- do proofs/uploads still work if enabled?

### Cross-Surface Questions

- does portal-created shipment still behave the same?
- does planning still see only eligible shipments?
- do print routes still reflect current state?
- do notifications still trigger exactly when intended?

### UX Questions

- do list filters survive page navigation?
- do users return to the expected list after actions?
- did operator speed regress?

---

## Precision Checks

### If Editing Shipment Lists

Also verify:

- `wms/scan_list_urls.py`
- `wms/templatetags/wms_dates.py`
- `templates/scan/includes/scan_list_pagination.html`
- `04-shared-contracts.md`

### If Editing Bulk Carton Actions

Also verify:

- `scan_carton_picking`
- `scan_cartons_picking`
- `scan_carton_document`
- grouped bundle routes

### If Editing Public Tracking

Also verify:

- `wms/shipment_tracking_access.py`
- `wms/views_shipment_tracking_access.py`
- tracking templates
- recovery/pending emails
- related tests

### If Editing Preparation Conversion

Also verify:

- `wms/preparation/conversion.py`

Confirm accepted proposals still create shipments in:

`PICKING`

not automatically `PACKED`.

---

## Run First

Choose nearest tests.

### Core High Value

- `api/tests/tests_ui_e2e_workflows.py`
- `wms/tests/core/tests_flow.py`

### Shipment Areas

- nearest tests under `wms/tests/shipment/`
- nearest scan shipment tests under `wms/tests/views/`

### If Tracking Changed

- tracking-related tests

### If Docs Changed

- print/document tests

---

## Known Traps

### False Ready Trap

A shipment appears ready to planning before physical confirmation.

### Silent Count Drift

Cartons changed but totals/list badges not updated.

### Portal Divergence

Portal-created shipments follow different validation than internal creation.

### Filter Loss

After action, user loses context and returns to page 1 unfiltered.

### Notification Storm

State transition now triggers duplicate emails/events.

### Document Drift

Printed customs or packing docs no longer match runtime truth.

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

If changing shipments, assume at least one other surface is impacted until proven otherwise.
