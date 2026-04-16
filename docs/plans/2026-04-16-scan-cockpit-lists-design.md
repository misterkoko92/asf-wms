# Scan Cockpit Lists Standardization Design

**Date:** 2026-04-16

## Goal

Standardize the main legacy Django `scan/` list screens around one shared operating model:
- server-side filtering, sorting, and pagination for large operator lists,
- explicit `list -> cockpit` navigation,
- consistent short date display,
- shared small helpers for mechanism reuse,
- domain-local query and presentation logic so the refactor does not create new monoliths.

## Current State

The repository already has three relevant signals:

1. Several `scan/` tables reuse the visual/table-tools contract:
   - `templates/scan/receipts_view.html`
   - `templates/scan/orders_view.html`
   - `templates/scan/shipments_tracking.html`
   - `wms/static/scan/scan.js`

2. Some operator lists already use server-side pagination capped at `100` rows:
   - `wms/stock_view_helpers.py`
   - `wms/views_scan_admin.py`

3. The UI governance docs explicitly keep `Table`, `Toolbar`, and `EmptyState` in `En convergence`,
   not in `Core stable`:
   - `docs/plans/2026-03-22-ui-library-governance-design.md`
   - `docs/plans/2026-03-25-core-stable-usage-rules.md`

This means the repository already supports parts of the target behavior, but the behavior is not yet
consistent across the main `scan/` cockpit lists.

## Problems To Solve

- Large operator lists do not all behave the same way.
- Some tables rely on client-side filtering over already-loaded rows, which breaks the expected
  operator behavior when the searched item lives outside the currently loaded page.
- Date rendering is repeated with ad hoc `|date:"..."` patterns across templates.
- Some lists are summary-only and do not provide a standardized path toward the correction cockpit.
- Query parsing, row building, and pagination helpers risk growing inside `views_scan_*` modules if
  the work is implemented without explicit boundaries.

## Decision

Adopt a standard `scan cockpit list` pattern for the main legacy Django operator lists.

Initial target screens:
- `scan_receipts_view`
- `scan_orders_view`
- `scan_shipments_tracking`

Core decision:
- use server-side filtering, sorting, and pagination for the main cockpit lists,
- reset to page `1` whenever a filter or sort changes,
- default to `100` rows per page,
- keep the list focused on finding, prioritizing, and opening work,
- keep important mutations inside a cockpit or dossier page,
- share only the mechanism helpers that have already proven to be cross-screen.

## Non-Goals

This design does **not** aim to:
- create a universal `ui_table` primitive in `Core stable`,
- retrofit every table in the repository,
- move work into `frontend-next/` or reopen the paused Next migration scope,
- reopen translation work,
- force every cockpit to expose the exact same row schema,
- turn the list rows into inline CRUD panels.

## Product Principles

### 1. List for triage, cockpit for action

The list page is for:
- filtering,
- sorting,
- counting,
- spotting urgency,
- opening the right dossier.

The cockpit page is for:
- correcting data,
- mutating state,
- deleting when allowed,
- reviewing linked documents,
- handling domain-specific decisions.

Default rule:
- the list exposes one clear primary action, usually `Ouvrir`.

Allowed exception:
- a lightweight inline action may remain on the list when it is already a stable operator shortcut and
  does not replace the cockpit. `scan_shipments_tracking` is the clearest example, where `Suivi/MAJ`
  opens the dossier and `Clore le dossier` may remain a secondary inline action.

### 2. Pagination applies after filtering

Expected operator behavior:
- a search term must be applied to the full filtered dataset,
- then pagination is computed,
- then the first page of the filtered result is shown.

So if the user is on page `1`, types `compresse`, and the matching row used to be on page `3`,
the matching row must still appear.

### 3. Shared mechanism, local métier

Shared:
- querystring and pagination helpers,
- short date display helpers,
- pagination partial,
- common empty-state and action affordances.

Local to each domain:
- queryset composition,
- business filters,
- row presentation logic,
- cockpit actions,
- mutation permissions.

## Target Contract

### A. URL Contract

Standard query parameters for cockpit lists:
- `q`: free-text search
- `sort`: selected sort key
- `page`: current page number

Domain filters keep explicit names, for example:
- `type`
- `destination`
- `closed`
- `dispute`

Rules:
- filter/sort changes drop `page` and reopen at page `1`,
- next/previous pagination preserves current filters,
- reset links return to the base list URL without stale filters,
- URLs stay shareable and reproducible.

### B. View Context Contract

Each cockpit list view should expose a small shared page-level contract:
- `total_count`
- `page_obj`
- `page_prev_url`
- `page_next_url`
- `reset_url`
- `current_filters`
- `sort_value`
- `page_size`
- `rows`

The page-level contract is standardized.

The row payload is only partially standardized. Each row may keep domain-specific keys, but should
provide these shared affordances:
- `open_url`
- `open_label`
- `row_tone` when relevant
- already formatted display values rather than raw domain objects wherever possible

This keeps templates readable without forcing a generic row abstraction across unrelated workflows.

### C. UI Contract

A standard cockpit list page contains:
- a title/count header,
- an optional short context note,
- a GET filter toolbar,
- the main dense table,
- the pagination block,
- a consistent empty state.

The table stays an `En convergence` pattern:
- aligned with the current UI Lab and Bootstrap layer,
- not promoted yet to a global `Core stable` primitive.

### D. Date Contract

Dense operator lists should stop repeating raw format strings and converge on named short formats:

- `scan_date_short`: `JJ/MM/AA`
- `scan_datetime_short`: `JJ/MM/AA HHhMM`
- `scan_date_weekday_short`: `Jour JJ/MM/AA`

Usage rules:
- dense lists use the short forms,
- cockpits may use the short forms or a slightly longer variant when context benefits from it,
- documents/exports may keep longer formats where formality matters.

## Factorization Strategy

### Shared building blocks

Introduce small helpers with single responsibilities instead of one large table service:

- a dedicated template-tag module for short scan date formats,
- a small querystring/pagination URL helper module,
- a shared pagination partial for cockpit lists.

Good candidates:
- `wms/templatetags/wms_dates.py`
- `wms/scan_list_urls.py`
- `templates/scan/includes/scan_list_pagination.html`

### Domain-local modules

Keep domain list composition local to the relevant screen/domain:

- receipts:
  - filtering/queryset builder
  - row presenter
  - receipt cockpit payload/actions

- orders:
  - list query builder
  - row presenter and order dossier payload

- shipments:
  - tracking filters/query builder
  - row presenter
  - close/track actions remain local to shipment logic

Shared helpers should never assemble business rows for all domains.

## Screen-Specific Direction

### 1. Receipts

Current state:
- `scan/receipts/` is mostly a summary list with a type filter.
- It does not provide a standardized correction cockpit from the list itself.

Target:
- add server-side search/sort/pagination,
- add a clear `Ouvrir` action per row,
- introduce a receipt dossier/cockpit page,
- keep correction/delete actions in the receipt cockpit rather than inline in the list.

Recommended safety rule:
- destructive actions such as delete should be restricted to states where downstream references make
  the action safe and explainable.

### 2. Orders

Current state:
- `scan_orders_view` already follows the right product direction.
- It already opens `scan_order_detail`.

Target:
- keep `order_detail` as the cockpit,
- add server-side search/sort/pagination to the list,
- align dates and shared pagination behavior,
- avoid pushing more order-specific logic into `views_scan_orders.py`.

### 3. Shipments Tracking

Current state:
- `scan_shipments_tracking` already behaves like a cockpit list and already opens the tracking
  dossier through `Suivi/MAJ`.

Target:
- keep the existing dossier path,
- add server-side pagination capped at `100`,
- preserve current filters across paging,
- align dates with the shared short date helpers,
- keep `Clore le dossier` as a documented inline exception.

## Architectural Boundaries

### Do

- keep Django legacy as the active delivery surface,
- move shared read-only payload composition into `wms/application/scan/` only when the same payload
  is genuinely shared with a UI API or another adapter,
- prefer small pure helpers for URL/pagination behavior,
- keep mutation rules close to the owning domain modules.

### Do Not

- add a giant `table_helpers.py`,
- add a giant `scan_cockpit_service.py`,
- add a generic Python table object with dozens of options,
- centralize business row assembly for unrelated domains,
- move this work into the paused Next/React stack.

## Testing And Documentation Expectations

Implementation should update:
- view tests for each target screen,
- bootstrap/UI regression tests where shared contract assertions change,
- UI Lab demos if the visual contract changes materially,
- `docs/repo-reference/04-shared-contracts.md` because this is a cross-screen UI contract update,
- relevant impact-map notes if shared cockpit-list propagation rules change.

Minimum proof for the three main lists:
- filter applies to the full dataset, not only the currently visible page,
- pagination preserves active filters,
- sort changes reset to page `1`,
- list pages expose a stable `Ouvrir` path to the right cockpit,
- short date helper rendering is consistent.

## Rollout Strategy

Implement in phases rather than through one repo-wide sweep:

1. shared short date helpers and shared list pagination/querystring helpers,
2. receipt cockpit plus receipt list migration,
3. orders list migration,
4. shipments tracking migration,
5. UI Lab, repo-reference, and regression-test alignment.

This keeps the refactor incremental and makes it easier to stop after each working phase.
