# Scan Service Worker Bump Design

## Goal

Force legacy `scan` clients to pick up the newest deployed UI assets without requiring manual hard refreshes.

## Scope

In scope:
- legacy Django `scan` shell only
- explicit scan service worker version bump
- verification of adjacent legacy cache points already in use
- targeted regression tests for the served worker and registration URL

Out of scope:
- Next/React paused scope
- global asset versioning across the whole legacy stack
- redesign of the scan service worker strategy
- cache changes outside the legacy `scan` entrypoint

## Current State

The legacy scan shell registers the service worker from [templates/scan/base.html](/Users/EdouardGonnu/asf-wms/.worktrees/scan-service-worker-bump/templates/scan/base.html) using `service-worker.js?v=50`.

The worker itself is served by [wms/views_scan_misc.py](/Users/EdouardGonnu/asf-wms/.worktrees/scan-service-worker-bump/wms/views_scan_misc.py), where:
- `SCAN_SERVICE_WORKER_VERSION = "50"`
- `SERVICE_WORKER_JS` builds `CACHE_NAME = wms-scan-v50`
- the worker precaches the core scan assets and deletes old scan caches on `activate`

Other adjacent legacy cache points checked during design:
- the scan manifest is linked statically from the scan base template
- the scan CSS/JS are linked statically from the scan base template
- no second manual cache version constant was found in the legacy scan shell beyond the service worker version and its registration query string

This makes the scan service worker the right invalidation lever for the current symptom.

## Recommended Approach

Use a targeted scan-only bump and keep the existing invalidation pattern aligned in both places:
- increment the worker version constant in [wms/views_scan_misc.py](/Users/EdouardGonnu/asf-wms/.worktrees/scan-service-worker-bump/wms/views_scan_misc.py)
- increment the explicit `?v=` query string in [templates/scan/base.html](/Users/EdouardGonnu/asf-wms/.worktrees/scan-service-worker-bump/templates/scan/base.html)

This keeps the change minimal while forcing:
- a new worker registration URL
- a new internal `CACHE_NAME`
- deletion of previous scan caches during worker activation

No broader cache-busting mechanism is introduced because the current issue is already explained by the existing scan worker version staying static.

## Testing

Targeted regressions:
- extend [wms/tests/views/tests_views_scan_misc.py](/Users/EdouardGonnu/asf-wms/.worktrees/scan-service-worker-bump/wms/tests/views/tests_views_scan_misc.py) to assert the new worker cache name and registration query string
- rerun the focused scan misc test module after the bump

Known baseline noise before implementation:
- [wms/tests/views/tests_views_scan_misc.py](/Users/EdouardGonnu/asf-wms/.worktrees/scan-service-worker-bump/wms/tests/views/tests_views_scan_misc.py#L90) already fails on `test_scan_faq_renders_native_english_when_runtime_disabled`
- that failure is unrelated to the service worker bump and should not be treated as a regression from this work

Success criteria:
- the worker response contains the new `wms-scan-vNN` cache name
- the scan template registers `service-worker.js?v=NN`
- after deployment, reloading a scan page is enough to activate the new worker and refresh stale scan assets
