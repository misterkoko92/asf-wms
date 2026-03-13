# Release Smoke Matrix Design

**Goal:** définir une matrice smoke minimale pour `asf-wms` qui couvre les chaînes nominales critiques sans dupliquer les nombreux tests unitaires, d'intégration, et de vues déjà présents dans le repo.

## Contexte

Le dépôt contient déjà une couverture dense sur le legacy Django:

- tests de domaine, formulaires, vues et handlers sous `wms/tests/`
- workflows API bout en bout sous `api/tests/tests_ui_e2e_workflows.py`
- flows emails bout en bout sous `wms/tests/emailing/tests_email_flows_e2e.py`
- smoke planning nominal sous `wms/tests/planning/tests_smoke_planning_flow.py`

Le problème n'est donc pas un manque global de tests, mais le risque de sur-ajouter des smoke tests sur tous les parcours utilisateur, ce qui créerait une suite lente, fragile, et redondante.

## Décision

Séparer la stratégie smoke en deux couches:

1. **CI**
   - garder un sous-ensemble très petit de smoke déterministes
   - couvrir uniquement les chaînes critiques transverses
   - éviter les variantes UI secondaires, les cas d'erreur détaillés, et les branches métier fines

2. **Post-deploy**
   - exécuter une matrice courte et manuelle
   - vérifier d'abord les routes vitales et un flux scan nominal
   - ajouter des checks conditionnels selon les domaines touchés par la release

## Portée recommandée

### CI

Smoke guards transverses à conserver comme référence:

- `api.tests.tests_ui_e2e_workflows`
- `wms.tests.emailing.tests_email_flows_e2e`
- `wms.tests.planning.tests_smoke_planning_flow`

On n'ajoute un nouveau smoke CI que si une nouvelle chaîne critique traverse plusieurs couches et qu'une régression de câblage ne serait pas captée par les tests existants.

### Post-deploy

Toujours vérifier:

- routes vitales (`/`, `/admin/login/`, `/scan/`, `/scan/shipments-ready/`, `/scan/shipments-tracking/`, `/api/v1/products/`)
- un flux scan nominal authentifié
- la création et la visibilité d'un brouillon d'expédition
- un flux de suivi ou de clôture sur une expédition existante
- la santé des queues email et document scan

Vérifications conditionnelles selon le scope de la release:

- portail: login + un flux nominal commande ou destinataire
- planning: cockpit/version publiée/artifact si le domaine a changé
- billing: prévisualisation/export ou correction/paiement nominal si le domaine a changé

## Non-objectifs

- ne pas ajouter un smoke pour chaque écran ou chaque variante utilisateur
- ne pas répliquer en smoke les assertions métier déjà couvertes par les tests de domaine ou de vues
- ne pas utiliser les smoke post-deploy pour explorer des imports destructifs ou risqués en production

## Critères d'acceptation

- la checklist de release distingue explicitement `always-on smoke` et `conditional smoke`
- le runbook d'operations explique que les smoke ne doivent couvrir que les chaînes nominales critiques
- la documentation cite le petit sous-ensemble de smoke CI servant de garde-fou transverse
