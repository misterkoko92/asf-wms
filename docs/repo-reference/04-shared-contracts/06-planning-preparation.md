# Planning, Artifacts, And Warehouse Preparation Contracts

Read this file when touching planning cockpit, planning exports, PDF/workbook artifacts, warehouse preparation runs, recipient-preference-driven preparation, or planning eligibility.

---

## Planning Flight Capacity Cockpit Contract

### Primary runtime sources

- `wms/application/planning/version_detail_queries.py`
- `wms/planning/stats.py`
- `wms/planning/version_dashboard.py`
- `wms/planning/artifact_health.py`
- planning templates

### Current contract

- `version_detail_queries.py` is shared GET composition layer for `planning/version_detail`.
- `flight_load_breakdown[]` is flight-capacity source of truth.
- One row represents one `PlanningFlightSnapshot`.
- Load-state thresholds:
  - `ok` when `< 80%`
  - `tension` when `>= 80% and < 95%`
  - `critical` when `>= 95% and <= 100%`
  - `overload` when `> 100%`
- Missing capacity uses `load_state=unknown`.
- Cockpit order remains: `header -> priorities -> section nav -> planning capacity -> planning by flight -> secondary details`.

### Maintenance rule

- If thresholds, row fields, cockpit ordering, exports, or artifact health change, update helpers, templates, tests, and repo-reference.
- Keep views thin over shared application query layer.
- Keep load-state rules in policies.

---

## Artifacts Boundary Contract

### Primary runtime sources

- `wms/artifacts/planning.py`
- `wms/artifacts/attachments.py`
- `wms/artifacts/proofs.py`
- `wms/application/planning_artifacts/use_cases.py`
- `wms/print_artifact_delivery.py`
- `wms/planning/exports.py`
- `wms/planning/communication_actions.py`
- print/admin compatibility views
- `wms/print_pack_sync.py`
- `wms/jobs/print_artifacts.py`

### Current contract

- `wms/artifacts/planning.py` owns workbook/PDF orchestration and artifact metadata.
- `wms/planning/exports.py` remains compatibility adapter.
- `wms/artifacts/attachments.py` owns attachment resolution and PDF readiness/blocking semantics.
- `wms/application/planning_artifacts/use_cases.py` is application entrypoint.
- `wms/artifacts/proofs.py` owns proof-path payloads.
- `wms/print_artifact_delivery.py` owns shared delivery/runtime behavior.
- `print_pack_sync.py` keeps transport/retry behavior.
- Print artifact job persists bounded `proof_sync_preview`.

### Maintenance rule

- Update artifact modules first, keep adapters thin.
- If job summaries change, update jobs, runtime tracking, ops docs, and this contract.

---

## Warehouse Preparation Create Contract

### Primary runtime sources

- `wms/forms_preparation.py`
- `wms/views_scan_preparation.py`
- preparation templates

### Current contract

- Flight-window fields use native date inputs.
- Default operational targets remain explicit.
- Flight window starts Monday of `S+1` or `S+2` depending on launch day.
- Scopes expose `Tout sélectionner` and default to active options.
- Parameter set defaults to last run used by operator, then latest current set.
- Destination rules live in `PreparationDestinationRule`, not planning-vols rules.
- Destination weekdays use native multi-select.
- If flight acquisition fails and no fallback batch exists, form stays with non-field error and no orphan run.

### Maintenance rule

- Keep forms, views, templates, and tests aligned if defaults or settings behavior changes.

---

## Warehouse Preparation And Recipient Preference Contract

### Primary runtime sources

- `wms/models_domain/preparation.py`
- `wms/models_domain/shipment_parties.py`
- `wms/recipient_product_preferences.py`
- `wms/preparation/needs.py`
- `wms/preparation/reservations.py`
- `wms/preparation/candidates.py`
- `wms/preparation/scoring.py`
- `wms/preparation/conversion.py`

### Current contract

- `planning vols` and warehouse `run magasin` remain separate domains.
- Preparation state must not be folded into `wms/models_domain/planning.py`.
- Preferences live on `RecipientProductPreference`, scoped by `ShipmentRecipientOrganization`.
- Resolution order: `product -> most specific category -> unspecified`.
- Category `requested`/`allowed` supported; category `refused` invalid.
- Run snapshots freeze recurring need data.
- Reservations own lot-level `quantity_reserved`.
- Conversion is explicit.
- Conversion creates shipments in `PICKING`, not `PACKED`.
- Promotion to `PACKED` is later explicit shipment-dossier action.

### Maintenance rule

- If preference, run state, fairness, reservation, snapshot, or conversion semantics change, keep preparation modules, shipment-party modules, tests, and this section aligned.
