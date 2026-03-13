# Local Helper Versioning Design

## Contexte

Le helper local `tools/planning_comm_helper` est deja utilise par les ecrans legacy Django pour:
- convertir des workbooks Excel en PDF
- fusionner plusieurs PDF
- ouvrir localement le resultat

Le flux actuel sait:
- detecter un helper absent
- proposer un installeur adapte a la plateforme
- reessayer apres installation

En revanche, il ne sait pas encore:
- exposer une vraie version helper
- declarer ses capabilities
- distinguer un helper acceptable d'un helper obsolete
- guider une mise a jour avant generation PDF

Contraintes confirmees:
- scope strictement sur la stack Django legacy
- support cible: plusieurs postes operateurs macOS et Windows
- l'installation reste locale au poste et au profil utilisateur
- pas d'auto-update silencieux force

## Objectif

Ajouter un protocole de versioning et de compatibilite du helper local afin que, au clic sur un bouton PDF:
- l'application sache si le helper local est absent, obsolete, compatible ou seulement en retard
- la generation soit bloquee seulement si la version minimale requise n'est pas atteinte ou si une capability obligatoire manque
- une mise a jour guidee soit proposee avant reessai de la generation

## Decision produit

Le comportement retenu est "mise a jour recommandee":

- helper absent: blocage
- helper plus ancien que `minimum_helper_version`: blocage
- helper compatible mais plus ancien que `latest_helper_version`: generation autorisee avec recommandation de mise a jour
- helper compatible et a jour: generation directe

La mise a jour n'est pas silencieuse:
- l'utilisateur peut lancer la mise a jour depuis l'ecran
- l'installeur adapte a la plateforme est telecharge
- l'utilisateur l'execute sur son poste
- le navigateur reprobe ensuite le helper et relance automatiquement la generation si la compatibilite est restauree

## Versioning retenu

Le helper porte une version logique unique commune a macOS et Windows:
- exemple: `2.4.0`

Il ne faut pas maintenir deux streams de version separes par OS tant que:
- le protocole HTTP helper est commun
- les capabilities exposees sont equivalentes

Le helper renvoie aussi:
- `platform`: pour diagnostic et choix d'installeur
- `capabilities`: pour declarer finement ce qu'il sait faire

Exemple de payload helper:

```json
{
  "ok": true,
  "helper_version": "2.4.0",
  "platform": "macOS",
  "capabilities": ["pdf_render", "pdf_merge", "excel_render"]
}
```

## Contrat helper

### Endpoint de sante

Le helper expose `POST /health`.

Reponse cible:

```json
{
  "ok": true,
  "helper_version": "2.4.0",
  "platform": "macOS",
  "capabilities": ["pdf_render", "pdf_merge", "excel_render"]
}
```

Pourquoi conserver `POST`:
- le helper supporte deja `POST` + `OPTIONS`
- cela limite le delta sur le serveur HTTP local existant
- cela reste coherent avec les autres routes helper

### Capabilities

Capabilities initiales recommandees:
- `pdf_render`
- `excel_render`
- `pdf_merge`

Une capability doit decrire une aptitude observable par le navigateur, pas une implementation interne.

## Contrat Django

Chaque page legacy capable de declencher une action helper doit disposer des metadonnees suivantes:

```json
{
  "minimum_helper_version": "2.4.0",
  "latest_helper_version": "2.5.1"
}
```

Les capabilities requises doivent etre declarees a l'action, pas globalement a la page.

Le payload helper job JSON renvoye par Django devient:

```json
{
  "documents": [...],
  "output_filename": "print-pack-A-001.pdf",
  "merge": true,
  "open_after_render": true,
  "required_capabilities": ["pdf_render", "excel_render", "pdf_merge"]
}
```

Pourquoi au niveau du job:
- certaines actions exigent `pdf_merge`, d'autres non
- cela evite de dupliquer une logique fragile dans les templates
- le backend legacy reste la source de verite metier

## Evaluation de compatibilite

Le navigateur calcule un statut local a partir de:
- reponse `POST /health`
- `minimum_helper_version`
- `latest_helper_version`
- `required_capabilities`

Statuts cibles:
- `missing`
- `outdated_blocking`
- `outdated_recommended`
- `unsupported_blocking`
- `ready`

Regles:
- helper absent ou reponse invalide -> `missing`
- `helper_version < minimum_helper_version` -> `outdated_blocking`
- capability requise absente -> `unsupported_blocking`
- `minimum_helper_version <= helper_version < latest_helper_version` -> `outdated_recommended`
- sinon -> `ready`

## UX cible

### Cas absent ou obsolete bloquant

Au clic:
- le bouton ne lance pas la generation PDF
- le panneau helper apparait
- le message explique que la version locale doit etre installee ou mise a jour
- l'utilisateur peut:
  - telecharger l'installeur
  - copier la commande
  - cliquer sur `Reessayer`

Le bouton principal recommande:
- `Mettre a jour le helper puis generer le PDF`

### Cas obsolete non bloquant

Au clic:
- la generation PDF continue normalement
- un message non bloquant propose de mettre a jour le helper apres l'action

### Cas capability manquante

Au clic:
- la generation est bloquee
- le message doit mentionner que cette action requiert une version helper plus recente prenant en charge la fonctionnalite demandee

## Flux cible

1. clic sur un bouton PDF helper-aware
2. JS appelle `POST /health` sur le helper local
3. JS recupere le helper job JSON depuis Django
4. JS evalue la compatibilite
5. si statut bloquant:
   - affichage du panneau d'installation/mise a jour
   - memorisation de l'action en attente
6. si statut non bloquant:
   - telechargement des workbooks
   - appel `POST /v1/pdf/render`
7. apres mise a jour manuelle:
   - clic sur `Reessayer`
   - nouveau `POST /health`
   - si statut OK, relance automatique de l'action memorisee

## Distribution et limites

Cette iteration ne transforme pas encore le helper en artefact desktop autonome.

Le modele reste:
- installeur genere par Django
- script local qui repointe le launcher stable vers le repo et la `.venv` du poste

Cela suffit pour:
- plusieurs postes operateurs
- macOS et Windows
- gestion centralisee d'une version minimale et recommandee

Limite explicite:
- l'installation reste par utilisateur OS
- si une meme machine a plusieurs comptes utilisateurs, chaque compte garde son helper propre

## Non-goals

- auto-update silencieux sans confirmation utilisateur
- packaging desktop autonome versionne par OS
- gestion MDM / parc machine
- support de la stack `frontend-next/`
- mise a jour forcee a chaque release si la version minimale est deja satisfaite

## Rollout recommande

1. ajouter une vraie version helper + capabilities exposees par `POST /health`
2. exposer `minimum_helper_version` et `latest_helper_version` cote Django
3. enrichir les helper jobs avec `required_capabilities`
4. mettre a jour le bridge JS pour evaluer les statuts et guider `update + retry`
5. couvrir le flux par tests helper, view tests Django et tests UI legacy
