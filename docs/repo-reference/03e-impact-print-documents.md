# Print & Documents Impact Map

Use this file when touching any printable output, generated document, label flow, customs paperwork, PDF export, or document delivery route.

Read this file for changes involving:

- shipment labels
- carton labels
- A4 labels
- continuous-roll labels
- packing lists
- customs documents
- shipment notes
- billing documents
- PDF generation
- HTML print templates
- grouped print bundles
- downloadable files
- print actions from scan/admin/planning
- template editors
- artifact exports linked to planning

Document bugs often remain invisible until operational use. Precision matters.

---

## Also Read

Depending on the change, also read:

- `03c-impact-shipments.md` — shipment references / carton truth
- `03d-impact-parties.md` — names / addresses / actor data
- `03f-impact-planning.md` — planning exports / packs
- `03a-impact-scan.md` — print actions from internal UI
- `03g-impact-shared-ui-api.md` — API delivery routes
- `04-shared-contracts.md` — shared formatting / list contracts

If unsure, read more than one file.

---

## Critical Invariants

These rules must remain true unless explicitly redesigned.

### Truth Integrity

Printed data must match current canonical runtime data.

### Reference Integrity

Shipment/carton references on documents must match system references.

### Layout Integrity

Operational templates must remain printable in their intended format.

### Regulatory Integrity

Customs and billing documents must not silently lose required fields.

### Bundle Integrity

Grouped print actions must preserve expected ordering and included documents.

---

## Always Check

### Runtime Sources

- `wms/shipment_document_handlers.py`
- `wms/billing_document_handlers.py`
- scan/admin print routes re-exported through `wms/views.py`

### Templates

- `templates/print/`
- `templates/scan/print_template_*`

### Planning Artifacts

- `wms/artifacts/*`
- planning export routes if linked

### API Surfaces

- `api/v1/ui_views.py` document/template endpoints

### Tests

- `wms/tests/print/`

---

## Ask Yourself

### Truth Questions

- does the document reflect current shipment/carton state?
- are names / addresses current?
- are quantities correct?

### Layout Questions

- does it still print on intended paper size?
- did spacing break after content changes?
- do long names overflow badly?

### Workflow Questions

- is the same document reachable from all intended entrypoints?
- did one route diverge from another?
- are grouped actions still coherent?

### Operational Questions

- can staff print quickly without manual cleanup?
- would customs or partners understand it?
- would users trust the output?

### Compatibility Questions

- do downloaded filenames remain usable?
- do browser print flows still work?
- does PDF conversion still work?

---

## Precision Checks

### If Editing Shipment Paper Bundle

Also verify expected order remains:

`shipment_note -> customs -> packing_list_shipment x2`

### If Editing Standard Labels

Also verify current meaning remains:

one `A4` page per carton with blocks:

- donation
- shipment label
- contact label
- carton packing list

### If Editing Carton Lists

Distinguish:

- continuous-roll action page: `carton_lists`
- direct printable A4 surface: `carton_lists_a4`

Do not confuse the two.

### If Editing Shared Party Fields

Also verify:

- addresses
- phone/email if used
- multilingual labels if present
- customs identifiers if used

### If Editing Planning Exports

Also verify:

- selected version truth
- filenames
- attached proofs
- pack completeness

---

## Run First

Choose nearest tests.

### High Value

- nearest tests under `wms/tests/print/`

### Cross Flow

- shipment tests if references changed
- planning tests if export packs changed
- E2E tests if user-facing routes changed

### Manual Verification Often Needed

- open generated PDF
- browser print preview
- sample long-name scenario
- sample multi-carton scenario

---

## Known Traps

### Pretty But False Trap

Template looks nicer but data is wrong.

### Overflow Trap

Long names/addresses break layout.

### Silent Missing Field Trap

Customs/billing field disappears unnoticed.

### Route Drift Trap

Scan route and admin route generate different outputs.

### Wrong Bundle Trap

Grouped print action misses one required document.

### Filename Chaos Trap

Users download multiple files with unusable names.

---

## Docs To Update

If behavior changed, review:

- `docs/mvp_spec.md`
- `docs/operations.md`
- `docs/release_checklist.md`
- `docs/repo-reference/02-key-flows-and-living-tests.md`

---

## Final Rule

If changing documents, optimize for truth, printability, and operational usability — not visual elegance alone.
