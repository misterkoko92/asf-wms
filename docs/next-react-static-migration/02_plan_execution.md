# 02 - Plan d'execution detaille (mis a jour 2026-02-25)

## Cadrage global

- Priorite: copie conforme integrale Benev/Classique.
- Contrainte: ne pas casser le legacy.
- Methode: migration parallele incrementale, pilotee par criteres de sortie.

## Etat global (P0 -> P7)

- Phase 0: `DONE`
- Phase 1: `DONE`
- Phase 2: `IN_PROGRESS` (couche API UI largement livree, derniers points role/audit a finaliser)
- Phase 3: `IN_PROGRESS` (ecrans prioritaires presents, parite stricte non atteinte)
- Phase 4+: `TODO`

## Capacites disponibles aujourd'hui (en environnement de dev)

Front Next parallel (sans impact legacy):

- `/app/scan/dashboard/`
- `/app/scan/stock/`
- `/app/scan/cartons/`
- `/app/scan/shipment-create/`
- `/app/scan/shipments-ready/`
- `/app/scan/shipments-tracking/`
- `/app/scan/shipment-documents/`
- `/app/scan/templates/`
- `/app/portal/dashboard/`

Couche API UI livree:

- dashboard/stock/shipments (create, update, tracking, close)
- shipment documents + labels
- portal (dashboard, order create, recipients, account)
- print templates (list/detail/update, superuser)

Tests en place:

- tests API endpoint (`api.tests.tests_ui_endpoints`)
- tests workflow E2E API (`api.tests.tests_ui_e2e_workflows`)
- tests fonction serializer (`api.tests.tests_ui_serializers`)

Important:

- workflow complet valide aujourd'hui **au niveau API**,
- couverture UI navigateur en progression (dashboard live + filtres destination/periode KPI + bloc KPI periode + bloc expeditions + bloc colis + bloc receptions/commandes + bloc graphique expeditions + bloc stock sous seuil, stock mutations+filtres, cartons/shipments-ready/shipments-tracking dedies avec table live + filtres suivi + etats visuels de cloture, archivage stale drafts + menu documents legacy sur shipments-ready, shipment create + creation colis inline, portal mutations), parite ecran stricte restante.

## Phase 0 - Inventaire et baseline (J0 -> J2)

### Objectif
Figer le perimetre de parite avant tout developpement.

### Taches

- [x] Geler la liste des ecrans et flux a migrer (scan + portal).
- [x] Capturer la baseline fonctionnelle des ecrans legacy.
- [x] Lister champs/validations/regles/permissions par ecran.
- [x] Definir les KPI de migration.
- [x] Definir la strategie de test de parite (fonctionnel + visuel).

### Criteres de sortie

- Matrice de parite complete: `OK`
- Liste des ecarts API connue: `OK`
- Scenarios E2E critiques legacy definis: `OK`
- Baseline visuelle automatisee: `PARTIAL` (checklist prete, industrialisation a finaliser)

Livrables:

- `p0_phase0_report_2026-02-22.md`
- `p0_inventaire_fonctionnel.md`
- `p0_api_gap_analysis.md`
- `p0_e2e_suite.md`
- `p0_baseline_visuelle_checklist.md`

---

## Phase 1 - Socle Next statique en parallele (J2 -> J4)

### Objectif
Avoir un shell Next deployable sur PythonAnywhere sans impacter l'existant.

### Taches

- [x] Creer le frontend Next de production (hors prototypes).
- [x] Configurer build statique (`output: export`).
- [x] Configurer integration Django pour servir `/app/*`.
- [x] Implementer feature flag global `legacy | next`.
- [x] Ajouter switch permanent "Retour interface actuelle".
- [x] Mettre en place logs front (erreurs JS, timings, trace actions).

### Criteres de sortie

- `/scan/*` et `/portal/*` legacy inchanges: `OK`
- `/app/*` accessible en parallele: `OK`
- rollback immediat par switch utilisateur: `OK`

Livrable:

- `p1_phase1_report_2026-02-22.md`

---

## Phase 2 - Couche API et permissions (J4 -> J7)

### Objectif
Permettre au nouveau front d'appeler le backend sans dupliquer la logique metier.

### Taches

- [x] Construire client API type (stock, expedition, portal, docs, templates).
- [x] Ajouter endpoints manquants cote Django sur perimetre prioritaire P2.
- [x] Verifier compatibilite fine tous roles (admin, qualite, magasinier, benevole, livreur) sur tous endpoints UI.
- [x] Uniformiser les codes d'erreur API (`ok/code/message/field_errors/non_field_errors`).
- [x] Completer audit trail sur toutes actions critiques (mutations portal/documents + traces existantes stock/expedition/templates).

### Criteres de sortie

- Couverture actions critiques backend: `OK` (tests role-matrix + audit trail mutations UI consolides)
- Validation metier backend unique: `OK` (reutilisation handlers/services existants)

Reste concret P2:

- [x] etendre les tests permissions role par role (`api/tests/tests_ui_endpoints.py`),
- [x] finaliser la trace d'audit sur mutations UI restantes (`log_workflow_event` sur mutations portal/documents),
- [x] lancer un premier harness E2E navigateur Playwright sur routes `/app/*` (`wms/tests/core/tests_ui.py::NextUiTests`, `make test-next-ui`),
- [x] etendre les scenarios navigateur E2E aux workflows metier complets (stock, expedition, portal) - `OK`: workflows documents/templates/stock(update+out)/shipment(create+tracking+close)/portal(order+recipients+account) couverts.
- [x] brancher execution reguliere des scenarios navigateur sur environnement cible (GitHub Actions planifie): `.github/workflows/next-ui-browser-e2e.yml`.

Livrables:

- `p2_phase2_increment1_2026-02-22.md`
- `p2_phase2_increment2_2026-02-22.md`
- `p2_phase2_increment3_2026-02-23.md`
- `p2_phase2_increment4_2026-02-23.md`
- `p2_phase2_increment5_2026-02-23.md`
- `p2_phase2_increment6_2026-02-25.md`
- `p2_phase2_increment7_2026-02-25.md`
- `p2_phase2_increment8_2026-02-25.md`
- `p2_phase2_increment9_2026-02-25.md`
- `p2_phase2_increment10_2026-02-25.md`
- `p2_phase2_increment11_2026-02-25.md`

---

## Phase 3 - Parite fonctionnelle stricte ecrans prioritaires (J7 -> J12)

### Objectif
Migrer en priorite les 3 pages business cibles.

### Ecrans cibles

- Dashboard.
- Creation expedition.
- Vue stock.

### Taches

- [ ] Reproduire structure UI/UX Benev/Classique a l'identique.
- [ ] Reproduire libelles, formulaires, validations, etats, permissions.
- [ ] Integrer completement les actions 1 clic:
  - MAJ stock,
  - creation colis,
  - creation expedition,
  - affectation colis,
  - MAJ statut.
- [ ] Implementer mode offline mobile pour stock.

Etat factuel:

- ecrans Next presents mais encore hybrides (maquette + branchements API),
- actions metier critiques majeures des ecrans prioritaires davantage couvertes (dashboard avec filtres destination/periode KPI + bloc KPI periode + bloc expeditions + bloc colis + bloc receptions/commandes + bloc graphique expeditions + bloc stock sous seuil, stock mutations + filtres sur `scan/stock`, creation colis inline sur `shipment-create`, table live + filtres suivi + etats visuels de cloture sur `scan/shipments-tracking`, archivage stale drafts + menu documents legacy sur `scan/shipments-ready`),
- parite visuelle stricte non validee.

### Criteres de sortie

- Demo pilote utilisable de bout en bout: `IN_PROGRESS`
- KPI minimum atteints sur flux principal: `TODO`
- Aucun blocant fonctionnel vs legacy: `TODO`

Etat courant:

- les ecrans existent en Next avec connexions API partielles,
- la parite stricte visuelle/fonctionnelle n'est pas encore validee.

---

## Phase 4 - Parite fonctionnelle complete scan + portal (J12 -> J20)

### Objectif
Couvrir tout le perimetre fonctionnel Benev/Classique.

### Taches

- [ ] Migrer tous les ecrans listes dans la matrice.
- [ ] Gerer cas d'exception critiques:
  - parties non conformes,
  - documents manquants,
  - stock insuffisant.
- [ ] Implementer parcours complet:
  - dashboard,
  - vue stock,
  - mise a jour stock,
  - creation colis,
  - creation expedition,
  - affectation colis,
  - suivi,
  - cloture.

### Criteres de sortie

- 100% flux critiques passent sur Next sans retour arriere force.
- Diff de comportement metier = 0 vs legacy.

Statut: `TODO`

---

## Phase 5 - Pilote controle + A/B test (J20 -> J24)

### Objectif
Valider en conditions reelles sans risque.

### Taches

- [ ] Activer le nouveau front pour groupe pilote (feature flag utilisateur).
- [ ] Mesurer KPI vs legacy.
- [ ] Recueillir feedback metier quotidien.
- [ ] Corriger ecarts de parite et stabilite.

### Criteres de sortie

- Aucun incident bloquant sur 5 jours ouvres.
- KPI egaux ou meilleurs que legacy.
- Validation explicite de ta part.

Statut: `TODO`

---

## Phase 6 - Ajustements UI cibles (apres parite)

### Objectif
Ameliorer progressivement boutons, cards, densite, lisibilite sans casser la logique.

### Taches

- [ ] Introduire design tokens (couleurs, radius, spacing, typo).
- [ ] Creer variantes de composants (`button`, `card`, `table`, `alert`).
- [ ] Tester variations par feature flag visuel.

### Criteres de sortie

- UX plus moderne validee.
- Pas de regression fonctionnelle.

Statut: `TODO`

---

## Phase 7 - Editeur de templates documentaire (chantier dedie)

### Objectif
Resoudre le point faible majeur: creation/edition de templates plus souple.

### Taches

- [ ] Definir schema de templates versionnes.
- [ ] Creer editeur hybride (blocs + zones libres).
- [ ] Ajouter placeholders metier (expedition, colis, contacts, douane, donation).
- [ ] Previsualisation PDF live.
- [ ] Validation et publication de versions.

### Criteres de sortie

- Creation de templates sans code.
- Cycle complet: brouillon -> preview -> publication.
- Compatibilite avec generation documentaire existante.

Statut: `TODO`

---

## Gouvernance

### Rituels

- Standup court quotidien (blocants, risques, decisions).
- Revue hebdo parite (legacy vs next).
- Revue metier hebdo (toi + retours terrain).

### Definition of Done (par ecran)

- [ ] UI conforme Benev/Classique.
- [ ] Donnees et validations conformes.
- [ ] Permissions conformes.
- [ ] E2E nominal + exceptions passent.
- [ ] Capture visuelle validee.
- [ ] Rollback possible sans migration.
