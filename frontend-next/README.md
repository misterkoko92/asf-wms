# frontend-next (P2 shell)

Frontend Next.js statique, servi en parallele de l'interface legacy.

## Objectif P2

- shell Next de production (hors prototypes),
- export statique pour PythonAnywhere,
- routes `/app/*` servies par Django,
- rollback immediat via `/ui/mode/legacy/`.
- branchement progressif sur `api/v1/ui/*` (dashboard, stock, shipment, docs/labels, templates).

## Routes disponibles

- `/app/scan/dashboard`
- `/app/scan/stock`
- `/app/scan/shipment-create`
- `/app/scan/shipment-documents`
- `/app/scan/templates`
- `/app/portal/dashboard`

## Commandes

```bash
cd frontend-next
npm ci
npm run build
```

Le build genere `frontend-next/out`.

## Deploiement recommande (tout gratuit)

Priorite: build local, puis sync du seul dossier `out` vers PythonAnywhere.

```bash
PA_SSH_TARGET="youruser@ssh.pythonanywhere.com" \
PA_PROJECT_DIR="/home/youruser/asf-wms" \
deploy/pythonanywhere/push_next_export.sh
```

Ce script:

- rebuild `frontend-next`,
- synchronise `frontend-next/out` uniquement (pas de `node_modules`, pas de `.next`),
- garde l'hebergement principal Django sur PythonAnywhere.

Mode verification sans ecriture distante:

```bash
DRY_RUN=1 SKIP_BUILD=1 \
PA_SSH_TARGET="youruser@ssh.pythonanywhere.com" \
PA_PROJECT_DIR="/home/youruser/asf-wms" \
deploy/pythonanywhere/push_next_export.sh
```

## Fallback GitHub Actions (manuel)

Workflow: `.github/workflows/frontend-next-export.yml` (declenchement manuel).

Sortie:

- `next-export-<sha>.tar.gz`
- `next-export-<sha>.tar.gz.sha256`

Installation sur PythonAnywhere apres upload:

```bash
PROJECT_DIR="/home/youruser/asf-wms" \
deploy/pythonanywhere/install_next_export.sh /home/youruser/next-export-<sha>.tar.gz
```

## Integration Django

- `/app/*` est servi par `wms.views_next_frontend.next_frontend`.
- Le frontend envoie des logs client vers `/ui/frontend-log/`.
- Le switch utilisateur est gere par `/ui/mode/{legacy|next}/`.

## Contraintes

- Pas de runtime Node en production.
- Tous les ecrans doivent rester compatibles avec `output: export`.
