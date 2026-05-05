# UI, Shell, Asset, And Frontend Security Contracts

Read this file when touching shared UI primitives, shells, base templates, scan/portal/planning CSS/JS, shared input controls, frontend security, or service-worker cache behavior.

---

## Shared UI Contract

### Primary runtime sources

- `wms/templatetags/wms_ui.py`
- `templates/wms/components/`
- `templates/scan/ui_lab.html`
- `wms/static/scan/scan-bootstrap.css`
- `wms/static/portal/portal-bootstrap.css`
- `wms/static/wms/admin-bootstrap.css`

### Current contract

Stable primitives include:

- `ui_button`
- `ui_field`
- `ui_file_input`
- `ui_alert`
- `ui_status_badge`
- `ui_switch`
- `ui-number-input`
- `ui-date-input`
- `ui-comp-card`
- `ui-comp-panel`
- `ui-comp-actions`
- shared select contract: `form-select` + `ui-select--sm|md|lg|xl`
- shared masthead history navigation include: `templates/includes/history_nav_buttons.html`

Surfaces that reuse these contracts:

- `templates/scan/`
- `templates/portal/`
- `templates/planning/`
- `templates/benevole/`
- custom admin templates
- `templates/scan/ui_lab.html`

### Maintenance rule

- If a primitive changes semantics, update UI Lab and bootstrap regression tests.
- If shared select contract changes, keep `wms/view_utils.py`, form/widget sorting, and scan/portal/planning/benevole select templates aligned.
- If a pattern is local, do not prematurely promote it into a shared primitive.

### Reference tests

- `wms/tests/views/tests_scan_bootstrap_ui.py`
- `wms/tests/views/tests_portal_bootstrap_ui.py`

---

## Shared Shell Contract

### Primary runtime sources

- `templates/scan/base.html`
- `templates/portal/base.html`
- `templates/planning/base.html`
- `templates/benevole/base.html`
- `templates/includes/secondary_shell_masthead.html`
- `templates/includes/secondary_shell_offcanvas.html`
- `templates/portal/includes/onboarding_wizard.html`
- `wms/static/portal/portal_onboarding.js`

### Current contract

- Scan, portal, planning, and benevole shells load shared scan bootstrap CSS.
- Page-level horizontal overflow must be blocked on mobile.
- Wide tables and dense matrices keep horizontal scroll inside local wrappers.
- Portal, planning, and benevole secondary shells reuse shared secondary-shell masthead/offcanvas includes.
- Portal scoped pages render the onboarding wizard through `templates/portal/base.html`; the `Tutoriel` masthead link falls back to `/portal/faq/` without JavaScript.
- `wms/static/portal/portal_onboarding.js` owns portal tutorial open/close, step navigation, and preference persistence.
- Planning keeps legacy scan sidebar content but injects it through shared secondary-shell offcanvas.
- Scan-camera controls must preserve active scan targets when switching cameras, stop live ZXing controls before restart, and ignore stale callbacks.
- OCR activation is disabled until OCR engine assets are self-hosted and covered by CSP, cache, and regression-test updates.

### Maintenance rule

- If secondary shell structure changes, update shared includes, base templates, and bootstrap/view tests together.
- If shared masthead history navigation changes, keep scan/portal/planning/benevole shells aligned.
- If portal onboarding shell behavior changes, keep `wms/application/portal/onboarding.py`, the preference endpoint, modal template, static asset, FAQ, and portal tests aligned.

---

## Shared Select Contract

### Primary runtime sources

- `wms/view_utils.py`
- `wms/forms.py`
- `wms/static/scan/scan-bootstrap.css`
- `templates/scan/ui_lab.html`
- manual select templates under scan, portal, planning, benevole

### Current contract

- Selects use native `<select>` controls with `form-select`.
- Fixed widths use `ui-select--sm`, `ui-select--md`, `ui-select--lg`, or `ui-select--xl`.
- Right-side caret spacing is provided by shared CSS.
- Select widths stay stable and do not resize based on selected label.
- Default ordering is alphabetical by rendered label.
- Placeholder options such as `---------` stay at the top.
- Grouped choices keep groups while sorting options inside each group.
- Explicit exceptions are allowed when business order matters.
- `scan/pack` uses descending shipment references with labels formatted as `REFERENCE - IATA`.

### Maintenance rule

- When changing select ordering or sizing, update backend choice builders and rendered template/widget classes together.
- Keep documented exceptions explicit and local.

---

## Shared Number Input Contract

### Primary runtime sources

- `wms/static/scan/modules/core.js`
- `wms/static/scan/scan-bootstrap.css`
- `templates/scan/ui_lab.html`
- base templates for scan, portal, planning, benevole

### Current contract

- Eligible legacy `input[type="number"]` controls can be enhanced into `ui-number-input`.
- Shared controls render compact decrement/increment buttons on the left.
- Runtime respects native `min`, `max`, `step`, `disabled`, and `readonly`.
- Enhancement dispatches native-feeling `input` and `change` events.
- Tight contexts can opt into `ui-number-input-compact`.
- Local exceptions can opt out with `data-ui-number-input-optout="1"` or `ui-number-input-optout`.

### Maintenance rule

- If number-input behavior changes, update shared JS, CSS, base template includes, UI Lab, and runtime tests together.

---

## Shared Date Input Contract

### Primary runtime sources

- `wms/static/scan/modules/core.js`
- `wms/static/scan/scan-bootstrap.css`
- base templates for scan, portal, planning, benevole

### Current contract

- Eligible legacy `input[type="date"]` controls can be enhanced into `ui-date-input`.
- Enhanced field keeps native date input and adds shared `Calendrier` action.
- If browser exposes native picker, action calls `showPicker()`.
- Otherwise it opens shared calendar implemented in `core.js`.
- Dynamically rendered date fields dispatch `wms:enhance-date-inputs`.
- Local exceptions can opt out with `data-ui-date-input-optout="1"` or `ui-date-input-optout`.

### Maintenance rule

- If date-input behavior changes, update shared JS, CSS, base template includes, and bootstrap regression tests.

---

## Legacy Scan Asset Facade Contract

### Primary runtime sources

- `templates/scan/base.html`
- `templates/portal/base.html`
- `templates/planning/base.html`
- `wms/static/scan/scan.js`
- `wms/static/scan/scan.css`
- `wms/static/scan/scan-bootstrap.css`
- `wms/static/scan/modules/table-tools.js`
- `wms/static/scan/modules/`
- `wms/static/scan/css/partials/`

### Current contract

- `scan.js`, `scan.css`, and `scan-bootstrap.css` remain stable shared filenames consumed by scan, portal, planning, and public/auth surfaces.
- `templates/scan/base.html` keeps `scan.js` plus `scan/modules/core.js` as shared scan script facade.
- Scan and portal preload `scan/modules/table-tools.js` before page-specific table tooling.
- Page-local scan scripts extend through `extra_scripts`.
- First JS slices include `core.js`, `dashboard.js`, `shipments.js`, `table-tools.js`.
- First CSS partials include `foundation.css`, `ops.css`, `auth-public.css`.

### Maintenance rule

- Keep stable entrypoint filenames unless consuming templates and bootstrap regression tests move together.
- If scan and portal share table sort/filter parsing, keep it in `table-tools.js`.

---

## Frontend Security Contract

### Primary runtime sources

- `asf_wms/settings.py`
- `wms/security_headers.py`
- scan, portal, planning, benevole templates
- `wms/static/scan/`

### Current contract

- Responses include `Content-Security-Policy-Report-Only` by default.
- `CSP_REPORT_ONLY_ENABLED` disables it only by explicit environment choice.
- `CONTENT_SECURITY_POLICY_REPORT_ONLY` overrides maintained default policy.
- Default `connect-src` allows same-origin requests, Nominatim address lookup, and the local helper endpoint `http://127.0.0.1:38555`.
- Stable third-party JS/CSS assets must be self-hosted or include SRI plus `crossorigin`.
- Dormant OCR paths must fail closed; future OCR activation must not load engine, worker, WASM, or language assets from a CDN.
- New `target="_blank"` links/forms must include `rel` with `noopener`.
- User/server data must not be assembled into dynamic HTML strings when DOM APIs can express the same change.

### Maintenance rule

- If frontend assets, shared templates, CDN imports, or security headers change, update security tests, operations docs, and release checklist.

---

## Shared Scan Frontend Cache Contract

### Primary runtime sources

- `wms/views_scan_misc.py`
- `templates/scan/base.html`
- `docs/release_checklist.md`

### Current contract

- Legacy scan shell registers versioned service worker URL under `/scan/service-worker.js?v=NN`.
- Served worker uses same version in `CACHE_NAME = wms-scan-vNN`.
- Worker caches shared scan assets including `scan.css`, `scan-bootstrap.css`, `scan.js`, `modules/core.js`, manifest, and icon.

### Maintenance rule

- If shared scan frontend asset changes can leave stale styles/scripts, bump both `SCAN_SERVICE_WORKER_VERSION` and the registration query string.
- Do not rely on hard refresh as primary invalidation path.
