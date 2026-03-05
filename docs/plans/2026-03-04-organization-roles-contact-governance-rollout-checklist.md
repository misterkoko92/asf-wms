# Organization Roles Contact Governance Rollout Checklist

## Scope covered

- Task 9: Admin review dashboard for migration queue.
- Task 10: Role-based shipper/recipient resolution in order/shipment flows.
- Task 11: Role-based notification routing in signals with dedup and correspondent coordination note.

## Status update (2026-03-05)

- Final no-legacy cutover delivered: `legacy_contact_write_enabled` removed from runtime model/config/forms and scan/public/admin flows.
- Verification evidence is tracked in `docs/plans/2026-03-05-no-legacy-final-cutover-verification.md`.

## Verification evidence

### Task 9 validation

- Command:
  - `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_organization_roles_review -v 2`
- Result: PASS (4 tests).

### Task 10 validation

- Command:
  - `./.venv/bin/python manage.py test wms.tests.domain.tests_domain_orders_org_roles wms.tests.forms.tests_forms_org_roles_gate -v 2`
- Result: PASS (5 tests).

### Task 11 validation

- Command:
  - `./.venv/bin/python manage.py test wms.tests.emailing.tests_signals_org_role_notifications -v 2`
- Result: PASS (4 tests).

### Non-regression suites executed

- `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_extra -v 2` -> PASS.
- `./.venv/bin/python manage.py test wms.tests.forms.tests_forms wms.tests.domain.tests_domain_orders_extra wms.tests.scan.tests_scan_shipment_handlers wms.tests.public.tests_public_order_helpers -v 2` -> PASS.
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal -v 2` -> PASS.
- `./.venv/bin/python manage.py test wms.tests.orders.tests_order_scan_handlers -v 2` -> PASS.
- `./.venv/bin/python manage.py test wms.tests.emailing.tests_signals_extra wms.tests.emailing.tests_signals_org_role_notifications wms.tests.emailing.tests_signal_notifications_queue -v 2` -> PASS.

## Migration dry-run check

- Command:
  - `./.venv/bin/python manage.py migrate_contacts_to_org_roles --dry-run`
- Result: FAIL in local environment (`no such table: wms_organizationroleassignment`).
- Interpretation: local DB schema is not migrated to the org-role model version.
- Required action before production-style dry-run:
  - Run `./.venv/bin/python manage.py migrate` on the target environment.
  - Re-run dry-run command and capture summary metrics.

## Rollout gates

- `org_roles_engine_enabled`: keep disabled until migration review queue and bindings are validated.
- `org_roles_review_max_open_percent`: configured threshold currently set to 20.

## Go/No-Go decision (current local evidence)

- Code-level and behavior-level tests for Tasks 9-11: GO.
- Data migration dry-run evidence on a migrated DB: NO-GO until environment migration step is completed.

## Next operational actions

1. Apply migrations in target environment.
2. Run `migrate_contacts_to_org_roles --dry-run` and validate review queue volume vs threshold.
3. Use admin review dashboard to resolve open migration items.
4. Enable `org_roles_engine_enabled`.
