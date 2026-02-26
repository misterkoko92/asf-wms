# Next Functional Parity Sprint C Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebaseliner la migration Next vers une parite strictement fonctionnelle sur l'ensemble des ecrans/boutons/fonctions, fermer les ecarts metier restants et ouvrir la refonte visuelle sous feature flag sans regression metier.

**Architecture:** Conserver Django comme source unique de logique metier, finaliser la couverture fonctionnelle complete de la matrice (`scan` + `portal` + routes dynamiques) sur routes `/app/*`, puis ajouter une couche design system progressive strictement decouplee de la logique fonctionnelle. Les ecarts visuels legacy sont traces en backlog et ne bloquent pas la validation de sprint tant que les tests metier et la recette manuelle complete passent.

**Tech Stack:** Django, Next.js (export statique), TypeScript/React, Python Playwright (`NextUiTests`), GitHub Actions, Markdown planning docs.

---

### Task 1: Fermer la parite fonctionnelle globale dans la matrice

**Files:**
- Modify: `docs/next-react-static-migration/03_matrice_parite_benev_classique.md`
- Modify: `docs/next-react-static-migration/02_plan_execution.md`
- Create: `docs/next-react-static-migration/p3_sprint_c_gap_register_2026-02-26.md`

**Step 1: Ecrire le test de coherence documentaire (attendu en echec)**

Lister tous les ecrans/routes encore `IN_PROGRESS` ou `TODO` et verifier que chaque ligne a un gap fonctionnel explicite dans le registre.

**Step 2: Lancer la verification et confirmer l'echec initial**

Run:
```bash
rg -n "\| (P1|P2|P3) \|.*\| (IN_PROGRESS|TODO)" docs/next-react-static-migration/03_matrice_parite_benev_classique.md
```
Expected: plusieurs lignes IN_PROGRESS/TODO sans registre de gaps associe.

**Step 3: Implementer le registre minimal des ecarts**

Documenter pour chaque ecran/route de la matrice:
- comportements manquants,
- tests manquants,
- owner,
- increment cible,
- critere de fermeture.

**Step 4: Relancer la verification**

Run:
```bash
rg -n "scan/dashboard|scan/stock|scan/orders|scan/receipts|scan/settings|portal/dashboard|portal/orders/detail|portal/request-account|scan/shipment/edit|scan/carton/doc" docs/next-react-static-migration/p3_sprint_c_gap_register_2026-02-26.md
```
Expected: couverture explicite des routes prioritaires et secondaires de la matrice dans le registre.

**Step 5: Commit**

```bash
git add docs/next-react-static-migration/03_matrice_parite_benev_classique.md docs/next-react-static-migration/02_plan_execution.md docs/next-react-static-migration/p3_sprint_c_gap_register_2026-02-26.md
git commit -m "docs: add sprint C functional parity gap register"
```

### Task 2: Completer les tests fonctionnels manquants sur l'ensemble du perimetre

**Files:**
- Modify: `wms/tests/core/tests_ui.py`
- Modify: `api/tests/tests_ui_endpoints.py`
- Modify: `api/tests/tests_ui_e2e_workflows.py`

**Step 1: Ecrire les tests en echec (scope global)**

Ajouter des tests qui couvrent les trous identifies dans le registre (validations bloquantes, transitions de statut, permissions fines).

**Step 2: Executer uniquement les tests ajoutes pour confirmer l'echec**

Run:
```bash
RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests -v 2
.venv/bin/python manage.py test api.tests.tests_ui_endpoints api.tests.tests_ui_e2e_workflows -v 2
```
Expected: echec sur les nouveaux cas tant que les ecarts fonctionnels ne sont pas implementes.

**Step 3: Implementer le minimum de code metier/front pour passer**

Modifier uniquement les handlers/endpoints/composants necessaires aux cas en echec.

**Step 4: Relancer la verification complete globale**

Run:
```bash
make test-next-ui
.venv/bin/python manage.py test api.tests.tests_ui_endpoints api.tests.tests_ui_e2e_workflows api.tests.tests_ui_serializers -v 2
```
Expected: PASS complet sur les suites ciblees avec couverture des routes/ecrans hors vague 1 ajoutes dans l'increment.

**Step 5: Commit**

```bash
git add wms/tests/core/tests_ui.py api/tests/tests_ui_endpoints.py api/tests/tests_ui_e2e_workflows.py
git commit -m "test: close remaining functional parity gaps across full matrix"
```

### Task 3: Fermer la recette metier manuelle globale

**Files:**
- Create: `docs/next-react-static-migration/p3_sprint_c_recette_manuelle_2026-02-26.md`
- Modify: `docs/next-react-static-migration/03_matrice_parite_benev_classique.md`

**Step 1: Ecrire une checklist manuelle en echec (non validee)**

Creer la checklist par ecran/role avec colonnes `Resultat`, `Preuve`, `Bloquant` initialement vides.

**Step 2: Executer les parcours manuels et capturer les resultats**

Run:
```bash
# execution manuelle guidee selon la checklist
```
Expected: premier passage complet multi-roles (staff + association + admin) sur l'ensemble du perimetre cible de l'increment.

**Step 3: Reporter les anomalies dans le gap register**

Lier chaque anomalie au fichier `p3_sprint_c_gap_register_2026-02-26.md` avec priorite et owner.

**Step 4: Marquer les points valides dans la matrice**

Run:
```bash
rg -n "recette metier manuelle complete" docs/next-react-static-migration/03_matrice_parite_benev_classique.md
```
Expected: item present et passe a `[x]` quand la recette est complete.

**Step 5: Commit**

```bash
git add docs/next-react-static-migration/p3_sprint_c_recette_manuelle_2026-02-26.md docs/next-react-static-migration/03_matrice_parite_benev_classique.md docs/next-react-static-migration/p3_sprint_c_gap_register_2026-02-26.md
git commit -m "docs: complete sprint C manual business recipe across full matrix"
```

### Task 4: Demarrer la refonte visuelle sous feature flag sans impacter le metier

**Files:**
- Modify: `frontend-next/app/globals.css`
- Modify: `frontend-next/app/components/app-shell.tsx`
- Create: `frontend-next/app/lib/design-tokens.ts`
- Create: `frontend-next/app/lib/feature-flags.ts`

**Step 1: Ecrire un test de non-regression en echec**

Ajouter une verification Playwright que les actions critiques (stock update, shipment create, tracking close) restent operables quand le flag visuel est actif.

**Step 2: Lancer le test cible et confirmer l'echec initial**

Run:
```bash
RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests -v 2
```
Expected: echec tant que le flag visuel n'est pas cable proprement.

**Step 3: Implementer tokens + flag + variante visuelle minimale**

Introduire les tokens et une variante de skin desactivee par defaut, sans modifier schemas de donnees ni appels API.

**Step 4: Verifier build + regression metier**

Run:
```bash
cd frontend-next && npm run build
cd .. && make test-next-ui
```
Expected: build OK, tests UI metier OK, aucun changement de comportement fonctionnel.

**Step 5: Commit**

```bash
git add frontend-next/app/globals.css frontend-next/app/components/app-shell.tsx frontend-next/app/lib/design-tokens.ts frontend-next/app/lib/feature-flags.ts wms/tests/core/tests_ui.py
git commit -m "feat: add visual redesign flag with functional safety checks"
```

### Task 5: Ouvrir le pilote controle et mesurer les KPI

**Files:**
- Modify: `docs/next-react-static-migration/04_bascule_progressive_et_rollback.md`
- Create: `docs/next-react-static-migration/p5_pilot_kpi_scorecard_2026-02-26.md`
- Modify: `.github/workflows/next-ui-browser-e2e.yml`

**Step 1: Ecrire les criteres pilote en echec (non atteints)**

Definir KPI cibles (erreurs, temps de completion flux, rollback, incidents bloquants) avec seuils numeriques.

**Step 2: Activer collecte et verifier qu'elle tourne**

Run:
```bash
make test-next-ui
```
Expected: suite verte avant ouverture pilote, puis suivi quotidien des KPI.

**Step 3: Lancer pilote sur groupe restreint**

Activer le mode Next pour un sous-ensemble d'utilisateurs via feature flag utilisateur.

**Step 4: Evaluer resultat go/no-go**

Mettre a jour la scorecard quotidiennement pendant 5 jours ouvres.
Expected: aucun blocant metier, KPI >= baseline legacy.

**Step 5: Commit**

```bash
git add docs/next-react-static-migration/04_bascule_progressive_et_rollback.md docs/next-react-static-migration/p5_pilot_kpi_scorecard_2026-02-26.md .github/workflows/next-ui-browser-e2e.yml
git commit -m "docs: define sprint C pilot KPI scorecard and rollout gates"
```
