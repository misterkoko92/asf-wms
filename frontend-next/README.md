# frontend-next (P1 shell)

Frontend Next.js statique, servi en parallele de l'interface legacy.

## Objectif P1

- shell Next de production (hors prototypes),
- export statique pour PythonAnywhere,
- routes `/app/*` servies par Django,
- rollback immediat via `/ui/mode/legacy/`.

## Commandes

```bash
cd frontend-next
npm ci
npm run build
```

Le build genere `frontend-next/out`.

## Integration Django

- `/app/*` est servi par `wms.views_next_frontend.next_frontend`.
- Le frontend envoie des logs client vers `/ui/frontend-log/`.
- Le switch utilisateur est gere par `/ui/mode/{legacy|next}/`.

## Contraintes

- Pas de runtime Node en production.
- Tous les ecrans doivent rester compatibles avec `output: export`.
