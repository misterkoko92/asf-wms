# Migration Benev/Classique vers Next React statique

## Etat actuel (2026-02-25)

- `P0`: termine
- `P1`: termine
- `P2`: en cours (backend API avance + branchement front partiel)
- `P3`: en cours (parite stricte en construction)
- `P4+`: non demarre

Capacites utilisables des maintenant (dev):

- ecrans Next: `/app/scan/dashboard/`, `/app/scan/stock/`, `/app/scan/cartons/`, `/app/scan/shipment-create/`, `/app/scan/shipments-ready/`, `/app/scan/shipments-tracking/`, `/app/scan/shipment-documents/`, `/app/scan/templates/`, `/app/portal/dashboard/`
- API UI: stock, expedition, tracking, cloture, portal mutations, documents/labels, templates
- switch permanent legacy/next conserve

Niveau de maturite:

- bout en bout valide en tests API (workflow scan + portal),
- workflows UI navigateur critiques couverts en progression (dashboard live, stock mutations + filtres, cartons/shipments-ready/shipments-tracking dedies, shipment create avec creation colis inline, portal mutations),
- dashboard scan branche avec filtre destination (legacy) cote Next,
- dashboard scan branche avec filtre periode KPI (legacy) cote Next,
- dashboard scan enrichi avec section KPI periode (cartes activite),
- dashboard scan enrichi avec section expeditions (cartes metier legacy),
- dashboard scan enrichi avec section colis (cartes metier legacy),
- dashboard scan enrichi avec section receptions/commandes (cartes metier legacy),
- dashboard scan enrichi avec section suivi/alertes (cartes metier legacy),
- dashboard scan enrichi avec section graphique expeditions (repartition statuts),
- dashboard scan enrichi avec section stock sous seuil (table low stock),
- route `shipments-ready` branchee avec action d'archivage des brouillons stale,
- route `shipments-ready` alignee sur les liens Documents legacy (menu + 4 liens),
- route `shipments-tracking` branchee en live API avec filtres semaine/clos + table suivi + actions tracking/cloture,
- route `shipments-tracking` alignee sur les etats visuels de cloture (closable/bloque/deja clos),
- parite ecran stricte Next vs Benev/Classique encore en cours.

## Objectif
Basculer l'interface actuelle `Benev + Classique` vers un frontend Next/React **statique**, tout en gardant Django/PythonAnywhere comme backend principal, avec ces règles:

- **Copie conforme intégrale** (fonctionnelle et visuelle) en priorité.
- **Aucune régression métier**.
- **Aucune interruption**: l'interface actuelle reste disponible en permanence.
- **Migration parallèle**: nouveau front sous préfixe dédié + feature flag utilisateur.

## Décisions validées

- Frontend: Next.js + React, build statique.
- Backend: Django existant (logique métier, auth, PDF, règles).
- Hébergement: PythonAnywhere conservé.
- Stratégie de bascule: progressive (module par module, rôle par rôle), rollback immédiat possible.

## Livrables de ce dossier

1. `docs/next-react-static-migration/01_architecture_cible.md`
   - Architecture cible, contraintes PythonAnywhere, sécurité, offline.
2. `docs/next-react-static-migration/02_plan_execution.md`
   - Plan d'exécution détaillé en phases avec critères de sortie.
3. `docs/next-react-static-migration/03_matrice_parite_benev_classique.md`
   - Mapping écran par écran (legacy -> next) + checklist de parité.
4. `docs/next-react-static-migration/04_bascule_progressive_et_rollback.md`
   - Déploiement progressif, A/B, supervision et rollback.
5. `docs/next-react-static-migration/05_roadmap_apres_parite.md`
   - Ajustements UI (boutons/cards) puis éditeur de templates nouvelle génération.

## Livrables Phase 0 (réalisés)

- `docs/next-react-static-migration/p0_phase0_report_2026-02-22.md`
- `docs/next-react-static-migration/p0_inventaire_fonctionnel.md`
- `docs/next-react-static-migration/p0_api_gap_analysis.md`
- `docs/next-react-static-migration/p0_e2e_suite.md`
- `docs/next-react-static-migration/p0_baseline_visuelle_checklist.md`

## Livrables Phase 1 (réalisés)

- `docs/next-react-static-migration/p1_phase1_report_2026-02-22.md`

## Livrables Phase 2 (en cours)

- `docs/next-react-static-migration/p2_phase2_increment1_2026-02-22.md`
- `docs/next-react-static-migration/p2_phase2_increment2_2026-02-22.md`
- `docs/next-react-static-migration/p2_phase2_increment3_2026-02-23.md`
- `docs/next-react-static-migration/p2_phase2_increment4_2026-02-23.md`
- `docs/next-react-static-migration/p2_phase2_increment5_2026-02-23.md`
- `docs/next-react-static-migration/p2_phase2_increment6_2026-02-25.md`
- `docs/next-react-static-migration/p2_phase2_increment7_2026-02-25.md`
- `docs/next-react-static-migration/p2_phase2_increment8_2026-02-25.md`
- `docs/next-react-static-migration/p2_phase2_increment9_2026-02-25.md`
- `docs/next-react-static-migration/p2_phase2_increment10_2026-02-25.md`
- `docs/next-react-static-migration/p2_phase2_increment11_2026-02-25.md`
- `docs/next-react-static-migration/2026-02-23_p2_e2e_suite_increment5.md`

## Livrables Phase 3 (en cours)

- `docs/next-react-static-migration/p3_phase3_increment1_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment2_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment3_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment4_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment5_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment6_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment7_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment8_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment9_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment10_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment11_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment12_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment13_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment14_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment15_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment16_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment17_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment18_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment19_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment20_2026-02-25.md`
- `docs/next-react-static-migration/p3_phase3_increment21_2026-02-25.md`

## Prochaine cible

- finaliser la parite stricte des 3 ecrans prioritaires (dashboard, stock, creation expedition),
- completer les ecrans portal restants,
- lancer un pilote A/B avec KPI.

## Ordre d'exécution recommandé

1. Phase parité stricte (100% Benev/Classique).
2. Bascule limitée à un groupe pilote.
3. Stabilisation et généralisation.
4. Ajustements visuels ciblés.
5. Refonte de l'éditeur de templates.

## Principe de sécurité projet

Tant que la parité n'est pas validée par toi:

- l'ancien front reste la référence de production,
- le switch reste réversible instantanément,
- aucune suppression de template legacy n'est autorisée.
