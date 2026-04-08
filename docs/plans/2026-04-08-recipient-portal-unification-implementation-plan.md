# Recipient Portal Unification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move recipient shared data to a single shipment-party source of truth, add recipient portal access on the existing `/portal/` surface, and route shipper portal, recipient portal, scan/admin, and UI API writes through shared party use cases.

**Architecture:** Keep the shipment-party runtime (`ShipmentRecipientOrganization`, `ShipmentRecipientContact`, recipient documents, recipient product preferences, shipper-recipient links) as the canonical model. Add explicit portal access grants plus an active-scope session layer, migrate every mutation path to shared `wms/application/parties/` use cases, and keep `AssociationProfile` / `AssociationRecipient` only as transition compatibility until the old write paths are cut off.

**Tech Stack:** Django models/views/templates, Django auth/session, legacy portal and scan views, UI API endpoints, migrations, Django test runner, management commands.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`, `@repo-reference-governance`.

### Task 1: Add portal access-grant domain objects and scope helpers

**Files:**
- Modify: `wms/models_domain/portal.py`
- Modify: `wms/models.py`
- Create: `wms/migrations/<next>_portal_access_grants.py`
- Create: `wms/portal_access.py`
- Test: `wms/tests/portal/tests_portal_access_grants.py`
- Test: `wms/tests/portal/tests_portal_permissions.py`

**Step 1: Write the failing test**

Add tests that verify:
- a `PortalAccessGrant` can target either a `ShipmentShipper` or a `ShipmentRecipientOrganization`, but not both;
- a user can own multiple active grants;
- legacy `AssociationProfile` users still resolve to an implicit shipper scope;
- scope selection helpers reject inactive grants.

```python
def test_portal_access_grant_requires_exactly_one_scope(self):
    PortalAccessGrant.objects.create(user=user, shipper=shipper, recipient_organization=recipient_org)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_portal_access_grants wms.tests.portal.tests_portal_permissions -v 2`
Expected: FAIL because the model and helpers do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- `PortalAccessGrant` in `wms/models_domain/portal.py`;
- `wms/models.py` export wiring;
- `wms/portal_access.py` helpers for:
  - resolving explicit grants,
  - resolving legacy implicit shipper access from `AssociationProfile`,
  - activating a selected scope in session.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_portal_access_grants wms.tests.portal.tests_portal_permissions -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/portal.py wms/models.py wms/portal_access.py wms/migrations/*.py wms/tests/portal/tests_portal_access_grants.py wms/tests/portal/tests_portal_permissions.py
git commit -m "feat: add portal access grant domain model"
```

### Task 2: Move portal auth and permission checks to the active-scope model

**Files:**
- Modify: `wms/views_portal_auth.py`
- Modify: `wms/portal_helpers.py`
- Modify: `wms/view_permissions.py`
- Modify: `wms/portal_urls.py`
- Create: `templates/portal/access_scope_select.html`
- Test: `wms/tests/views/tests_views_portal.py`
- Test: `wms/tests/portal/tests_portal_permissions.py`

**Step 1: Write the failing test**

Add tests that verify:
- login with one grant activates the scope and redirects directly;
- login with multiple grants redirects to a scope selector;
- a recipient scope cannot access shipper-only order pages;
- a shipper scope cannot use recipient-only shared-data mutations once locked down.

```python
def test_login_with_multiple_grants_redirects_to_scope_selector(self):
    response = self.client.post(reverse("portal:portal_login"), {...})
    self.assertRedirects(response, reverse("portal:portal_scope_select"))
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.portal.tests_portal_permissions -v 2`
Expected: FAIL because the login flow still assumes a single `AssociationProfile`.

**Step 3: Write minimal implementation**

Implement:
- active-scope resolution in login flow;
- a scope-selection route/page for multi-access users;
- permission decorators that depend on active scope instead of only `request.association_profile`;
- compatibility fallback for legacy shipper users.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.portal.tests_portal_permissions -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_portal_auth.py wms/portal_helpers.py wms/view_permissions.py wms/portal_urls.py templates/portal/access_scope_select.html wms/tests/views/tests_views_portal.py wms/tests/portal/tests_portal_permissions.py
git commit -m "feat: add active portal scope selection"
```

### Task 3: Extract canonical recipient mutation use cases around the shipment-party runtime

**Files:**
- Modify: `wms/application/parties/use_cases.py`
- Modify: `wms/parties/sync.py`
- Create: `wms/parties/projections.py`
- Create: `wms/tests/core/tests_parties_use_cases.py`
- Modify: `wms/tests/portal/tests_portal_recipient_sync.py`
- Modify: `wms/tests/core/tests_parties_destination_scope.py`

**Step 1: Write the failing test**

Add tests that verify shared use cases can:
- create or update a recipient structure keyed by `(organization, destination)`;
- upsert recipient contacts and documents;
- save recipient product preferences on the canonical runtime;
- refresh a legacy `AssociationRecipient` projection when compatibility is still enabled.

```python
def test_update_shared_recipient_profile_updates_runtime_and_projection(self):
    result = update_recipient_shared_profile(...)
    self.assertEqual(result.recipient_organization.destination, destination)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_parties_use_cases wms.tests.portal.tests_portal_recipient_sync -v 2`
Expected: FAIL because the use cases do not exist yet.

**Step 3: Write minimal implementation**

Implement shared application-level writes such as:
- `create_or_link_shipper_recipient(...)`
- `update_recipient_shared_profile(...)`
- `save_recipient_product_preference(...)`
- `upsert_recipient_structure_documents(...)`
- `refresh_legacy_association_recipient_projection(...)`

Keep all canonical writes in the shipment-party runtime and keep projection logic isolated in `wms/parties/projections.py`.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_parties_use_cases wms.tests.portal.tests_portal_recipient_sync -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/application/parties/use_cases.py wms/parties/sync.py wms/parties/projections.py wms/tests/core/tests_parties_use_cases.py wms/tests/portal/tests_portal_recipient_sync.py wms/tests/core/tests_parties_destination_scope.py
git commit -m "feat: add canonical recipient mutation use cases"
```

### Task 4: Route shipper portal recipient CRUD through the shared use cases

**Files:**
- Modify: `wms/views_portal_account.py`
- Modify: `templates/portal/recipients.html`
- Modify: `templates/portal/recipient_detail.html`
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Modify: `wms/tests/portal/tests_portal_shipment_parties.py`

**Step 1: Write the failing test**

Add tests that verify:
- shipper portal recipient create/update paths no longer require direct writes to `AssociationRecipient` as the source of truth;
- recipient shared fields become read-only from the shipper portal once a recipient access grant exists;
- shipper-side relation management still creates the correct `ShipmentShipperRecipientLink`.

```python
def test_shipper_portal_recipient_edit_becomes_read_only_when_recipient_grant_exists(self):
    response = self.client.post(reverse("portal:portal_recipients"), {...})
    self.assertContains(response, "lecture seule")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.portal.tests_portal_shipment_parties -v 2`
Expected: FAIL because the portal still writes and owns shared recipient fields directly.

**Step 3: Write minimal implementation**

Implement:
- shipper portal create/link flow through the shared party use cases;
- shared-field read-only enforcement when a recipient grant exists;
- relation editing kept on shipper-owned link fields only.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.portal.tests_portal_shipment_parties -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_portal_account.py templates/portal/recipients.html templates/portal/recipient_detail.html wms/tests/views/tests_views_portal.py wms/tests/views/tests_portal_bootstrap_ui.py wms/tests/portal/tests_portal_shipment_parties.py
git commit -m "feat: route shipper portal recipient writes through shared use cases"
```

### Task 5: Add recipient portal maintenance screens on the existing `/portal/` shell

**Files:**
- Modify: `wms/views_portal_account.py`
- Modify: `wms/application/portal/dashboard_queries.py`
- Modify: `templates/portal/base.html`
- Create: `templates/portal/recipient_scope_home.html`
- Modify: `wms/tests/views/tests_views_portal.py`
- Modify: `wms/tests/views/tests_portal_bootstrap_ui.py`

**Step 1: Write the failing test**

Add tests that verify:
- a recipient scope lands on a recipient-oriented portal dashboard/home;
- the recipient scope can see structure data, contacts, documents, and product preferences for exactly one `ShipmentRecipientOrganization`;
- the existing shipper navigation still works unchanged for shipper scope.

```python
def test_recipient_scope_dashboard_shows_recipient_maintenance_sections(self):
    response = self.client.get(reverse("portal:portal_dashboard"))
    self.assertContains(response, "Preferences produits")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.views.tests_portal_bootstrap_ui -v 2`
Expected: FAIL because the portal shell only knows the shipper experience.

**Step 3: Write minimal implementation**

Implement:
- recipient-scope dashboard/home composition;
- portal shell navigation that reacts to active scope;
- a recipient maintenance screen reusing the canonical recipient runtime instead of `AssociationRecipient`.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal wms.tests.views.tests_portal_bootstrap_ui -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_portal_account.py wms/application/portal/dashboard_queries.py templates/portal/base.html templates/portal/recipient_scope_home.html wms/tests/views/tests_views_portal.py wms/tests/views/tests_portal_bootstrap_ui.py
git commit -m "feat: add recipient scope portal maintenance screens"
```

### Task 6: Route scan/admin recipient shared mutations through the same use cases

**Files:**
- Modify: `wms/views_scan_admin.py`
- Modify: `wms/scan_admin_contacts_cockpit.py`
- Modify: `templates/scan/admin_recipient_organization_detail.html`
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/views/tests_views_scan_admin_shipment_parties.py`

**Step 1: Write the failing test**

Add tests that verify:
- scan/admin edits to recipient shared fields call the same shared party use cases;
- scan/admin preference edits still update the canonical `RecipientProductPreference` rows;
- a scan/admin shared-data mutation becomes visible in portal shipper and portal recipient views.

```python
def test_scan_admin_recipient_update_refreshes_portal_views(self):
    response = self.client.post(scan_url, {...})
    self.assertRedirects(response, detail_url)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_admin_shipment_parties -v 2`
Expected: FAIL because scan/admin still mutates runtime data directly without the shared abstraction.

**Step 3: Write minimal implementation**

Implement:
- scan/admin detail mutations through shared party use cases;
- canonical projection refresh after scan edits when legacy portal projection still exists;
- no duplicate business rules outside the canonical use-case layer.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin wms.tests.views.tests_views_scan_admin_shipment_parties -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_scan_admin.py wms/scan_admin_contacts_cockpit.py templates/scan/admin_recipient_organization_detail.html wms/tests/views/tests_views_scan_admin.py wms/tests/views/tests_views_scan_admin_shipment_parties.py
git commit -m "feat: route scan recipient mutations through shared use cases"
```

### Task 7: Migrate UI API portal recipient endpoints to active scope and shared use cases

**Files:**
- Modify: `api/v1/ui_views.py`
- Modify: `api/v1/serializers.py`
- Modify: `api/v1/permissions.py`
- Modify: `api/tests/tests_ui_endpoints.py`
- Modify: `api/tests/tests_ui_e2e_workflows.py`

**Step 1: Write the failing test**

Add tests that verify:
- portal UI API recipient endpoints resolve the active scope;
- recipient-scope API payloads expose only the canonical recipient runtime they own;
- create/update endpoints call shared party use cases instead of direct legacy mutations.

```python
def test_ui_portal_recipient_patch_uses_active_recipient_scope(self):
    response = self.client.patch(url, data, content_type="application/json")
    self.assertEqual(response.status_code, 200)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test api.tests.tests_ui_endpoints api.tests.tests_ui_e2e_workflows -v 2`
Expected: FAIL because the UI API still assumes shipper-only portal behavior and direct legacy writes.

**Step 3: Write minimal implementation**

Implement:
- active-scope resolution in UI API permissions/views;
- shared use-case calls for recipient mutations;
- separate shipper vs recipient response shaping where needed, without diverging business rules.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test api.tests.tests_ui_endpoints api.tests.tests_ui_e2e_workflows -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add api/v1/ui_views.py api/v1/serializers.py api/v1/permissions.py api/tests/tests_ui_endpoints.py api/tests/tests_ui_e2e_workflows.py
git commit -m "feat: migrate portal UI API to active scope and shared party use cases"
```

### Task 8: Add recipient-graph reconciliation and optional rebuild tooling

**Files:**
- Create: `wms/parties/rebuild.py`
- Create: `wms/management/commands/rebuild_recipient_party_graph.py`
- Create: `wms/tests/management/tests_management_rebuild_recipient_party_graph.py`
- Modify: `wms/tests/scan/tests_admin_contacts_merge_service.py`

**Step 1: Write the failing test**

Add tests that verify the command can:
- dry-run duplicate recipient-organization detection by `(organization, destination)`;
- rebuild access grants from canonical shipper/recipient links;
- refresh legacy portal projections after canonical rebuild;
- leave unrelated contact capabilities untouched.

```python
def test_rebuild_recipient_party_graph_dry_run_reports_duplicates(self):
    call_command("rebuild_recipient_party_graph", "--dry-run")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.management.tests_management_rebuild_recipient_party_graph wms.tests.scan.tests_admin_contacts_merge_service -v 2`
Expected: FAIL because the rebuild command does not exist yet.

**Step 3: Write minimal implementation**

Implement:
- a deterministic rebuild service over canonical recipient runtime rows;
- a management command with `--dry-run` and `--apply`;
- regeneration of portal access grants and legacy projections from canonical state.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.management.tests_management_rebuild_recipient_party_graph wms.tests.scan.tests_admin_contacts_merge_service -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/parties/rebuild.py wms/management/commands/rebuild_recipient_party_graph.py wms/tests/management/tests_management_rebuild_recipient_party_graph.py wms/tests/scan/tests_admin_contacts_merge_service.py
git commit -m "feat: add recipient party graph rebuild tooling"
```

### Task 9: Update repo-reference docs and release checks to match the new portal model

**Files:**
- Modify: `docs/repo-reference/01-architecture-and-entrypoints.md`
- Modify: `docs/repo-reference/02-key-flows-and-living-tests.md`
- Modify: `docs/repo-reference/03-impact-map.md`
- Modify: `docs/repo-reference/04-shared-contracts.md`
- Modify: `docs/mvp_spec.md`
- Modify: `docs/release_checklist.md`

**Step 1: Write the failing test**

Add a doc checklist in the task notes that verifies:
- portal access is described as active-scope based, not shipper-only;
- recipient shared-data ownership and propagation rules are documented;
- release smoke mentions the recipient-scope portal path when enabled.

**Step 2: Run verification to show docs are stale**

Run: `rg -n "AssociationProfile|portal recipient|scope actif|recipient portal" docs/repo-reference docs/mvp_spec.md docs/release_checklist.md`
Expected: Missing or outdated descriptions before the doc update.

**Step 3: Write minimal implementation**

Update the repo-reference and release docs so they describe:
- the active-scope portal architecture;
- the canonical shipment-party write path;
- the new propagation checks for shipper portal, recipient portal, scan, and UI API.

**Step 4: Run verification to confirm docs are aligned**

Run: `rg -n "scope actif|PortalAccessGrant|recipient portal|shipment-party" docs/repo-reference docs/mvp_spec.md docs/release_checklist.md`
Expected: PASS with the new terminology and routes described.

**Step 5: Commit**

```bash
git add docs/repo-reference/01-architecture-and-entrypoints.md docs/repo-reference/02-key-flows-and-living-tests.md docs/repo-reference/03-impact-map.md docs/repo-reference/04-shared-contracts.md docs/mvp_spec.md docs/release_checklist.md
git commit -m "docs: document recipient portal active-scope architecture"
```

### Task 10: Run the minimum cross-surface regression suite before cleanup

**Files:**
- Test: `wms/tests/portal/tests_portal_access_grants.py`
- Test: `wms/tests/portal/tests_portal_recipient_sync.py`
- Test: `wms/tests/portal/tests_portal_shipment_parties.py`
- Test: `wms/tests/portal/tests_portal_permissions.py`
- Test: `wms/tests/views/tests_views_portal.py`
- Test: `wms/tests/views/tests_portal_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views_scan_admin.py`
- Test: `wms/tests/views/tests_views_scan_admin_shipment_parties.py`
- Test: `wms/tests/core/tests_parties_destination_scope.py`
- Test: `api/tests/tests_ui_endpoints.py`
- Test: `api/tests/tests_ui_e2e_workflows.py`

**Step 1: Run the focused regression suite**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.portal.tests_portal_access_grants \
  wms.tests.portal.tests_portal_recipient_sync \
  wms.tests.portal.tests_portal_shipment_parties \
  wms.tests.portal.tests_portal_permissions \
  wms.tests.views.tests_views_portal \
  wms.tests.views.tests_portal_bootstrap_ui \
  wms.tests.views.tests_views_scan_admin \
  wms.tests.views.tests_views_scan_admin_shipment_parties \
  wms.tests.core.tests_parties_destination_scope \
  api.tests.tests_ui_endpoints \
  api.tests.tests_ui_e2e_workflows -v 2
```

Expected: PASS.

**Step 2: Run rebuild-command smoke in dry-run mode**

Run: `./.venv/bin/python manage.py rebuild_recipient_party_graph --dry-run`
Expected: PASS with a deterministic summary and no writes.

**Step 3: Commit the final cleanup if needed**

```bash
git add -A
git commit -m "chore: finish recipient portal unification rollout"
```

Plan complete and saved to `docs/plans/2026-04-08-recipient-portal-unification-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
