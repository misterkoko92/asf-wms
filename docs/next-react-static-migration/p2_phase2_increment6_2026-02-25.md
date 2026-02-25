# P2 Report - Increment 6 (2026-02-25)

## Objectif

Consolider Sprint A de la phase P2 sur les deux points encore ouverts:

- compatibilite fine des permissions par role metier,
- audit trail homogene sur les mutations UI qui n'etaient pas encore tracees.

## Livrables

## 1) Matrice de permissions role par role etendue

Fichier:

- `api/tests/tests_ui_endpoints.py`

Ajouts:

- matrice scan: verification que les roles staff (`admin`, `qualite`, `magasinier`, `benevole`, `livreur`, `superuser`) passent les gates permission sur endpoints UI scan, et que `basic`/`portal` sont bloques,
- matrice templates: verification explicite `superuser` requis,
- matrice portal: verification explicite profil association requis (meme pour users staff/superuser sans profil association).

## 2) Audit trail mutation UI complete sur portal + documents

Fichier:

- `api/v1/ui_views.py`

Ajouts de logs structures (`log_workflow_event`) sur mutations critiques non couvertes auparavant:

- `ui_shipment_document_uploaded`
- `ui_shipment_document_deleted`
- `ui_portal_order_created`
- `ui_portal_recipient_created`
- `ui_portal_recipient_updated`
- `ui_portal_account_updated`

## 3) Couverture de tests d'audit associee

Fichier:

- `api/tests/tests_ui_endpoints.py`

Nouveaux cas verifies:

- emission des events d'audit lors des mutations documents expedition,
- emission des events d'audit lors des mutations portal (order/recipient/account).

## 4) Documentation migration synchronisee

Fichiers:

- `docs/next-react-static-migration/02_plan_execution.md`
- `docs/next-react-static-migration/03_matrice_parite_benev_classique.md`

Mises a jour:

- cases P2 role/audit passees en `DONE`,
- references explicites aux tests role-matrix et au nouvel increment.

## Validation executee

- `.venv/bin/python manage.py test api.tests.tests_ui_endpoints` -> OK (29 tests)
- `.venv/bin/python manage.py test api.tests` -> OK (73 tests)
- `.venv/bin/ruff check api/tests/tests_ui_endpoints.py api/v1/ui_views.py` -> OK

## Reste a faire pour P2

- etendre les scenarios E2E navigateur Playwright aux workflows metier complets (`/app/*`),
- brancher execution reguliere de ces E2E navigateur sur environnement cible (sockets + browser),
- poursuivre la parite ecran par ecran jusqu'au statut `DONE`.
