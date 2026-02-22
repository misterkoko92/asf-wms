# 02 - Plan d'exécution détaillé

## Cadrage global

- Priorité: **copie conforme intégrale Benev/Classique**.
- Contrainte: **ne pas casser le legacy**.
- Méthode: migration parallèle, incrémentale, pilotée par critères de sortie.

## Phases

## Phase 0 - Inventaire et baseline (J0 -> J2)

### Objectif
Figer le périmètre de parité avant tout développement.

### Tâches

- [ ] Geler la liste des écrans et flux à migrer (scan + portal).
- [ ] Capturer la baseline visuelle et fonctionnelle des écrans legacy.
- [ ] Lister champs/validations/règles/permissions par écran.
- [ ] Définir les KPI de migration:
  - clics par action,
  - temps de création expédition,
  - visibilité des actions en attente.
- [ ] Définir la stratégie de test de parité (fonctionnel + visuel).

### Critères de sortie

- Matrice de parité complète validée.
- Liste des écarts API connue.
- Scénarios E2E critiques validés sur legacy.

---

## Phase 1 - Socle Next statique en parallèle (J2 -> J4)

### Objectif
Avoir un shell Next déployable sur PythonAnywhere sans impacter l'existant.

### Tâches

- [x] Créer le frontend Next de production (hors dossier prototypes).
- [x] Configurer build statique (`output: export`).
- [x] Configurer intégration Django pour servir `/app/*`.
- [x] Implémenter feature flag global `legacy | next`.
- [x] Ajouter switch permanent "Retour interface actuelle".
- [x] Mettre en place logs front (erreurs JS, timings, trace actions).

### Critères de sortie

- `/scan/*` et `/portal/*` legacy inchangés.
- `/app/*` accessible en parallèle.
- Rollback immédiat par switch utilisateur.

---

## Phase 2 - Couche API et permissions (J4 -> J7)

### Objectif
Permettre au nouveau front d'appeler le backend sans dupliquer la logique métier.

### Tâches

- [ ] Construire client API typé (stock, colis, expédition, documents, tracking).
- [ ] Ajouter endpoints manquants côté Django (si page aujourd'hui pure HTML).
- [ ] Vérifier compatibilité rôles: admin, qualité, magasinier, bénévole, livreur.
- [ ] Uniformiser les codes d'erreur API.
- [ ] Implémenter audit trail côté backend pour actions critiques.

### Critères de sortie

- 100% des actions critiques de l'app utilisent API stable.
- Validation métier backend unique (pas de divergence front/back).

---

## Phase 3 - Parité fonctionnelle stricte écrans prioritaires (J7 -> J12)

### Objectif
Migrer en priorité les 3 pages business cibles.

### Écrans

- Dashboard.
- Création expédition.
- Vue stock.

### Tâches

- [ ] Reproduire structure UI/UX Benev/Classique à l'identique.
- [ ] Reproduire libellés, formulaires, validations, états, permissions.
- [ ] Intégrer actions 1 clic demandées:
  - MAJ stock,
  - création colis,
  - création expédition,
  - affectation colis,
  - MAJ statut.
- [ ] Implémenter mode offline mobile pour stock.

### Critères de sortie

- Démo pilote utilisable de bout en bout.
- KPI minimum atteints sur flux principal.
- Aucun blocant fonctionnel vs legacy.

---

## Phase 4 - Parité fonctionnelle complète scan + portal (J12 -> J20)

### Objectif
Couvrir tout le périmètre fonctionnel Benev/Classique.

### Tâches

- [ ] Migrer tous les écrans listés dans la matrice.
- [ ] Gérer cas d'exception critiques:
  - parties non conformes,
  - documents manquants,
  - stock insuffisant.
- [ ] Implémenter parcours complet:
  - dashboard,
  - vue stock,
  - mise à jour stock,
  - création colis,
  - création expédition,
  - affectation colis,
  - suivi,
  - clôture.

### Critères de sortie

- 100% des flux critiques passent sur Next sans retour arrière forcé.
- Diff de comportement = 0 sur règles métier attendues.

---

## Phase 5 - Pilote contrôlé + A/B test (J20 -> J24)

### Objectif
Valider en conditions réelles sans risque.

### Tâches

- [ ] Activer le nouveau front pour groupe pilote (feature flag par utilisateur).
- [ ] Mesurer KPI vs legacy.
- [ ] Recueillir feedback métier quotidien.
- [ ] Corriger écarts de parité et stabilité.

### Critères de sortie

- Aucun incident bloquant sur 5 jours ouvrés.
- KPI égaux ou meilleurs que legacy.
- Validation explicite de ta part.

---

## Phase 6 - Ajustements UI ciblés (après parité)

### Objectif
Améliorer progressivement boutons, cards, densité, lisibilité sans casser la logique.

### Tâches

- [ ] Introduire design tokens (couleurs, radius, spacing, typographie).
- [ ] Créer variantes de composants (`button`, `card`, `table`, `alert`) sans toucher les flux.
- [ ] Tester variations par feature flag visuel.

### Critères de sortie

- UX plus moderne validée.
- Pas de régression fonctionnelle.

---

## Phase 7 - Éditeur de templates documentaire (chantier dédié)

### Objectif
Résoudre le point faible majeur: création/édition de templates plus souple.

### Tâches

- [ ] Définir schéma de templates versionnés.
- [ ] Créer éditeur hybride (blocs + zones libres).
- [ ] Ajouter placeholders métier (expédition, colis, contacts, douane, donation).
- [ ] Prévisualisation PDF live.
- [ ] Validation et publication de versions.

### Critères de sortie

- Création de templates sans code.
- Cycle complet: brouillon -> preview -> publication.
- Compatibilité avec génération documentaire existante.

## Gouvernance

## Rituels

- Standup court quotidien (blocants, risques, décisions).
- Revue hebdo parité (legacy vs next).
- Revue métier hebdo (toi + retours terrain).

## Definition of Done (chaque écran)

- [ ] UI conforme Benev/Classique.
- [ ] Données et validations conformes.
- [ ] Permissions conformes.
- [ ] E2E nominal + exceptions passent.
- [ ] Capture visuelle validée.
- [ ] Rollback possible sans migration.
