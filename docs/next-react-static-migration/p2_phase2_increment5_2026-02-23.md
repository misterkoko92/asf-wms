# P2 Report - Increment 5 (2026-02-23)

## Objectif

Poursuivre P2 en branchant le frontend Next sur les endpoints API deja exposes et en ajoutant une couverture de tests structuree en trois niveaux:

- tests par fonction (contrats serializer),
- tests intermediaires (endpoints API),
- tests E2E (workflows complets).

## Livrables Frontend Next

## 1) Nouvelles vues P2 branchees API

Fichiers:

- `frontend-next/app/scan/shipment-documents/page.tsx`
- `frontend-next/app/components/scan-shipment-documents-live.tsx`
- `frontend-next/app/scan/templates/page.tsx`
- `frontend-next/app/components/scan-print-templates-live.tsx`

Fonctionnel:

- chargement docs expedition par `shipment_id`,
- upload/suppression de documents additionnels,
- acces aux labels (global + par carton),
- liste templates impression,
- edition JSON layout + sauvegarde/reinit template.

## 2) Navigation et shell

Fichiers:

- `frontend-next/app/components/app-shell.tsx`
- `frontend-next/app/components/mode-switch.tsx`
- `frontend-next/app/page.tsx`
- `frontend-next/app/globals.css`

Ajouts:

- entrées nav `Docs & labels` et `Templates`,
- liens landing directs vers ces ecrans,
- styles utilitaires pour formulaires inline, editeur JSON, notes panel.

## Livrables Tests

## 1) Tests par fonction (niveau bas)

Fichier:

- `api/tests/tests_ui_serializers.py`

Couverture:

- `UiPrintTemplateMutationSerializer` (defaults, valid layout, invalid layout, reset).

## 2) Tests intermediaires (niveau endpoint API)

Fichier (etendu):

- `api/tests/tests_ui_endpoints.py`

Points verifies:

- shipment docs upload/delete,
- shipment labels list/detail,
- templates permissions superuser + save/reset,
- non-regression des endpoints portal/scan precedents.

## 3) Tests E2E (workflow complet)

Fichier:

- `api/tests/tests_ui_e2e_workflows.py`

Scenarios:

- workflow scan complet: MAJ stock -> creation expedition -> tracking -> docs -> labels -> cloture + template patch,
- workflow portal complet: recipient -> order -> account -> dashboard.

Matrice E2E detaillee:

- `docs/next-react-static-migration/2026-02-23_p2_e2e_suite_increment5.md`

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_serializers` -> OK
- `.venv/bin/python manage.py test api.tests.tests_ui_e2e_workflows` -> OK
- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints` -> OK
- `.venv/bin/python manage.py test api.tests` -> OK
- `cd frontend-next && npm run build` -> OK

## Reste a faire pour P2

- ajouter un harness E2E navigateur (Playwright) pour verifier les interactions UI reelles,
- connecter ces vues P2 au mode/theme switch final par role (feature flags A/B),
- finir la matrice de parite (`03_matrice_parite_benev_classique.md`) avec statuts `IN_PROGRESS/DONE`.
