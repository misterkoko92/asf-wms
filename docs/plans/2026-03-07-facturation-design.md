# Facturation Design

## Context

ASF WMS needs a new legacy Django billing area for quotes and invoices driven from shipments, association receipts, configurable pricing rules, and an existing XLSX-to-PDF document pipeline.

The requested back-office entry point is a new scan tab `Facturation` with three pages:
- `Parametres`
- `Equivalence`
- `Edition Devis/Facture`

The portal scope for V1 is read-only consultation of issued documents, detailed transparency, correction requests, and billing preference change requests that require superuser approval.

## Validated Decisions

- V1 lives on the legacy Django stack only.
- Billing starts in scan/back-office; the portal is consultation-only in V1.
- A possible V2 may expose more self-service portal actions.
- A shipment becomes billable when it reaches `ShipmentStatus.SHIPPED`.
- Billing units use a mixed base:
  - standard `MM` and `CN` cartons default to `1 carton = 1 unit`
  - hors format uses dedicated equivalence rules
- The mixed base and the default formulas must remain configurable without code changes.
- By default the billed entity is the shipment shipper association, with per-document override.
- Per association, billing can be:
  - by shipment
  - aggregated by month / quarter / half-year / year
  - either as one aggregated document or as multiple per-shipment documents
- Pickup billing is stored directly on the association receipt in V1.
- Quotes and invoices are mixed-mode:
  - quotes can be created directly
  - invoices can be created directly
  - a quote can be converted into an invoice
- VAT is out of scope for V1 documents; the legal wording is already handled in the XLSX template.
- Quote numbering is automatic: `DEV-YYYY-####`.
- Invoice numbering is fully manual and required before issue.
- Period grouping uses the shipment date, not creation date or billing date.
- A shipment may appear in multiple quotes, but only one final invoice.
- Exchange rates are frozen at final edition time, not at draft creation time.
- Invoice payment tracking must support multiple payments and partial settlements.
- Portal users can see issued documents with line-level detail and can request corrections.
- Billing periodicity/regrouping changes can be requested from the portal but require superuser approval.
- Services use a configurable catalog with optional free manual lines and ad hoc discounts.
- When receipts are linked, the default formula is:
  - `75 EUR per started block of 10 allocated received units`
  - `+10 EUR per shipped unit above allocated received units`
  - the document can still override the formula case by case
- Documents become visible in the portal only after issue.
- For invoice corrections after issue, the flow is `credit/cancellation + new invoice`, never in-place replacement.
- Payment entries must store amount, date, payment method, reference, comment, and optional proof attachment.
- The new scan tab should expose:
  - a main access entry in scan navigation
  - three internal pages for parameters, equivalence, and editor
- Access rules:
  - superuser: `Parametres`, `Equivalence`, preference approval
  - dedicated billing staff: `Edition Devis/Facture`
- Global pricing exists, with optional per-association overrides.
- Document output is PDF only in V1, but regenerable.
- Quotes are recalculable by version; issued invoices are frozen and corrected through credit/new invoice flows.
- Association receipts are always mono-association.
- Receipt-to-shipment linking is many-to-many.
- The link must store allocated received units per receipt/shipment pair.
- Supported currencies for V1:
  - `EUR`, `USD`, `CHF`, `CNY` with automatic ECB prefill when available
  - `VND`, `XOF`, `XAF` with manual rate entry

## Existing Integration Points

- `wms.models_domain.inventory.Receipt` already stores association receipt data (`source_contact`, `carrier_contact`, `received_on`, carton counts, hors format counts).
- `wms.models_domain.shipment.Shipment` remains the logistics source of truth for shipped documents.
- `wms.models_domain.portal.AssociationProfile` already anchors the association portal identity.
- `templates/portal/account.html` and `wms/views_portal_account.py` already handle billing contacts (`is_billing`).
- `wms/print_pack_engine.py`, `wms/print_context.py`, `wms/print_pack_mapping_catalog.py`, and `wms/views_print_templates.py` already provide the XLSX mapping and PDF conversion pipeline to reuse.

The billing feature should plug into these existing aggregates rather than duplicating them.

## Scope V1

### Back-Office

- New scan tab `Facturation`
- Internal pages:
  - `Parametres`
  - `Equivalence`
  - `Edition Devis/Facture`
- Quote/invoice draft creation
- Quote-to-invoice conversion
- Shipment and receipt linking
- Configurable rule-driven calculation
- Manual service lines and discounts
- Manual invoice numbering
- PDF generation and regeneration
- Multi-payment tracking
- Credit/correction workflow

### Portal

- Billing document list page
- Billing document detail page
- Visibility only for issued documents
- Correction request submission
- Billing preference change request submission

### Receipt Flow

- Extend association receipt metadata with:
  - pickup amount
  - pickup currency
  - pickup comment
  - pickup attachment
- Add explicit receipt-to-shipment allocation records with allocated received units

## Non-Goals V1

- Portal self-service quote/invoice creation
- Fully automatic periodic draft generation
- Automatic issue without staff validation
- VAT rules by line or by document
- Replacing the existing template mapping UI
- Next/React migration work

## Target Architecture

### New Domain Module

Create a dedicated billing aggregate in `wms/models_domain/billing.py`, exposed through `wms/models.py`.

Recommended support modules:
- `wms/forms_billing.py`
- `wms/billing_permissions.py`
- `wms/billing_calculations.py`
- `wms/billing_exchange_rates.py`
- `wms/billing_document_handlers.py`
- `wms/views_scan_billing.py`
- `wms/views_portal_billing.py`

### Reused Rendering Stack

Billing documents should reuse the existing print-pack/template infrastructure rather than introducing a second renderer. The billing tab owns pricing/formulas and document composition. XLSX field mapping remains handled by the existing template tooling, extended with billing document contexts and source keys.

### Configuration-First Rule Engine

The pricing base, unit computation defaults, and receipt-linked formula must be stored as editable records, not hardcoded branches.

Recommended strategy:
- one configurable default profile for shipment-only billing
- one configurable default profile for receipt-linked billing
- optional per-association override profile selection
- document-level override snapshot when drafting/issuing

## Proposed Data Model

### `AssociationBillingProfile`

One-to-one with `AssociationProfile`.

Stores:
- billing frequency
- grouping mode
- document currency default
- default computation profile overrides
- optional billing identity override fields
- portal visibility preferences if needed later

### `AssociationBillingChangeRequest`

Tracks portal requests for billing preference changes.

Stores:
- association
- requested frequency
- requested grouping mode
- requested by / requested at
- status (`pending`, `approved`, `rejected`)
- reviewed by / reviewed at
- review comment

### `BillingComputationProfile`

Editable computation rules used by the billing editor.

Stores:
- code / label
- active flag
- applies when receipts linked or not
- base unit source (`shipped_units`, `allocated_received_units`, `manual`)
- base step size
- base step price
- extra unit mode (`none`, `shipped_minus_allocated_received`, `manual`)
- extra unit price
- allow manual override flag
- default flags

This model is the core answer to the requirement that the mixed base and default formula remain configurable without code.

### `ShipmentUnitEquivalenceRule`

Editable unit conversion rules.

Stores:
- label
- active flag
- applies to `standard_carton` or `hors_format`
- root category reference
- category depth to match
- units per item
- priority
- optional notes

The most specific active rule wins; ties fall back to priority and then creation order.

### `BillingServiceCatalogItem`

Editable service and discount catalog.

Stores:
- label
- description
- service type
- default unit price
- default currency
- is_discount
- active flag
- display order

### `BillingAssociationPriceOverride`

Optional per-association price exceptions.

Stores:
- association billing profile
- overridden service/computation profile field
- overridden amount
- effective dates
- notes

### `ReceiptShipmentAllocation`

Explicit association receipt <-> shipment link.

Stores:
- receipt
- shipment
- allocated received units
- optional note
- created by / created at

Constraints:
- unique per receipt/shipment pair
- all receipts linked to a shipment must belong to the same association contact

### `BillingDocument`

Common commercial document model.

Stores:
- document kind (`quote`, `invoice`, `credit_note`)
- status
- quote number / invoice number
- association profile
- billed identity snapshot
- document currency
- exchange-rate snapshot fields
- computation profile snapshot
- totals
- issued at / issued by
- visible in portal flag
- parent/previous document references for replacement or correction chains
- portal correction state

### `BillingDocumentShipment`

Links billing documents to shipments, keeping transparency and invoice exclusivity checks.

Stores:
- billing document
- shipment
- shipment date snapshot
- carton count snapshot
- reference snapshot

### `BillingDocumentReceipt`

Links billing documents to association receipts used for pickup billing or receipt-linked calculations.

Stores:
- billing document
- receipt
- pickup charge inclusion flags / snapshots

### `BillingDocumentLine`

Detailed billable lines.

Stores:
- billing document
- line kind (`base`, `extra_units`, `service`, `discount`, `manual`, `pickup`)
- label
- quantity
- unit price
- amount
- source metadata
- display order

### `BillingPayment`

Invoice settlement records.

Stores:
- invoice
- amount
- payment date
- payment method
- reference
- comment
- proof attachment

### `BillingIssue`

Tracks correction requests and staff review trail.

Stores:
- document
- source (`portal`, `staff`)
- status (`open`, `in_review`, `resolved`, `rejected`)
- message
- resolution note
- created by / created at
- resolved by / resolved at

## Workflow

### Quote

- `draft`
- `issued`
- `disputed`
- `replaced`

Quotes are auto-numbered and can be regenerated through new versions or re-issue flows.

### Invoice

- `draft`
- `ready_to_issue`
- `issued`
- `partially_paid`
- `paid`
- `disputed`
- `cancelled_or_corrected`

Invoices require a manual number before issue. Once issued, shipment exclusivity is enforced.

### Credit / Correction

- A corrected issued invoice never mutates in place.
- The system produces a correction chain:
  - credit or cancellation document
  - optional replacement invoice

### Payments

- Multiple payments are allowed.
- Invoice status derives from the remaining balance.

### Portal Visibility

- Only issued documents are visible.
- Drafts remain internal.
- Portal users can request corrections, which creates a `BillingIssue` and moves the document into a review state.

## Calculation Rules

### Default Shipment-Only Mode

- Apply only when shipper is not `Aviation Sans Frontieres`
- Base computation uses a configurable default profile, initially intended to represent `75 EUR per started block of 10 shipped units`

### Default Receipt-Linked Mode

- Base computation profile defaults to:
  - `75 EUR per started block of 10 allocated received units`
  - `+10 EUR per shipped unit above allocated received units`
- The exact numbers and unit source remain editable records in `BillingComputationProfile`

### Unit Resolution

- Standard cartons from `MM` and `CN` default to `1 carton = 1 unit`
- Hors format uses dedicated equivalence rules
- Product category depth matching is configurable
- The editor should expose the resolved unit total and the rule used

### Manual Overrides

- The editor can override:
  - billed identity
  - computation profile
  - received-unit baseline when needed
  - exchange rate
  - services and discounts

Manual overrides must be visible in the final line details and preserved in document snapshots.

## Screens And Permissions

### Scan Navigation

Add a new top-level scan nav entry `Facturation`, separate from the paused Next scope.

Inside the billing shell, expose:
- `Parametres`
- `Equivalence`
- `Edition Devis/Facture`

### `Parametres`

Superuser only.

Includes:
- computation profiles
- service catalog
- association-level price overrides
- supported currencies
- exchange-rate source settings
- default association billing preferences review

### `Equivalence`

Superuser only.

Includes:
- unit equivalence rules
- hors format rules
- priority and matching previews

### `Edition Devis/Facture`

Billing staff group + superuser.

Includes:
- association selector
- document type selector
- shipment-period selector
- eligible shipment list
- receipt allocation visibility
- draft line builder
- discounts/services/manual lines
- manual invoice number field
- PDF generation and regeneration
- quote-to-invoice conversion
- payment capture for invoices
- correction/credit workflow entry points

### Portal

Add a `Facturation` nav entry in the portal.

Pages:
- billing document list
- billing detail

Keep billing preference change requests on either the account page or the billing area, but the request must be explicit and approval-based.

## Exchange Rates

- `EUR`, `USD`, `CHF`, `CNY`: automatic prefill from the ECB when available
- `VND`, `XOF`, `XAF`: manual entry in V1
- At issue time, freeze:
  - source
  - fetch timestamp
  - source currency
  - document currency
  - effective rate

If automatic fetch fails or is unavailable, the editor must allow manual fallback without blocking the draft.

## Document Rendering

- Output is PDF only in V1.
- Generation should reuse the existing XLSX mapping and PDF conversion pipeline.
- Billing-specific print contexts and mapping keys must be added for:
  - quote
  - invoice
  - credit note
- Regeneration means:
  - quote: new rendered output from the current draft/version
  - invoice: rendered output from the frozen issued snapshot

## Risks And Assumptions

- Many-to-many receipt/shipment linking is necessary; pretending it is one-to-one would break common business cases.
- Formula configurability can drift if the UI is too generic; the parameter page should expose safe constrained options rather than arbitrary scripting.
- Portal correction requests require a clear review workflow to avoid silent re-issues.
- The existing template system likely needs new billing source keys; this should be an extension, not a parallel template engine.
- Billing staff permissions should be group-based and explicit instead of granting all staff access.

## Rollout Notes

- Start with manual assisted draft creation for all periodic modes.
- Use the current XLSX template editor for billing document mapping instead of building a second mapping UI.
- Add focused legacy Django tests before any implementation branches.
- Execute implementation in an isolated worktree once coding starts.
