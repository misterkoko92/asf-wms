# Récapitulatif Phases 0 à 3

Document de synthèse des lots effectivement implémentés sur `main`.

## Phase 0 - Stabilisation release

Objectif:

- Revenir à une base livrable (tests alignés avec les règles métier récentes).

Changements majeurs:

- Suite de tests stabilisée (régressions tags/portail/labels corrigées).
- Ajustements portail/commandes/destinataires et synchronisation métier.
- Finalisation migrations/statiques associées à l'évolution portail.
- Correction stock réservé: édition d'expédition liée à commande consomme correctement la réservation.

Commits de référence:

- `58e5342`
- `f8b560d`
- `ae6af86`

Impact:

- Base de release stabilisée, sans incohérence visible entre commandes, réservations et expéditions.

## Phase 1 - Durcissement contacts / portail

Objectif:

- Clarifier et sécuriser le domaine de portée destinations et la synchro portail -> contacts.

Changements majeurs:

- Source de vérité destination normalisée via `contacts/destination_scope.py` (M2M prioritaire).
- Commande d'audit/correction: `audit_contact_destinations` (`--apply` disponible).
- Renforcement de la synchro destinataires portail -> contacts (idempotence/non-régression).
- Tests métier E2E renforcés (portail -> validation admin -> expédition préremplie).

Commit de référence:

- `0a9baba`

Impact:

- Fiabilité accrue des sélecteurs et des règles shipper/destinataire/correspondant dans la création d'expédition.

## Phase 2 - Nettoyage architecture / legacy

Objectif:

- Réduire la complexité structurelle et encadrer les chemins legacy.

Changements majeurs:

- Lot 1: découpage `wms/models.py` vers `wms/models_domain/*` avec façade de compatibilité.
- Lot 2: découpage `wms/admin.py` et extraction des helpers scan expédition.
- Lot 3:
  - feature flag `ENABLE_SHIPMENT_TRACK_LEGACY`,
  - headers de dépréciation sur endpoint legacy,
  - alignement exports contacts sur la portée destinations M2M,
  - homogénéisation FR/accents.

Commits de référence:

- `4498ab0`
- `100e211`
- `72ed523`

Impact:

- Code plus maintenable, meilleure isolation des responsabilités, trajectoire de retrait legacy sécurisée.

## Phase 3 - Observabilité et exploitation

Objectif:

- Donner une visibilité opérationnelle continue et tracer les transitions métier.

Changements majeurs:

- Dashboard enrichi (`/scan/dashboard`):
  - queue email (pending/processing/failed/timeout),
  - blocages workflow >72h,
  - KPI SLA (Planifié -> OK mise à bord -> Reçu escale -> Livré).
- Journalisation métier structurée (`logger` `wms.workflow`) pour:
  - transitions statut colis,
  - transitions statut expédition,
  - actions litige,
  - événements de suivi,
  - clôture de dossier.
- Playbooks ops enrichis (`docs/operations.md`).
- Tests ciblés ajoutés/renforcés.

Commit de référence:

- `fd4db1d`

Impact:

- Exploitation plus proactive (détection des blocages, lecture SLA, diagnostic via logs structurés).

## Validation globale (état après phase 3)

- `python manage.py check`: OK
- `python manage.py makemigrations --check --dry-run`: OK
- `python manage.py test`: OK (`928` tests, `2` skipped)
