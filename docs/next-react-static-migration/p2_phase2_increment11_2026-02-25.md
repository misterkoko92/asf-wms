# P2 Report - Increment 11 (2026-02-25)

## Objectif

Clore Sprint A en branchant l'execution reguliere des scenarios navigateur Playwright (`NextUiTests`) sur environnement cible CI.

## Livrables

## 1) Workflow GitHub Actions dedie Next UI Browser E2E

Fichier:

- `.github/workflows/next-ui-browser-e2e.yml`

Comportement:

- declenchement manuel (`workflow_dispatch`),
- declenchement planifie quotidien (cron `03:30 UTC`),
- setup Python + Node,
- installation Playwright + navigateur Chromium,
- build `frontend-next/out`,
- execution `RUN_UI_TESTS=1 python manage.py test wms.tests.core.tests_ui.NextUiTests`.

## 2) Documentation migration synchronisee

Fichiers:

- `docs/next-react-static-migration/02_plan_execution.md`
- `docs/next-react-static-migration/03_matrice_parite_benev_classique.md`
- `docs/next-react-static-migration/README.md`

Mises a jour:

- point "execution reguliere E2E navigateur" marque comme couvert,
- ajout de cet increment dans la liste des livrables P2.

## Validation executee

- verification YAML/structure workflow local (`next-ui-browser-e2e.yml`),
- non regression locale des workflows navigateur deja valides sur increment 10:
  - `RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests` -> OK
  - `make test-next-ui` -> OK

## Reste a faire pour Sprint A / P2

- aucun item Sprint A restant; prochaine etape = pilotage de la phase de parite stricte.
