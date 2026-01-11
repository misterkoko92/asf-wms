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

## Docs
- MVP spec: `docs/mvp_spec.md`
- Backlog: `docs/backlog.md`
- Import template: `docs/import/products_template.csv`
- Print templates: `docs/templates/`

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
- `ORG_NAME`, `ORG_ADDRESS`, `ORG_CONTACT`, `ORG_SIGNATORY`
- `SKU_PREFIX`
- `IMPORT_DEFAULT_PASSWORD` (optional, for user imports when CSV password is empty)
- `INTEGRATION_API_KEY` (optional, for integration endpoints)
- MySQL (optional): `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_ENGINE`, `DB_SSL_CA`
  - If `DB_NAME` is set, Django uses MySQL; otherwise it uses SQLite.
  - Azure MySQL requires SSL. Use `DB_SSL_CA=/etc/ssl/certs/ca-certificates.crt`.

Example (bash):
```bash
export DJANGO_SECRET_KEY="change-me"
export DJANGO_DEBUG="false"
export DJANGO_ALLOWED_HOSTS="example.com,www.example.com"
export ORG_NAME="Aviation Sans Frontieres"
export ORG_ADDRESS="10 Rue Exemple, 75000 Paris"
export ORG_CONTACT="contact@example.com"
export ORG_SIGNATORY="Jean Dupont"
export SKU_PREFIX="ASF"
export IMPORT_DEFAULT_PASSWORD="TempPWD!"
export INTEGRATION_API_KEY="change-me"
export DB_SSL_CA="/etc/ssl/certs/ca-certificates.crt"
```

## Scan PWA
- URL: `http://localhost:8000/scan/`
- Camera scan uses the browser BarcodeDetector (Chrome/Android recommended)
- For desktop: USB/Bluetooth scanners work as keyboard input
- Login uses the admin credentials at `/admin/login/`

## API (v1)
- Base URL: `http://localhost:8000/api/v1/`
- Auth: session (admin login) or basic auth
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
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=yourdomain.pythonanywhere.com
SITE_BASE_URL=https://yourdomain.pythonanywhere.com
ORG_NAME=Aviation Sans Frontieres
ORG_ADDRESS=10 Rue Exemple, 75000 Paris
ORG_CONTACT=contact@example.com
ORG_SIGNATORY=Jean Dupont
SKU_PREFIX=ASF
IMPORT_DEFAULT_PASSWORD=TempPWD!
INTEGRATION_API_KEY=change-me
DB_NAME=youruser$asf_wms
DB_USER=youruser
DB_PASSWORD=yourpassword
DB_HOST=youruser.mysql.pythonanywhere-services.com
DB_PORT=3306
```
