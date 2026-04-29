# Shipment Prepared Without Cartons and Batch Creation Design

## Goal

Allow operators to prepare shipment dossiers and print all required paper and label material before the physical cartons are selected, while preserving stock truth and shipment readiness truth.

## Classification

- Primary: A. ASF operational need
- Secondary: B. generic reusable capability
- Related: C. organization configuration through the existing destination/contact graph

This is a sensitive shipment/document workflow change. The design preserves the current carton, stock, readiness, planning, and tracking contracts.

## Current Behavior

The scan shipment route already supports a definitive shipment dossier with zero real cartons. The limit is that the current `Nombre de colis` input drives line parsing. If an operator enters `10`, the backend expects ten lines, each containing either a prepared carton or a product line.

Printed documents and carton-level labels are derived from real `Carton` rows. With no cartons attached:

- the paper dossier can be opened, but carton count prints as `0`;
- carton-level labels cannot be generated because there are no cartons to iterate;
- the dossier cannot represent "10 cartons planned, 0 cartons selected".

## Decisions

### 1. Separate planned carton count from real cartons

Add a shipment-level planned count, tentatively `Shipment.planned_carton_count`.

Semantics:

- `0` means no separate planned count; current behavior remains derived from real cartons.
- `> 0` means the operator declared a planned shipment size.
- real carton truth remains `shipment.carton_set.count()`.
- operational display uses both values: `10 prevus / 0 associes`, `10 prevus / 6 associes`, or `10 associes` when no planned count exists.

The effective print count is:

```python
max(shipment.planned_carton_count or 0, shipment.carton_set.count())
```

This avoids printing `0` when a shipment is intentionally prepared with planned labels, while still reflecting real carton growth if more cartons are later attached than planned.

### 2. Add an explicit creation mode

The existing `/scan/shipment/` creation flow gets a choice:

- `Preparer avec colis`: current behavior, selecting prepared cartons or creating mono-product cartons.
- `Preparer sans colis`: new behavior, requiring only destination, shipper, recipient, correspondent, and planned carton count.

In `Preparer sans colis` mode:

- no carton lines are parsed;
- no stock is moved;
- no `Carton` row is created;
- the shipment stays in `DRAFT` / `Creation`;
- planning must not treat the shipment as ready;
- confirm-ready remains blocked until real cartons satisfy the existing readiness contract.

### 3. Add a post-create destination choice

For single shipment creation, add a post-create action:

- `Rester sur cette page`
- `Afficher le dossier cree`

When staying on the page, keep the operator's selected mode, destination, shipper, recipient, and correspondent so repetitive creation is fast. Show a success message with the new shipment reference and print/dossier links.

For batch creation, always show a batch summary page because multiple dossiers are created.

### 4. Generate preparatory labels from virtual carton slots

Do not create fake physical cartons. Instead, build virtual print slots for missing planned cartons.

For a shipment with `planned_carton_count=10` and zero real cartons, the print layer generates slots:

- `EXP-2026-0001-P01`
- `EXP-2026-0001-P02`
- ...
- `EXP-2026-0001-P10`

For a shipment with 6 real cartons and `planned_carton_count=10`, the print layer generates:

- 6 real carton slots, preserving real carton codes and data;
- 4 virtual slots for positions 7 to 10.

Virtual slots are only print artifacts. They are not stock, not cartons, and not planning-ready evidence.

### 5. Print bundle behavior

The dossier must support:

- paper dossier: shipment note, customs document, general packing list copies;
- preparatory IATA/destination labels;
- preparatory contact labels;
- donation certificates.

The preparatory label bundle should not claim carton contents when no real carton content is known. The current full `standard_labels` bundle includes carton packing lists; for prepared-without-cartons shipments, add or adapt a dedicated "preparatory labels" bundle that contains only:

- donation certificate;
- IATA/destination label;
- contact label.

When real cartons exist, carton packing lists remain generated from real carton contents through the existing bundle routes.

### 6. Batch creation is a line builder, not a fixed count

Add a batch creation surface where the operator adds shipment lines progressively, then validates the batch.

Each line is independent:

- destination;
- shipper;
- recipient;
- correspondent;
- planned carton count.

The batch flow is intentionally for document-first preparation without real carton selection. The existing single shipment flow remains the safe path for `Preparer avec colis`.

Recommended controls:

- `Ajouter une expedition`
- `Dupliquer cette ligne`
- `Supprimer cette ligne`
- `Valider le batch`

Validation is all-or-nothing. If one line is invalid, no shipment is created and errors are shown per line. This prevents partial hidden work such as "7 dossiers created out of 10".

### 7. Batch summary and grouped print

After successful batch creation, show a summary page listing all created shipment references.

Actions:

- open each dossier;
- print each shipment's paper dossier;
- print each shipment's preparatory labels;
- print all paper dossiers in the batch;
- print all preparatory labels in the batch.

The created IDs may be stored in session for the summary page. Batch print routes should still verify staff permissions and fetch active shipments by ID.

## Data Integrity And Safety

- Do not use fake cartons.
- Do not alter stock.
- Do not move shipment into a ready/planning status from planned count alone.
- Do not let planned count satisfy readiness.
- Do not let planned count appear as actual associated cartons in cockpit lists.
- Make labels visually and semantically tied to the shipment and position, not to a real carton code.
- Keep existing carton attachment/edit rules unchanged.

## User Experience

Single shipment creation remains dense and operator-focused.

Batch creation should be a compact table-like form, optimized for repeated entry. It should support duplicating a previous row because many fields often repeat, while still allowing every row to differ.

The page should avoid explanatory feature prose inside the UI. Labels and controls should be literal and operational.

## Tests

Required coverage:

- form/handler tests for prepared-without-cartons creation;
- handler/view tests for post-create redirect behavior;
- print context tests for effective print count and virtual slots;
- view tests for preparatory label bundles;
- batch service tests for all-or-nothing creation;
- batch view tests for per-line validation and summary actions;
- readiness tests proving planned count alone cannot make a shipment ready;
- scan UI tests for the new controls;
- print view tests for batch paper and label bundles.

## Documentation Impact

Documentation update required.

Update at minimum:

- `templates/scan/faq.html`;
- `wms/faq_changelog.py`;
- `docs/repo-reference/02-key-flows-and-living-tests.md`;
- `docs/repo-reference/03c-impact-shipments.md`;
- `docs/repo-reference/03e-impact-print-documents.md`;
- `docs/repo-reference/04-shared-contracts/05-shipments-tracking.md` if readiness wording needs explicit planned-count exclusion;
- `docs/operations.md` or `docs/release_checklist.md` if smoke instructions mention shipment document-first creation or print bundles.

## Non-Goals

- No fake or empty physical cartons.
- No stock reservation from planned count.
- No Next/React work.
- No translation parity work.
- No redesign of shipment status vocabulary.
- No batch creation with real carton selection in this first pass.
