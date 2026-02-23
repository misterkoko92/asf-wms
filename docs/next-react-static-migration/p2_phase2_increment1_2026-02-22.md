# P2 Report - Increment 1 (2026-02-22)

## Objectif

Démarrer la phase P2 (couche API + permissions) sur le périmètre prioritaire:

- dashboard scan,
- vue stock scan,
- création expédition (options formulaire),
- dashboard portal.

## Livrables

## 1) Nouveaux endpoints `api/v1/ui/*`

Fichier: `api/v1/ui_views.py`

- `GET /api/v1/ui/dashboard/`
- `GET /api/v1/ui/stock/`
- `GET /api/v1/ui/shipments/form-options/`
- `GET /api/v1/ui/portal/dashboard/`

Routage: `api/v1/urls.py`

## 2) Permissions API par rôle

Fichier: `api/v1/permissions.py`

- `IsStaffUser` pour les endpoints scan UI.
- `IsAssociationProfileUser` pour le dashboard portal.

## 3) Frontend Next: client API typé + branchement

Nouveaux fichiers:

- `frontend-next/app/lib/api/client.ts`
- `frontend-next/app/lib/api/types.ts`
- `frontend-next/app/lib/api/ui.ts`

Composants branchés:

- `frontend-next/app/components/scan-dashboard-live.tsx`
- `frontend-next/app/components/scan-stock-live.tsx`
- `frontend-next/app/components/scan-shipment-options-live.tsx`
- `frontend-next/app/components/portal-dashboard-live.tsx`

Pages intégrées:

- `frontend-next/app/scan/dashboard/page.tsx`
- `frontend-next/app/scan/stock/page.tsx`
- `frontend-next/app/scan/shipment-create/page.tsx`
- `frontend-next/app/portal/dashboard/page.tsx`

## 4) Tests

Nouveau fichier: `api/tests/tests_ui_endpoints.py`

Cas couverts:

- permissions staff vs non staff,
- payload dashboard scan,
- payload stock scan,
- payload shipment form-options,
- permissions/payload portal dashboard.

## Validation exécutée

- `python manage.py test api.tests.tests_ui_endpoints` -> OK
- `python manage.py test api.tests` -> OK
- `cd frontend-next && npm run build` -> OK

## Reste à faire pour P2

- endpoints mutation UI (stock update/out, create/edit shipment),
- structuration uniforme des erreurs (`field_errors`, `code`, `message`),
- permissions fines par action (admin/qualité/expédition/correspondant),
- brancher les écrans Next sur flux complets CRUD métier.
