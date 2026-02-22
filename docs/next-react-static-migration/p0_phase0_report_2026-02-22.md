# P0 Report - 2026-02-22

## Contexte

Phase 0 lancée pour préparer la migration vers Next/React statique (frontend parallèle), avec objectif de **copie conforme intégrale Benev/Classique** avant toute amélioration visuelle.

## Résultat P0 (au 2026-02-22)

## 1) Inventaire technique consolidé

- Routes legacy inventoriées:
  - `scan`: 38 routes (`/scan/*`)
  - `portal`: 10 routes (`/portal/*`)
- Templates legacy inventoriés:
  - `templates/scan`: 24
  - `templates/portal`: 9
  - `templates/print`: 14
- Permissions réelles consolidées:
  - staff scan via `scan_staff_required`
  - portail association via `association_required`

## 2) Baseline tests de non-régression (exécutée)

Commandes exécutées:

```bash
.venv/bin/python manage.py test \
  wms.tests.views.tests_views_scan_dashboard \
  wms.tests.views.tests_views_scan_stock \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.views.tests_views_tracking_dispute \
  wms.tests.views.tests_views_portal
```

Résultat:

- `96 tests`
- `OK`
- durée `~60.7s`

Commande API exécutée:

```bash
.venv/bin/python manage.py test api.tests
```

Résultat:

- `38 tests`
- `OK`
- durée `~15.5s`

Complément:

```bash
.venv/bin/python manage.py test wms.tests.core.tests_flow
```

Résultat:

- `1 test`
- `OK`

## 3) Livrables produits en P0

- `docs/next-react-static-migration/p0_inventaire_fonctionnel.md`
- `docs/next-react-static-migration/p0_api_gap_analysis.md`
- `docs/next-react-static-migration/p0_e2e_suite.md`
- `docs/next-react-static-migration/p0_baseline_visuelle_checklist.md`

## 4) Décisions P0 confirmées

- Migration en parallèle (aucune interférence legacy).
- Legacy reste disponible en permanence.
- Feature flag global utilisateur pour bascule.
- Bascule progressive par module/rôle.
- Parité stricte avant redesign.

## 5) Risques P0 identifiés

- API `v1` actuelle incomplète pour couvrir tout le front Next (voir gap analysis).
- Éditeur templates actuel: logique exploitable mais UX limitée pour usage non-technique.
- Captures visuelles de référence à industrialiser (checklist créée).

## 6) Statut de sortie P0

- Inventaire flux/permissions/formulaires: `OK`
- Baseline tests critiques: `OK`
- Matrice E2E critique: `OK`
- Gap API + plan d’extension: `OK`
- Baseline visuelle outillée: `PARTIAL` (checklist prête, script capture à brancher dans phase suivante)

## Recommandation de passage en P1

Go pour P1 (socle Next statique parallèle), en démarrant par:

1. création du frontend Next de production hors `docs/ui-prototypes`,
2. routage `/app/*` côté Django,
3. feature flag utilisateur `ui_mode`,
4. écrans prioritaires en parité stricte:
   - dashboard,
   - vue stock,
   - création expédition.
