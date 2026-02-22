# P1 Report - 2026-02-22

## Objectif P1

Mettre en place le socle Next statique en parallele, sans regression sur l'interface legacy.

## Resultat P1

## 1) Frontend Next de production cree

- Nouveau dossier: `frontend-next/`
- Configuration export statique:
  - `frontend-next/next.config.mjs` -> `output: "export"`
  - `basePath: "/app"`
  - `trailingSlash: true`
- Shell navigable P1:
  - `/app/scan/dashboard/`
  - `/app/scan/stock/`
  - `/app/scan/shipment-create/`
  - `/app/portal/dashboard/`

## 2) Integration Django de `/app/*`

- Routes ajoutees dans `asf_wms/urls.py`:
  - `/app/`
  - `/app/<path:path>`
- Service statique via `wms/views_next_frontend.py`:
  - resolution securisee des fichiers exportes
  - fallback `templates/app/next_build_missing.html` si build absent

## 3) Feature flag global utilisateur `legacy | next`

- Mode utilisateur stocke en DB:
  - `UserUiPreference`
  - migration `wms/migrations/0054_useruipreference.py`
- Helpers:
  - `wms/ui_mode.py`
- Contexte template global:
  - `wms.context_processors.ui_mode_context`

## 4) Switch permanent et rollback immediat

- Endpoint switch:
  - `/ui/mode/`
  - `/ui/mode/<mode>/`
- Boutons ajoutés dans:
  - `templates/scan/base.html`
  - `templates/portal/base.html`
- Switch permanent dans le shell Next:
  - bouton "Retour interface actuelle" present sur tous les ecrans P1.

## 5) Logs front minimaux (P1)

- Endpoint de collecte:
  - `/ui/frontend-log/`
- Logs captures:
  - page view + timing de navigation,
  - erreurs JS,
  - promesses non gerees,
  - actions utilisateur taggees `data-track`.

## 6) Legacy conserve

- Aucune route legacy retiree ou renommee:
  - `/scan/*` et `/portal/*` restent operationnels.
- Coexistence parallele confirmee:
  - nouveau front sous `/app/*`.

## Points a confirmer en P1.1 (execution locale/deploiement)

- Build frontend local:
  - `cd frontend-next && npm ci && npm run build`
- Validation manuelle:
  - acces `/app/*`,
  - switch legacy/next,
  - fallback build absent.
