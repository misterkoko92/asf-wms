# Deferred Follow-Ups

Use this file to record improvements that were explicitly discussed, judged valuable, and intentionally deferred.

This is not the product roadmap and not a dumping ground for vague ideas.

Add an entry here when:

- a change was considered during active work,
- the team explicitly decided not to implement it now,
- reopening it later would benefit from preserving context, scope, and rationale.

Do not add entries for:

- generic future ideas without a concrete decision,
- already tracked roadmap items that belong in `docs/backlog.md`,
- minor implementation notes that remain local to one design or implementation plan.

## Entry format

For each deferred follow-up, capture:

- date of the decision,
- current surface or flow,
- deferred change,
- why it was deferred now,
- estimated cost / risk if already discussed,
- trigger to reopen,
- canonical references.

## Deferred items

### 2026-03-28 - Carton double-status model

- Surface: legacy scan carton flow (`/scan/cartons/`, carton detail, shipment assignment/tracking, dashboard, UI API).
- Deferred change: replace the current single `Carton.status` contract with two real axes:
  - preparation status: `Créé`, `En préparation`, `Prêt`
  - assignment/shipment status: `Libre`, `Affecté`, `Étiqueté`, `Expédié`
- Decision for now: keep the lightweight UI approach only. Do not change the data model in the current carton-view simplification sequence.
- Why deferred now:
  - current codebase uses one canonical `Carton.status` field across stock, shipment assignment, tracking, dashboard, and UI API
  - a proper split requires migration/backfill and cross-surface refactoring
  - the current need is readability in `Vue Colis`, not a full workflow contract rewrite
- Estimated cost if reopened: about 4 to 7 developer days, plus 1 to 2 days of QA/regression checks
- Main risks if reopened:
  - breaking shipment readiness/progress rules that currently depend on carton status aggregation
  - incorrect backfill for existing cartons when reconstructing the preparation axis
  - divergence between legacy scan HTML, dashboard, and UI API if one surface remains on the old contract
- Trigger to reopen:
  - business wants combinations such as `En préparation + Affecté` to become real workflow states across the product, not just a display hint
  - assignment and preparation need to evolve independently in handlers, dashboards, APIs, or tracking rules
- Canonical references:
  - `wms/models_domain/shipment.py`
  - `wms/shipment_status.py`
  - `wms/scan_shipment_handlers.py`
  - `wms/carton_handlers.py`
  - `api/v1/ui_views.py`
  - `docs/plans/2026-03-28-carton-view-bulk-actions-design.md`
  - `docs/plans/2026-03-28-carton-view-bulk-actions-implementation-plan.md`
