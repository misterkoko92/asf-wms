# Scan Planning Nav And Service Worker Bump Design

## Goal

Add a direct `Planning` entry in the legacy `scan` navigation and force scan clients to pick up the newest UI assets without requiring a manual hard refresh.

## Scope

In scope:
- legacy Django `scan` shell only
- `Planning` nav entry pointing to the legacy planning run list
- explicit scan service worker version bump
- targeted regression tests

Out of scope:
- Next/React paused scope
- broader scan navigation refactor
- service worker strategy redesign beyond this cache invalidation fix

## Design

### Navigation

The scan navbar in [templates/scan/base.html](/Users/EdouardGonnu/asf-wms/.worktrees/codex/scan-planning-nav-sw-bump/templates/scan/base.html) will gain a simple top-level `Planning` nav item pointing to `planning:run_list`.

This keeps the change minimal:
- no new dropdown
- no changes to planning permissions
- no scan active-state reuse beyond a simple link render

### Service Worker Invalidation

The scan service worker is served by [wms/views_scan_misc.py](/Users/EdouardGonnu/asf-wms/.worktrees/codex/scan-planning-nav-sw-bump/wms/views_scan_misc.py) and registered from [templates/scan/base.html](/Users/EdouardGonnu/asf-wms/.worktrees/codex/scan-planning-nav-sw-bump/templates/scan/base.html).

To reduce stale UI after deployment, the bump will happen in two places:
- increment the `CACHE_NAME` constant in the worker body
- append an explicit version query parameter to the `navigator.serviceWorker.register(...)` URL

This is intentionally redundant. Updating both the worker internals and its registration URL gives the browser a clearer signal that the old worker and caches must be replaced.

## Testing

Targeted regressions:
- scan bootstrap UI test asserting the `Planning` nav link is present
- scan misc/service-worker test asserting the served worker contains the new cache version and headers remain correct

Broader regressions are not required for this tiny legacy-shell change unless targeted tests expose collateral failures.
