# W2.2 SLA Alerts Implementation Plan

**Goal:** add actionable SLA delay alerts to the local legacy scan dashboard, keep runtime tuning local and lightweight, and mirror the same contract through the UI API without introducing a dedicated alert model.

**Architecture:** compute alert rows from shipment tracking timestamps at read time. Keep the existing aggregate SLA cards and add a second layer of operational rows plus summary cards. Share the computation across dashboard HTML, settings impact preview, and the UI API through a small helper module instead of duplicating logic three times.

**Tech Stack:** Django legacy views/templates, shared helper in `wms/`, runtime settings view, UI API, Django tests under `wms/tests/views` and `api/tests`, repo-reference docs.

---

### Task 1: Lock The W2.2 Design In Docs

**Files:**
- Create: `docs/plans/2026-03-31-w22-sla-alerts-design.md`
- Create: `docs/plans/2026-03-31-w22-sla-alerts-implementation-plan.md`
- Inspect: `docs/plans/2026-03-31-pilotage-flux-roadmap.md`
- Inspect: `docs/repo-reference/03-impact-map.md`

Document:
- local-only scope,
- severity thresholds derived from `tracking_alert_hours`,
- panel and API contracts,
- limited runtime preset strategy.

### Task 2: Add The First Failing Dashboard Tests

**Files:**
- Modify: `wms/tests/views/tests_views_scan_dashboard.py`
- Reference: `wms/views_scan_dashboard.py`
- Reference: `templates/scan/dashboard.html`

Add failing tests covering:
- `sla_alert_summary_cards` is exposed with `new`, `persistent`, `critical` counts,
- `sla_alert_rows` exposes the right shipment references, segment labels, owner, severity, delay and url,
- the dashboard renders `Alertes SLA`,
- the action queue promotes SLA alerts ahead of lower-priority stock or order items.

Run the targeted tests and verify RED before implementation.

### Task 3: Add The First Failing Settings Tests

**Files:**
- Modify: `wms/tests/views/tests_views_scan_settings.py`
- Reference: `wms/views_scan_settings.py`
- Reference: `templates/scan/settings.html`

Add failing tests covering:
- `incident_sla` preset pre-fills the tighter SLA thresholds,
- preview impact exposes `sla_new_delay_count`, `sla_persistent_delay_count`, `sla_critical_delay_count`.

Run the targeted tests and verify RED.

### Task 4: Add The First Failing UI API Tests

**Files:**
- Modify: `api/tests/tests_ui_endpoints.py`
- Reference: `api/v1/ui_views.py`

Add failing tests covering:
- payload includes `sla_alert_summary_cards`,
- payload includes `sla_alert_rows`,
- rows expose `segment`, `severity`, `freshness`, `delay_hours`, `age_hours`, `url`.

Run the targeted API test and verify RED.

### Task 5: Implement Shared SLA Helper

**Files:**
- Create: `wms/scan_dashboard_sla.py`

Add:
- tracking-date annotation helper,
- aggregate SLA row builder,
- open SLA alert row builder,
- summary-card builder for `new / persistent / critical`,
- small helper for owner and segment labels.

Keep the module read-only and query-focused. No persistence layer.

### Task 6: Wire Dashboard And Settings

**Files:**
- Modify: `wms/views_scan_dashboard.py`
- Modify: `templates/scan/dashboard.html`
- Modify: `wms/views_scan_settings.py`

Implement:
- dashboard summary cards and rows,
- action queue promotion,
- `incident_sla` preset,
- settings impact preview counts.

### Task 7: Wire The UI API Mirror

**Files:**
- Modify: `api/v1/ui_views.py`

Implement:
- same helper-driven SLA summary cards,
- same helper-driven SLA rows,
- keep `pending_actions[]` contract stable while injecting SLA actions only as regular prioritized actions.

### Task 8: Verify, Update Docs, Commit

**Files:**
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Modify: `docs/operations.md`

Verification:
- targeted dashboard, settings, and API tests,
- `uv run ruff check` on touched Python files,
- manual smoke on local dashboard and settings pages while keeping the existing dev server alive.
