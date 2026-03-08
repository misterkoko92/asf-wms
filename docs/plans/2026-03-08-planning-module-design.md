# Planning Module Design

## Context
`asf_scheduler/new_repo` couvre aujourd'hui la generation du planning, les mises a jour, les statistiques, les exports et la preparation des communications dans une application Streamlit alimentee par plusieurs sources:
- des donnees metier issues de fichiers Excel comme `TABLEAU DE BORD.xlsx`, `PLANNING BENEVOLE.xlsx`, `Vols.xlsx` et `Planning.xlsx`
- un moteur de regles metier autour de `ParamBE`, `ParamDest`, `ParamExpediteur`, `ParamBenev`
- un solveur OR-Tools pour affecter expeditions, benevoles et vols
- des integrations operateur poste local pour Excel, PDF et brouillons Outlook

`asf-wms` porte deja les domaines expedition, portail association et benevoles sur la pile Django legacy. L'objectif valide est d'absorber le metier du planning dans `asf-wms` afin d'avoir un seul outil, sans toucher a la migration Next/React en pause.

Point de convergence confirme pendant le cadrage:
- l'onglet `Equivalence` du module facturation porte deja dans `asf-wms` le referentiel utilise pour calculer les quantites possibles sur un vol, soit l'equivalent pratique de `ParamBE`
- cette logique existe aujourd'hui via `ShipmentUnitEquivalenceRule` et les fonctions de resolution de `wms/billing_calculations.py`

Decisions produit validees pendant le cadrage:
- `asf-wms` devient la source de verite cible
- `Planning.xlsx` reste un artefact transitoire au debut, pas la source de verite durable
- les communications sont preparees dans `asf-wms`, mais l'envoi reste manuel
- les vols fonctionnent en mode hybride API et/ou Excel pendant la transition, puis basculent vers API-first
- le planning doit rester modifiable manuellement apres passage du solveur
- toute republication doit creer une nouvelle version du planning
- le verrouillage de decisions manuelles dans le solveur n'est pas une exigence V1
- `ParamDest` doit devenir un referentiel specifique au planning
- `ParamBenev` vient du domaine `/benevole`
- `ParamExpediteur` vient des contacts associations du domaine `/portal`
- `ParamBE` doit sortir de la facturation comme point d'entree partage reutilisable par plusieurs modules

## Implementation Reality
La branche `codex/planning-foundation` met bien en place le socle planning legacy Django dans `asf-wms`:
- domaine `planning` persistant avec runs, snapshots, versions, affectations, artefacts et brouillons de communication
- import `ParamDest`, consommation des donnees benevoles et portal, et point d'entree partage pour l'equivalence unite ou carton
- vues legacy sous `/planning/` pour creation de run, validation, solve, edition manuelle, publication, duplication, diff, brouillons et export
- mise a jour optionnelle des expeditions a partir d'une version publiee avec creation d'evenement de tracking

Ecarts volontaires constates apres implementation:
- le solveur actuellement livre est `ortools_cp_sat_v1`, avec capacite par vol, contrainte benevole par vol, compatibilite horaire et exclusivite par vol physique, mais pas encore la parite complete avec tout le solveur historique
- la source vols API est branchee via un client injectable et des runtime settings, mais le connecteur concret reste a finaliser selon l'API retenue
- l'export `Planning.xlsx` reste un classeur de transition minimal, pas une reproduction 1:1 du workbook historique
- les communications sont generees et editables dans `asf-wms`, mais l'envoi reste volontairement manuel

## Decision Summary
Decision retenue:
- creer un vrai module metier `planning` dans `asf-wms`
- reintegrer le moteur de regles, le solveur, les sorties et la preparation des communications dans la base Django legacy
- utiliser les domaines `Shipment`, `Destination`, `VolunteerProfile`, `VolunteerAvailability` et `portal` comme sources internes prioritaires
- traiter Excel et l'API vols comme des connecteurs d'entree ou de sortie, pas comme le coeur de l'application

Decision explicite:
- l'UI cible reste sur les vues, formulaires et templates Django legacy
- `Planning.xlsx` reste genere pendant la migration pour ne pas casser l'operationnel
- les messages email et WhatsApp sont rattaches a une version de planning et regenerables a chaque version
- `ParamDest` est planning-owned
- `ParamBenev` est benevole-owned
- `ParamExpediteur` est portal or contacts-owned
- `ParamBE` devient shared-owned, avec un point d'entree transverse hors module facturation

Decisions rejetees:
- embarquer `asf_scheduler` presque tel quel dans `asf-wms`
- garder un service planning separe branche par API en cible

Pourquoi:
- ces approches conservent une logique metier fragmentee et retardent la convergence vers un outil unique
- elles laissent trop de dependances structurelles a Excel et a une application externe
- elles compliquent le versioning, la tracabilite et les evolutions fonctionnelles cote WMS

## Scope
### V1
- creation d'un run de planning pour une semaine donnee
- chargement des expeditions depuis `asf-wms`
- chargement des benevoles, contraintes et disponibilites depuis `asf-wms`
- chargement des vols en mode API, Excel ou hybride
- remplacement des parametres Excel critiques par:
  - un referentiel planning pour `ParamDest`
  - le domaine benevole pour `ParamBenev`
  - le domaine portal ou contacts pour `ParamExpediteur`
  - un referentiel partage d'equivalence pour `ParamBE`
- validation des donnees avant solveur avec blocants et warnings
- execution du solveur et stockage des resultats
- revue du planning dans `asf-wms`
- corrections manuelles avant diffusion
- publication d'une version de planning
- creation d'une nouvelle version a partir d'une version publiee
- regeneration des exports, brouillons de communication et statistiques pour chaque version
- export `Planning.xlsx` compatible en phase transitoire

### V1.5
- mode API vols par defaut avec Excel en secours
- meilleure UI de comparaison entre versions
- import initial ou resynchronisation encadree des parametres historiques Excel
- surfaces de pilotage admin pour les templates et jeux de parametres

### V2
- reduction forte de la dependance a `Planning.xlsx`
- ecrans natifs complets pour statistiques, diffusion et reprises operationnelles
- eventuel rerun du solveur avec contraintes manuelles figees si le besoin est toujours present

### Out Of Scope
- envoi automatique des emails ou messages WhatsApp
- dependances Outlook COM, AppleScript ou automation desktop equivalentes a l'identique
- migration Next/React
- portage 1:1 de l'UI Streamlit

## Target Architecture
Je recommande une architecture metier explicite, decoupee en sous-composants internes:

1. `wms/models_domain/planning.py`
   Porte les objets persistants purement planning, notamment `ParamDest`, les runs, snapshots, versions et affectations.
2. `wms/models_domain/equivalence.py`
   Porte le referentiel partage d'equivalence aujourd'hui loge dans la facturation.
3. `wms/planning/`
   Porte les services metier internes: sources, snapshots, validation, regles, solveur, versioning, exports, communications, statistiques.
4. `wms/views_planning.py` et `wms/planning_urls.py`
   Exposent la surface utilisateur legacy Django sous `/planning/`.
5. `templates/planning/*`
   Portent les ecrans de creation de run, revue, edition, publication, diff et preparation des communications.
6. `wms/forms_planning.py`
   Porte les formulaires de creation de run, edition manuelle, publication et templates de communication.

L'architecture cible ne reimporte pas l'application Streamlit. Elle reimporte les briques metier, puis les rebranche sur les conventions `asf-wms`.

Structure de services recommandee:
- `wms/unit_equivalence.py`
- `wms/planning/sources.py`
- `wms/planning/flight_sources.py`
- `wms/planning/snapshots.py`
- `wms/planning/validation.py`
- `wms/planning/rules.py`
- `wms/planning/solver.py`
- `wms/planning/versioning.py`
- `wms/planning/communications.py`
- `wms/planning/exports.py`
- `wms/planning/stats.py`
- `wms/planning/shipment_updates.py`

Le module planning doit reutiliser un point d'entree transverse pour le calcul d'equivalence unite ou carton, idealement extrait vers `wms/models_domain/equivalence.py` et `wms/unit_equivalence.py`, puis consomme par facturation et planning.

## Domain Model
Le domaine cible doit separer trois choses:
- les donnees de reference maitres dans `asf-wms`
- les parametres planning administres
- les snapshots et versions qui rendent chaque planning reproductible

### Parametres et referentiel planning
#### `PlanningParameterSet`
Jeu de parametres versionne, avec statut `draft` ou `active`, date d'effet, notes, auteur et marqueur "current".

#### Equivalence unite ou carton
Le contenu metier equivalent a `ParamBE` ne doit pas etre remodele dans `planning` ni rester billing-owned.

Source canonique recommandee:
- `ShipmentUnitEquivalenceRule` deplace vers un domaine partage
- logique de resolution exposee via un point d'entree transverse, par exemple `wms/unit_equivalence.py`

Implication:
- le planning consomme ce referentiel pour calculer la quantite equivalente mobilisee sur un vol
- la facturation consomme le meme point d'entree
- chaque run gele soit les regles actives appliquees, soit les quantites equivalentes resolues par expedition afin de garantir la reproductibilite
- si des champs supplementaires deviennent necessaires, ils doivent enrichir ce referentiel partage plutot que creer un deuxieme systeme d'equivalence

#### `PlanningDestinationRule`
Remplace le contenu metier de `ParamDest`: frequence de desserte, capacite, nombre de colis max, contraintes de jour, priorites locales, correspondants et drapeaux logistiques utiles.

#### Entrees expediteur
Le contenu equivalent a `ParamExpediteur` doit venir des contacts associations et du referentiel portal ou contacts, pas d'un nouveau referentiel planning duplique.

Source canonique recommandee:
- `AssociationProfile`
- contacts organisation ou contacts portail pertinents
- eventuels champs metier deja portes dans le domaine portal ou contacts

Le planning consomme ces donnees et les fige dans les snapshots. Si un champ manque pour l'orchestration planning, il doit de preference etre ajoute au domaine portal ou contacts avant de creer un overlay planning.

#### Entrees benevole
Le contenu equivalent a `ParamBenev` doit venir du domaine benevole.

Source canonique recommandee:
- `VolunteerProfile`
- `VolunteerConstraint`
- `VolunteerAvailability`
- `VolunteerUnavailability`

Le champ critique `max_colis_vol` doit etre porte nativement par `asf-wms` dans le domaine benevole.

Ces regles restent des donnees maitres modifiables dans `asf-wms`, puis gelees dans chaque run.

Seul `ParamDest` reste planning-owned dans `PlanningParameterSet`. Les autres referentiels sont consommes depuis leurs domaines maitres puis figes dans le run.

### Alimentation vols
#### `FlightSourceBatch`
Batch importe depuis l'API ou un fichier Excel, avec source, periode, horodatage, checksum ou metadonnees du fichier, et statut d'import.

#### `Flight`
Vol planifiable rattache a un batch, avec numero de vol, date, heures, route, destination, capacite et marqueurs de qualite de donnees.

Le couple `FlightSourceBatch` + `Flight` permet de conserver un historique d'import et d'ancrer un run sur un lot de vols stable.

### Execution et snapshots
#### `PlanningRun`
Execution technique du moteur pour une periode donnee.

Champs recommandes:
- `week_start`
- `week_end`
- `flight_mode` (`api`, `excel`, `hybrid`)
- `flight_batch`
- `parameter_set`
- `status` (`draft`, `validating`, `validation_failed`, `ready`, `solving`, `solved`, `failed`)
- `created_by`
- `validation_summary`
- `solver_payload`
- `solver_result`
- `log_excerpt`
- `created_at`, `updated_at`

#### `PlanningIssue`
Issue de validation rattachee a un run, avec severite (`error`, `warning`), code, message, objet source et contexte exploitable en UI.

#### `PlanningShipmentSnapshot`
Snapshot des expeditions eligibles pour un run. Il fige les champs utilises par le solveur a la date du calcul: destination, expediteur, priorite, statut, quantites, contraintes, drapeaux, et quantite equivalente issue du referentiel partage d'equivalence.

#### `PlanningVolunteerSnapshot`
Snapshot des benevoles eligibles, de leurs disponibilites, contraintes, localisation utile, capacites et autres champs utilises par le solveur.

#### `PlanningFlightSnapshot`
Snapshot des vols retenus pour le run, afin de ne pas dependre d'une mutation ulterieure du lot de vols.

Le principe est de pouvoir reconstituer exactement les entrees d'un run, meme si les objets maitres ont change ensuite.

### Versions et affectations
#### `PlanningVersion`
Version operationnelle du planning issue d'un `PlanningRun`.

Champs recommandes:
- `run`
- `number`
- `status` (`draft`, `published`, `superseded`, `cancelled`)
- `based_on`
- `change_reason`
- `created_by`
- `published_at`
- `created_at`, `updated_at`

Une version publiee est immuable. Toute nouvelle diffusion cree une nouvelle version.

#### `PlanningAssignment`
Ligne d'affectation pour une version donnee.

Champs recommandes:
- `version`
- `shipment_snapshot`
- `volunteer_snapshot`
- `flight_snapshot`
- `assigned_carton_count`
- `assigned_weight_kg`
- `status`
- `source` (`solver`, `manual`, `copied`)
- `notes`
- `sequence`

Ce modele reste volontairement fin pour permettre:
- l'agregation visuelle par vol et par benevole
- les ajustements manuels ponctuels
- le diff entre versions
- la tracabilite de l'origine d'une affectation

#### `PlanningArtifact`
Artefact genere pour une version: export Excel, CSV, PDF leger si utile, brouillon global, etc.

## Data Flow
Flux cible:
1. un operateur cree un `PlanningRun`
2. `asf-wms` charge les expeditions eligibles depuis l'ORM
3. `asf-wms` charge les benevoles, contraintes et disponibilites depuis le domaine benevole
4. `asf-wms` charge les references expediteur depuis le domaine portal ou contacts
5. `asf-wms` charge les vols depuis un `FlightSourceBatch`
6. `asf-wms` compile `PlanningDestinationRule` et charge le referentiel partage d'equivalence
7. le systeme applique les regles d'equivalence partagees puis cree les snapshots du run
8. la validation produit des `PlanningIssue`
9. si des erreurs bloquantes existent, le run s'arrete avant solveur
10. sinon, `wms/planning/rules.py` transforme les snapshots en payload solveur
11. `wms/planning/solver.py` execute le solveur et cree une `PlanningVersion` brouillon
12. l'operateur relit puis ajuste manuellement les `PlanningAssignment`
13. la publication fige la version et genere ses artefacts
14. si un changement arrive plus tard, l'operateur cree une nouvelle version a partir de la precedente
15. `asf-wms` regenere exports, brouillons de communication et statistiques pour la nouvelle version

## Manual Adjustments And Versioning
Le besoin metier valide impose une distinction forte entre calcul et diffusion.

Decision:
- `PlanningRun` porte le calcul et ses entrees
- `PlanningVersion` porte la diffusion operationnelle

Consequences fonctionnelles:
- la premiere sortie solveur cree une version `v1` en brouillon
- l'operateur peut corriger les affectations dans `asf-wms`
- la publication de `v1` la fige
- un changement ulterieur cree `v2` a partir de `v1`, jamais une edition destructive de `v1`
- les differences entre versions doivent etre visibles en UI
- les artefacts et messages sont toujours rattaches a une version precise

Ce design couvre le besoin critique de correction manuelle et de republication sans introduire, en V1, un rerun solveur avec verrous manuels.

## Communication Model
Les communications doivent etre regenerables a chaque version et modifiables avant diffusion.

### `CommunicationTemplate`
Modele de message par canal et usage:
- email benevole
- email correspondant
- message WhatsApp benevole
- message recap equipe

Le template contient le sujet si necessaire, le corps, le canal, le scope, les variables autorisees et un statut actif.

### `CommunicationDraft`
Instance concretisee pour une `PlanningVersion` et un destinataire.

Champs recommandes:
- `version`
- `channel`
- `template`
- `recipient_label`
- `recipient_contact`
- `subject`
- `body`
- `status` (`generated`, `edited`, `exported`, `sent_manually`)
- `edited_by`
- `edited_at`

Principes:
- une version publiee conserve ses brouillons
- une nouvelle version genere une nouvelle serie de brouillons
- l'operateur peut retoucher chaque brouillon avant diffusion
- l'application prepare les messages mais ne les envoie pas automatiquement

## Excel Transition Strategy
Les fichiers Excel ne doivent plus etre les sources de verite du metier planning.

Remplacement cible:
- `TABLEAU DE BORD.xlsx` est remplace par les expeditions, destinations, expediteurs et parametres administres dans `asf-wms`
- `PLANNING BENEVOLE.xlsx` est remplace par `VolunteerProfile`, `VolunteerConstraint`, `VolunteerAvailability` et `VolunteerUnavailability`
- `ParamExpediteur` est remplace par les contacts associations du domaine `/portal` et du referentiel contacts
- `ParamBE` est remplace par un referentiel partage d'equivalence transverse a plusieurs modules
- `Vols.xlsx` reste acceptable comme source transitoire de `FlightSourceBatch`
- `Planning.xlsx` reste un export de sortie en phase transitoire

Je recommande un import de bootstrap pour les feuilles de parametres historiques, afin d'eviter une ressaisie manuelle initiale.

## Validation And Error Handling
Le systeme doit rendre explicites les erreurs aujourd'hui masquees dans Excel ou dans les corrections manuelles.

Regles recommandees:
- erreur bloquante si une expedition eligible n'a pas les parametres requis
- erreur bloquante si l'equivalence unite ou carton necessaire au calcul de capacite vol ne peut pas etre resolue
- erreur bloquante si un benevole ne porte pas les champs critiques attendus par le solveur
- erreur bloquante si aucun vol exploitable n'est disponible pour la semaine
- warning si une donnee est incomplete mais peut etre ignoree sans casser le calcul
- toutes les erreurs et warnings sont persistants dans `PlanningIssue`
- les services planning restent idempotents quand ils regenerent une version, des brouillons ou des exports

Les integrations desktop historiques ne sont pas reproduites a l'identique. La cible prepare des artefacts web exploitables dans `asf-wms`.

## Testing Strategy
Le module planning doit etre couvert a trois niveaux:

1. tests de domaine
   Verifient les modeles, contraintes, snapshots, versioning et immutabilite des versions publiees.
2. tests de services
   Verifient compilation des parametres, validation, transformation en payload solveur, generation des brouillons et des exports.
3. tests de vues legacy Django
   Verifient creation de run, consultation, edition manuelle, publication, duplication de version, diff et ecrans de communication.

Je recommande aussi de porter dans `asf-wms` une partie des tests de contrat deja presents dans `asf_scheduler/new_repo/tests/test_data_sources.py` et `asf_scheduler/new_repo/tests/test_solver_contracts.py`.

## Migration Strategy
Je recommande une migration en quatre phases:

### Phase 1
- creer le domaine `planning`
- creer le referentiel partage d'equivalence hors facturation
- modeliser `ParamDest`
- brancher `ParamBenev` sur le domaine benevole
- brancher `ParamExpediteur` sur le domaine portal ou contacts
- brancher les sources internes WMS et le chargement de vols
- reintegrer validation et solveur
- produire un `Planning.xlsx` compatible

### Phase 2
- introduire la revue web, les corrections manuelles et le versioning
- rattacher statistiques et mises a jour expedition a une version
- generer les brouillons de communication dans `asf-wms`

### Phase 3
- rendre le workflow planning majoritairement web
- limiter Excel a l'import vols et a l'export de secours

### Phase 4
- basculer en API vols par defaut
- deprecier les dependances Excel residuelles qui ne sont plus utiles

## Open Points Already Answered
Les arbitrages valides pour la suite sont:
- `asf-wms` est la cible maitre
- `Planning.xlsx` reste transitoire
- l'envoi des communications reste manuel
- les vols sont hybrides en transition puis API-first
- les corrections manuelles sont necessaires
- le versioning par republication est obligatoire
- le rerun solveur avec verrous manuels n'est pas un prerequis V1
