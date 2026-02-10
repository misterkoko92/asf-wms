# ASF WMS

MVP WMS for product catalog, lot-based stock, and shipments.

## Local setup
- Python 3.11 or 3.12 recommended (Django 4.2 LTS)
- Create venv and install deps
- Run migrations and create admin user

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Tests and coverage
```bash
pip install -r requirements-dev.txt
python manage.py test
coverage run --rcfile=.coveragerc manage.py test
coverage report -m --fail-under=95
coverage xml
```

## Quality and security checks
```bash
python -m pip check
python manage.py check --deploy --fail-level WARNING
ruff check .
pip-audit -r requirements.txt
bandit -r asf_wms api contacts wms -x "wms/migrations,contacts/migrations,wms/tests.py,wms/tests_*.py,api/tests.py,api/tests_*.py,contacts/tests.py,contacts/tests_*.py"
pre-commit run --all-files
```

## Operations quick commands
```bash
# Process outbound email queue (default: 100 events)
python manage.py process_email_queue --limit=100

# Retry events currently in failed status
python manage.py process_email_queue --include-failed --limit=100

# Inspect queue status counts
python manage.py shell -c "from wms.models import IntegrationEvent, IntegrationDirection; qs=IntegrationEvent.objects.filter(direction=IntegrationDirection.OUTBOUND, source='wms.email', event_type='send_email'); print({s: qs.filter(status=s).count() for s in ['pending','processing','processed','failed']})"
```

## Docs
- MVP spec: `docs/mvp_spec.md`
- Backlog: `docs/backlog.md`
- Operations runbook: `docs/operations.md`
- Release checklist: `docs/release_checklist.md`
- Import template: `docs/import/products_template.csv`
- Print templates: `docs/templates/`

## Architecture (refactor)
- `wms/views.py`: re-exports used by URL routing/tests.
- `wms/views_scan_*.py`, `wms/views_portal_*.py`, `wms/views_public_*.py`: thin views, mostly wiring.
- `*_handlers.py`: request/form orchestration, error handling, redirects.
- `*_state.py` / `*_helpers.py`: view model builders and UI data prep.
- `wms/domain/*.py`: business logic (stock, orders) kept framework-light.
- `wms/import_services_*.py`: import pipelines (facade: `wms/import_services.py`).
- `wms/scan_*_helpers.py`: scan helpers (facade: `wms/scan_helpers.py`).

## Import products
```bash
python manage.py import_products docs/import/products_template.csv
python manage.py import_products docs/import/products_template.csv --update
python manage.py import_products docs/import/products_template.xlsx
```
Notes:
- `sku` can be empty on import; it will be auto-generated.
- `brand` is optional.

## Sample data
- Produit (CSV): `docs/import/sample_products.csv`
- Chaine complete (fixtures): `python manage.py loaddata wms/fixtures/sample_chain.json`
- Contacts: `python manage.py loaddata contacts/fixtures/sample_contacts.json`
- Receptions: `python manage.py loaddata wms/fixtures/sample_receipts.json` (necessite les fixtures contacts + chain)

## Admin workflows
- Stock movements: Reception stock, Ajuster stock, Transferer stock, Preparer carton
- Cartons: action Deconditionner pour remettre en stock
- Shipments: Impression A5 (bon expedition, attestations, listes colisage)
- Produits: QR code auto-genere, archivage/reactivation, selection categorie 4 niveaux
- Categorie: un seul selecteur avec chemin complet (ex: L1 > L2 > L3)
- Contacts: gestion des donateurs/transporteurs/expediteurs avec adresses
- Commandes: creation, reservation stock, preparation automatique

## Configuration
- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` (comma-separated)
  - In production (`DJANGO_DEBUG=false`), `DJANGO_SECRET_KEY` must be a strong non-default value.
- `ENABLE_BASIC_AUTH` (optional, defaults to true in debug and false in production)
- Security (optional): `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
  `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`,
  `SECURE_REFERRER_POLICY`, `USE_PROXY_SSL_HEADER`, `CSRF_TRUSTED_ORIGINS`
- `ORG_NAME`, `ORG_ADDRESS`, `ORG_CONTACT`, `ORG_SIGNATORY`
- `SKU_PREFIX`
- `IMPORT_DEFAULT_PASSWORD` (optional, for user imports when CSV password is empty)
- `INTEGRATION_API_KEY` (optional, for integration endpoints)
- `ACCOUNT_REQUEST_THROTTLE_SECONDS` (optional, default `300`)
- `PUBLIC_ORDER_THROTTLE_SECONDS` (optional, default `300`)
- MySQL (optional): `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_ENGINE`
  - If `DB_NAME` is set, Django uses MySQL; otherwise it uses SQLite.

Example (bash):
```bash
export DJANGO_SECRET_KEY="replace-with-a-long-random-secret-key-of-at-least-50-characters"
export DJANGO_DEBUG="false"
export DJANGO_ALLOWED_HOSTS="example.com,www.example.com"
export ENABLE_BASIC_AUTH="false"
export SECURE_SSL_REDIRECT="true"
export SESSION_COOKIE_SECURE="true"
export CSRF_COOKIE_SECURE="true"
export USE_PROXY_SSL_HEADER="true"
export CSRF_TRUSTED_ORIGINS="https://example.com,https://www.example.com"
export ORG_NAME="Aviation Sans Frontieres"
export ORG_ADDRESS="10 Rue Exemple, 75000 Paris"
export ORG_CONTACT="contact@example.com"
export ORG_SIGNATORY="Jean Dupont"
export SKU_PREFIX="ASF"
export IMPORT_DEFAULT_PASSWORD="TempPWD!"
export INTEGRATION_API_KEY="change-me"
export ACCOUNT_REQUEST_THROTTLE_SECONDS="300"
export PUBLIC_ORDER_THROTTLE_SECONDS="300"
```

## Scan PWA
- URL: `http://localhost:8000/scan/`
- Camera scan uses the browser BarcodeDetector (Chrome/Android recommended)
- For desktop: USB/Bluetooth scanners work as keyboard input
- Login uses the admin credentials at `/admin/login/`

## API (v1)
- Base URL: `http://localhost:8000/api/v1/`
- Auth: session (admin login) and basic auth when `ENABLE_BASIC_AUTH=true`
- Endpoints:
  - `GET /api/v1/products/`
  - `POST /api/v1/stock/receive/`
  - `POST /api/v1/pack/`
  - `POST /api/v1/orders/{id}/reserve/`
  - `POST /api/v1/orders/{id}/prepare/`
- Integration endpoints (require admin user or `INTEGRATION_API_KEY` via `X-ASF-Integration-Key`):
  - `GET /api/v1/integrations/shipments/`
  - `GET /api/v1/integrations/destinations/`
  - `GET /api/v1/integrations/events/`
  - `POST /api/v1/integrations/events/`

## PythonAnywhere (free tier)
- Create a new web app (Manual config)
- Use a virtualenv with Python 3.11/3.12
- Install deps: `pip install -r requirements.txt`
- Set WSGI to `asf_wms.wsgi`
- Run migrations from a Bash console
- For MySQL: create the database in the Databases tab, then set `DB_*` env vars in WSGI

Example env vars (Web tab -> WSGI configuration):
```
DJANGO_SECRET_KEY=replace-with-a-long-random-secret-key-of-at-least-50-characters
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=yourdomain.pythonanywhere.com
SITE_BASE_URL=https://yourdomain.pythonanywhere.com
ENABLE_BASIC_AUTH=false
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
USE_PROXY_SSL_HEADER=true
CSRF_TRUSTED_ORIGINS=https://yourdomain.pythonanywhere.com
ORG_NAME=Aviation Sans Frontieres
ORG_ADDRESS=10 Rue Exemple, 75000 Paris
ORG_CONTACT=contact@example.com
ORG_SIGNATORY=Jean Dupont
SKU_PREFIX=ASF
IMPORT_DEFAULT_PASSWORD=TempPWD!
INTEGRATION_API_KEY=change-me
ACCOUNT_REQUEST_THROTTLE_SECONDS=300
PUBLIC_ORDER_THROTTLE_SECONDS=300
DB_NAME=youruser$asf_wms
DB_USER=youruser
DB_PASSWORD=yourpassword
DB_HOST=youruser.mysql.pythonanywhere-services.com
DB_PORT=3306
```
