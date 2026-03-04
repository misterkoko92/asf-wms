# Admin Contacts Org-Role Cockpit Verification (2026-03-04)

## Scope

Verification du cockpit `scan:scan_admin_contacts` pour:

1. filtres et lecture org-role,
2. actions roles / contacts organisation / scopes / bindings,
3. creation guidee,
4. gate runtime legacy (`legacy_contact_write_enabled`),
5. non-regression pages admin scan et UI bootstrap.

## Branch and commits

- Branch: `codex/admin-contacts-cockpit`
- Commits implementes:
1. `588fc63` feat(scan): add admin contacts org-role cockpit skeleton
2. `5c665da` feat(scan): add org-role cockpit filters and result rows
3. `86918e2` feat(scan): add role activation and deactivation actions
4. `82f2d21` feat(scan): add organization contacts and role-contact linking
5. `b0ea7f6` feat(scan): add shipper scope management in cockpit
6. `946bb50` feat(scan): add recipient binding management in cockpit
7. `38e9817` feat(scan): add guided contact creation workflow
8. `443eeac` feat(scan): gate legacy contact actions and finalize org-role cockpit

## Executed commands

1. Guided contact fixes (targeted):

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_admin_contacts_cockpit.ScanAdminContactsCockpitViewTests.test_create_guided_contact_creates_organization_and_role_assignment \
  wms.tests.views.tests_views_scan_admin_contacts_cockpit.ScanAdminContactsCockpitViewTests.test_create_guided_contact_creates_person_linked_to_existing_org -v 2
```

Result: PASS (2 tests).

2. Legacy gate targeted checks:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_admin_contacts_cockpit.ScanAdminContactsCockpitViewTests.test_legacy_actions_blocked_when_runtime_flag_disabled \
  wms.tests.views.tests_views_scan_admin.ScanAdminViewTests.test_scan_admin_contacts_hides_legacy_forms_when_runtime_flag_disabled \
  wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_admin_contacts_bootstrap_keeps_fallback_links_when_legacy_disabled -v 2
```

Result: PASS (3 tests).

3. Final non-regression suite:

```bash
/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_admin_contacts_cockpit \
  wms.tests.views.tests_views_scan_admin \
  wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Result: PASS (74 tests).

## Outcome

- Cockpit org-role disponible sur la route legacy `scan:scan_admin_contacts`.
- Actions metier principales couvertes par tests vue.
- Gate legacy valide:
1. actions legacy bloquees quand flag runtime desactive,
2. formulaires legacy masques,
3. fallback admin Django conserve.
- Aucune regression detectee sur les suites admin scan et bootstrap ciblees.
