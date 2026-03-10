# Planning Flight API Provider Design

## Context
Le module `planning` de `asf-wms` sait deja importer des vols depuis Excel via `wms/planning/flight_sources.py`, puis les persister en `FlightSourceBatch` et `Flight`.

Le mode API existe seulement comme point d'extension:
- `PlanningFlightApiClient.fetch_flights()` leve encore `NotImplementedError`
- `collect_flight_batches(...)` sait deja combiner Excel et API
- `wms/runtime_settings.py` expose seulement `base_url`, `api_key` et `timeout_seconds`

Un ancien worktree `codex/planning-ortools-solver` contient une premiere integration Air France-KLM non mergee. Elle montre qu'un provider concret peut:
- interroger l'endpoint `flightstatus`
- normaliser les vols multi-stop via `route`
- sortir des lignes compatibles avec le contrat planning actuel

Le besoin valide pour cette phase est d'introduire un vrai provider API interchangeable, avec Air France-KLM comme premiere implementation concrete, sans casser:
- l'import Excel existant
- le mode `HYBRID`
- le contrat metier `FlightSourceBatch -> Flight`

## Goal
Ajouter dans `asf-wms` un systeme de providers API de vols interchangeable, en branchant Air France-KLM comme premier provider reel et en gardant un fallback operateur fiable en mode `HYBRID`.

## Non-Goals
- remplacer Excel comme source principale tout de suite
- exposer une UI de configuration avancée pour plusieurs providers
- ajouter un registry dynamique complexe
- modifier le solveur ou les vues planning en dehors de la gestion des erreurs de source vols
- ouvrir le scope Next/React

## Problem Statement
Le module planning sait deja vivre avec des batches de vols normalises, mais il manque encore la couche d'acquisition API concrete. Si on branche Air France-KLM en dur dans `flight_sources.py`, on gagne vite en connectivite mais on se ferme la porte a d'autres APIs de vols ou de referentiel plus tard.

Le bon compromis est donc:
- une abstraction simple et stable pour les providers
- un provider Air France-KLM concret
- une orchestration centrale qui preserve le comportement Excel et `HYBRID`

## Options Considered
### Option 1: Air France-KLM en direct dans `flight_sources.py`
Avantages:
- implementation rapide
- peu de fichiers

Inconvenients:
- couplage fort a un fournisseur unique
- evolution plus couteuse quand une deuxieme API arrive
- fichier `flight_sources.py` rapidement surcharge

### Option 2: sous-module providers dedie
Avantages:
- separation claire entre orchestration et integration externe
- Air France-KLM devient un premier backend concret, pas une hypothese definitive
- facilite l'ajout d'autres providers plus tard

Inconvenients:
- un peu plus de structure a poser maintenant

### Option 3: registre extensible complet
Avantages:
- architecture tres generale

Inconvenients:
- surdimensionne pour cette phase
- complexite inutile tant qu'un seul provider reel existe

## Recommended Approach
Option 2.

Le module garde:
- `wms/planning/flight_sources.py` comme orchestrateur applicatif
- un sous-module `wms/planning/flight_providers/` pour les integrations externes

Cette approche reste simple, testable, et prepare les futures integrations sans forcer une refonte quand une deuxieme API apparaitra.

## Target Architecture
### Orchestrateur
`wms/planning/flight_sources.py` reste responsable de:
- normaliser les lignes de vols
- persister les `FlightSourceBatch`
- combiner les sources Excel et API
- appliquer les regles de fallback `API` vs `HYBRID`

### Contrat provider
`wms/planning/flight_providers/base.py` definira:
- un contrat `PlanningFlightProvider`
- des erreurs de domaine, par exemple `PlanningFlightProviderError`
- une petite fabrique qui resout le provider a partir des settings

Le contrat retournera des lignes normalisees compatibles avec `normalize_flight_record(...)`, pas des objets ORM.

### Premiere implementation concrete
`wms/planning/flight_providers/airfrance_klm.py` portera:
- la construction de l'URL `flightstatus`
- les headers `API-Key`
- le parsing JSON
- la gestion des `404` vides
- l'expansion des vols multi-stop a partir de `route`
- l'extraction d'une heure de depart exploitable depuis le payload

### Configuration
`wms/runtime_settings.py` exposera un bloc plus complet:
- `provider`
- `base_url`
- `api_key`
- `timeout_seconds`
- `origin_iata`
- `operating_airline_code`
- `time_origin_type`

La selection du provider sera faite par un setting explicite, du type:
- `PLANNING_FLIGHT_API_PROVIDER=airfrance_klm`

## Data Flow
1. Le run planning demande ses vols via `collect_flight_batches(...)`.
2. En mode Excel, rien ne change.
3. En mode API ou `HYBRID`, `import_api_flights(...)` resout le provider configure.
4. Le provider retourne des lignes de vols normalisees.
5. `flight_sources.py` passe ces lignes dans `normalize_flight_record(...)`.
6. Les lignes sont persistees dans un `FlightSourceBatch` `source="api"`.
7. Le reste du module planning consomme ces batches comme aujourd'hui.

## Error Handling
### Mode `API`
Si le provider echoue:
- l'import API echoue explicitement
- le run reste bloque
- l'erreur doit etre exploitable par l'operateur ou le support

### Mode `HYBRID`
Si le provider echoue et qu'un batch Excel est deja disponible:
- le systeme continue avec Excel
- l'incident API est trace dans le batch ou les notes associees
- le run ne doit pas etre bloque pour autant

Si le provider repond vide sans erreur:
- il faut distinguer une vraie absence de vols d'une mauvaise configuration
- le message remonte doit rester explicite

## Testing Strategy
La phase doit etre couverte par:
- tests de non-regression Excel
- tests du provider Air France-KLM sur payload simplifie mais realiste
- tests de fabrique provider depuis les settings
- tests de fallback `HYBRID` quand l'API echoue
- tests d'echec explicite en mode `API`

Le point important est de verrouiller le contrat normalise, pas seulement les details HTTP.

## Risks
### Payload API incomplet ou instable
Mitigation:
- garder le parsing dans un provider dedie
- tester l'expansion multi-stop et les champs strictement necessaires au planning

### Couplage trop tot a Air France-KLM
Mitigation:
- imposer une interface provider simple des cette phase
- limiter l'orchestrateur a un contrat generique

### Fallback hybride silencieux
Mitigation:
- tracer explicitement l'incident API dans les notes ou erreurs de batch
- conserver un comportement different entre `API` et `HYBRID`

## Success Criteria
La phase est terminee quand:
- `asf-wms` dispose d'un provider Air France-KLM concret derriere une interface interchangeable
- la config provider est complete dans `wms/runtime_settings.py`
- l'import Excel existant continue de fonctionner sans regression
- le mode `HYBRID` retombe proprement sur Excel en cas d'erreur API
- une doc courte de configuration et de comportement d'erreur est versionnee
