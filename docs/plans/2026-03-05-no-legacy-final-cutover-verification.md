# No Legacy Final Cutover Verification

Date: 2026-03-05

## Scope verified
- Scan order creation no longer blocked by legacy write gate.
- Public order helper no longer writes legacy `ContactTag` / `ContactAddress` side-effects.
- Scan admin contacts no longer exposes legacy CRUD actions (`create_contact`, `update_contact`, `delete_contact`).
- Runtime flag `legacy_contact_write_enabled` removed from model/config/forms/runtime pipeline.

## Commands executed and results

### 1) RED->GREEN targeted suite (forms/orders/public/admin/bootstrap)
```bash
./.venv/bin/python manage.py test \
  wms.tests.forms.tests_forms_org_roles_gate \
  wms.tests.orders.tests_order_scan_handlers \
  wms.tests.public.tests_public_order_helpers \
  wms.tests.views.tests_views_scan_admin \
  wms.tests.views.tests_views_scan_admin_contacts_cockpit \
  wms.tests.views.tests_scan_bootstrap_ui -v 1
```
Result: `Ran 99 tests ... OK`

### 2) Runtime/settings/domain wave for flag removal
```bash
./.venv/bin/python manage.py test \
  wms.tests.core.tests_runtime_role_migration_flags \
  wms.tests.forms.tests_forms_scan_settings \
  wms.tests.views.tests_views_scan_settings \
  wms.tests.domain.tests_domain_orders_org_roles -v 2
```
Result: `Ran 25 tests ... OK`

### 3) Public order regression slice
```bash
./.venv/bin/python manage.py test \
  wms.tests.public.tests_public_order_helpers \
  wms.tests.views.tests_views_public_order -v 1
```
Result: `Ran 21 tests ... OK`

### 4) Broader regression slice
```bash
./.venv/bin/python manage.py test \
  wms.tests.domain.tests_domain_orders_org_roles \
  wms.tests.domain.tests_domain_orders_extra \
  wms.tests.forms.tests_forms \
  wms.tests.views.tests_views -v 1
```
Result: `Ran 107 tests ... OK`

### 5) Runtime settings smoke
```bash
./.venv/bin/python manage.py test wms.tests.core.tests_runtime_settings -v 1
```
Result: `Ran 3 tests ... OK`

### 6) Residual reference check
```bash
rg -n "legacy_contact_write_enabled|is_legacy_contact_write_enabled|action\" value=\"create_contact|action\" value=\"update_contact|action\" value=\"delete_contact" wms templates
```
Result: matches only in migrations history and tests assertions.

Runtime/template code-only check:
```bash
rg -n "legacy_contact_write_enabled|is_legacy_contact_write_enabled|action\" value=\"create_contact|action\" value=\"update_contact|action\" value=\"delete_contact" wms templates -g '!wms/tests/**' -g '!wms/migrations/**'
```
Result: no match.

### 7) Full project suite (`wms.tests`)
```bash
./.venv/bin/python manage.py test wms.tests -v 1
```
Result: `Ran 1232 tests ... OK (skipped=43)`

### 8) Schema checks
```bash
./.venv/bin/python manage.py makemigrations --check --dry-run
./.venv/bin/python manage.py migrate
```
Result:
- `No changes detected`
- `No migrations to apply`

## Residual risks
- Historical migrations and historical docs still contain legacy wording by design (audit trail).
- Existing migration dependency name `0072_wmsruntimesettings_legacy_contact_write_enabled_and_more` remains unchanged (safe and expected).

## Go / No-Go
- **Go** for code-level no-legacy cutover on Django runtime paths covered above.
