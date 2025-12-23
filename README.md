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

## PythonAnywhere (free tier)
- Create a new web app (Manual config)
- Use a virtualenv with Python 3.11/3.12
- Install deps: `pip install -r requirements.txt`
- Set WSGI to `asf_wms.wsgi`
- Run migrations from a Bash console
