# 01 - Architecture cible (Next statique + Django/PythonAnywhere)

## Statut implementation (2026-02-23)

- socle parallel Next/Django: `DONE`
- feature flag/switch legacy-next: `DONE`
- couche API UI prioritaire: `IN_PROGRESS` (avancee, couverture principale en place)
- mode offline PWA: `TODO`

## 1) Architecture de référence

```
Utilisateurs (mobile / tablette / desktop)
            |
            v
   PythonAnywhere (même domaine)
   ├─ Django (backend principal)
   │  ├─ Auth/session/permissions
   │  ├─ Logique métier WMS (stock, colis, expédition, tracking, clôture)
   │  ├─ API JSON (existantes + endpoints complémentaires)
   │  └─ Génération documentaire/PDF
   └─ Static hosting
      └─ Build Next exporté (HTML/CSS/JS)
```

## 2) Contrainte clé du mode statique

Pas de runtime Node en production. Donc:

- pages Next pré-générées au build,
- navigation métier orientée routes statiques + paramètres (`query string`) quand nécessaire,
- logique dynamique via appels API côté client.

Implication pratique: les écrans type `.../<id>/edit/` peuvent être servis en Next via une route stable (ex: `/app/scan/shipment/edit?id=123`) pour rester compatibles avec l'export statique.

## 3) Coexistence sans impact avec l'existant

- Legacy conservé sous ses URLs actuelles (`/scan/*`, `/portal/*`).
- Nouveau front sous préfixe dédié (recommandé): `/app/*`.
- Feature flag utilisateur global: `ui_mode = legacy | next`.
- Bouton visible en permanence pour revenir à `legacy`.

## 4) Contrat backend

### 4.1 Rôle de Django

- Source unique de vérité métier.
- Validation serveur inchangée.
- Permissions/rôles inchangés.
- Journal d'audit inchangé.

### 4.2 API

- Réutiliser `api/v1` existante.
- Ajouter des endpoints spécifiques pour combler les pages aujourd'hui rendues uniquement en template.
- Stabiliser les payloads via DTO versionnés (`v1`), sans casser les vues legacy.

Etat reel:

- endpoints UI actifs sous `/api/v1/ui/*` pour dashboard, stock, shipments, docs/labels, templates et portal.
- logique metier centralisee conservee dans Django (forms/handlers/services legacy reutilises).

## 5) Auth, sécurité, conformité

- Session Django existante conservée.
- API appelée avec cookies + CSRF.
- Aucune exposition de secrets côté Next.
- Masquage des données sensibles (contacts) au niveau API selon rôle.
- Logging d'audit conservé côté backend.

## 6) Offline mobile (cible, non implantee a date)

- PWA cote nouveau front.
- Cache des ecrans stock + operations critiques.
- File d'attente locale pour actions hors-ligne (IndexedDB).
- Rejeu idempotent a la reconnexion.
- Indicateur visuel `offline / sync pending`.

## 7) Thèmes et parité Benev/Classique

Approche recommandée:

- Créer des tokens `legacy-classique` et `legacy-benev`.
- Reproduire structure, typographie, densité, états et libellés.
- Ajouter tests de non-régression visuelle (capture/screenshot diff).

Etat reel:

- switch global legacy/next en place via `/ui/mode/` et `/ui/mode/<mode>/`.
- parite visuelle stricte non finalisee (ecrans Next encore hybrides).

## 8) Organisation code frontend (etat reel + cible)

Etat reel:

```
frontend-next/
  app/
    scan/
    portal/
    components/
    lib/api/
```

Cible (post-parite):

- extraire des modules metier (`scan`, `portal`, `shipment`, `stock`, `documents`),
- introduire bibliotheque de composants partagee,
- ajouter `lib/offline` et `lib/feature-flags` dedies.

## 9) CI/CD (sans Node runtime en prod)

- Build Next statique en CI.
- Publication des assets dans le dossier static servi par Django.
- Déploiement PythonAnywhere inchangé (WSGI Django).
- Smoke tests post-déploiement:
  - login,
  - dashboard,
  - stock view/update,
  - création expédition complète,
  - suivi + clôture.
