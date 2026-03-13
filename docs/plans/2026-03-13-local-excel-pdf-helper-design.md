# Local Excel PDF Helper Design

## Contexte

`asf-wms` genere deja plusieurs documents `.xlsx` qui doivent etre convertis en PDF avec une equivalence de rendu aussi proche que possible d'Excel.

Contraintes confirmees:
- pas de fallback LibreOffice
- abandon progressif de `asf-planning`, mais reutilisation autorisee de sa logique Excel desktop qui fonctionne deja
- scope strictement sur le stack Django legacy
- l'approche Microsoft Graph ne convient pas operationnellement

Etat actuel du depot:
- `tools/planning_comm_helper/planning_pdf.py` convertit deja un workbook en PDF via Microsoft Excel desktop sur macOS/Windows
- `tools/planning_comm_helper/server.py` expose deja un helper local sur `127.0.0.1:38555`
- `wms/print_pack_graph.py` et `wms/print_pack_engine.py` portent aujourd'hui la conversion PDF cote serveur via Graph pour les print packs
- `wms/static/wms/planning_communications_helper.js` montre deja le pattern navigateur -> helper local -> action locale

Le point structurant n'est donc pas "comment convertir un Excel en PDF", mais "ou faire tourner ce rendu Excel de reference".

## Objectif

Standardiser les flux `xlsx -> pdf` interactifs de `asf-wms` sur un helper local base sur Microsoft Excel desktop, afin de:
- garder un rendu aligne sur Excel
- supprimer la dependance Graph pour ces flux
- eviter toute dependance Excel sur le serveur Django
- reutiliser le code et l'UX helper deja en place pour le planning

## Decisions validees

- le moteur de rendu de reference est Microsoft Excel desktop
- `asf-wms` reste la source de verite metier et continue de generer les `.xlsx`
- le helper local devient generique et n'est plus limite au seul planning
- aucune conversion LibreOffice n'est introduite, meme en secours
- pour les documents qui exigent la parite Excel, l'absence du helper ou d'Excel doit produire une erreur explicite, pas un rendu degrade

## Approches considerees

### Option 1: helper Django

Django genere les `.xlsx`, pilote Excel, convertit en PDF, puis retourne le PDF a l'utilisateur.

Avantages:
- routes de consultation inchangees
- archivage serveur plus simple a conserver

Inconvenients:
- suppose Excel installe sur le serveur
- incompatible avec une cible Linux/PythonAnywhere
- bloque des requetes web sur une automatisation desktop fragile
- couple la disponibilite du rendu PDF a l'infrastructure serveur

### Option 2: helper local minimal

Django genere les `.xlsx`, le navigateur telecharge un workbook et l'envoie au helper local, qui le convertit en PDF.

Avantages:
- tres proche de l'existant `asf-planning`
- faible cout technique initial

Inconvenients:
- gere mal les packs multi-documents
- laisse la fusion PDF a un autre composant
- oblige vite a une deuxieme iteration

### Option 3: helper local complet

Django genere les `.xlsx`, le navigateur orchestre l'appel au helper local, et le helper convertit un ou plusieurs workbooks, fusionne les PDF si besoin, puis ouvre le resultat localement.

Avantages:
- reutilise la logique Excel desktop deja prouvee
- elimine Graph des flux interactifs
- couvre les documents simples et les packs multi-documents
- reste compatible avec le pattern deja employe pour Outlook/WhatsApp

Inconvenients:
- les boutons concernes deviennent des actions JS, pas de simples liens PDF serveur
- l'archivage serveur des PDF sort du chemin nominal V1

### Recommendation

Retenir l'option 3: helper local complet.

## Pourquoi le helper local est la bonne cible

Le depot montre deja une cible de deploiement PythonAnywhere/Linux. Dans ce contexte, faire tourner Microsoft Excel au niveau Django est un mauvais couplage technique et operationnel.

Le helper local, lui, place la dependance Excel la ou elle a du sens:
- sur un poste operateur
- dans un processus dedie
- sur un flux explicitement interactif

Il est aussi coherent avec le modele deja adopte pour les brouillons Outlook:
- Django prepare le contenu
- le navigateur transmet au helper local
- le helper realise l'action locale necessaire

## Design cible

### 1. Coeur `Excel -> PDF` generique

La logique actuelle de `tools/planning_comm_helper/planning_pdf.py` devient le coeur generique de conversion Excel desktop.

Attendus:
- conserver Windows COM + AppleScript macOS
- garder l'absence de fallback LibreOffice
- ajouter un mode "strict Excel" avant export:
  - ouverture du workbook via Excel
  - recalcul complet
  - attente du resultat si necessaire
  - export PDF
- retourner des erreurs explicites:
  - Excel absent
  - workbook invalide
  - export PDF non produit

Compatibilite:
- conserver un alias ou wrapper compatible pour les usages planning existants
- renommer la semantique "planning_pdf" vers une semantique generique "excel_pdf"

### 2. Helper HTTP local generique

Le helper local existant reste le point d'entree unique sur `127.0.0.1:38555`.

Nouvelle route recommandee:
- `POST /v1/pdf/render`

Contrat cible:
- entree:
  - `documents`: liste de workbooks `.xlsx`
  - `output_filename`
  - `merge`: booleen
  - `open_after_render`: booleen
  - `job_label`: optionnel
- sortie JSON:
  - `ok`
  - `output_filename`
  - `opened`
  - `warning_messages`

Comportement:
- convertir chaque workbook en PDF via Excel desktop
- fusionner les PDF quand `merge=1`
- ouvrir le PDF final localement quand `open_after_render=1`
- ne jamais faire de fallback LibreOffice

Decision V1:
- le helper ouvre le PDF localement et renvoie un accus de succes
- le helper ne renvoie pas le PDF brut au navigateur en V1

Ce choix garde le helper simple, evite les charges base64 importantes, et reste coherent avec le modele d'actions locales deja utilise pour Outlook.

### 3. Django comme orchestrateur metier

`asf-wms` garde la responsabilite de:
- produire les `.xlsx`
- decrire les documents a rendre
- verifier les permissions
- exposer les URLs de telechargement necessaires au navigateur

Pour les print packs:
- reutiliser `render_pack_xlsx_documents(...)` comme source des workbooks
- ne plus appeler Graph dans le chemin interactif nominal

Pour le planning:
- conserver les brouillons Outlook
- faire evoluer les types de pieces jointes vers une semantique generique `excel_workbook` ou equivalent

### 4. Pont navigateur -> helper local

Le navigateur devient le pont entre Django et le helper local.

Pattern recommande:
1. l'utilisateur clique un bouton WMS
2. le navigateur recupere un payload JSON depuis Django
3. le navigateur telecharge les workbooks associes en session authentifiee
4. le navigateur les transmet au helper local
5. le helper convertit, fusionne si besoin, puis ouvre le PDF
6. le navigateur affiche un retour de succes ou une erreur d'installation

Cette architecture reutilise directement les mecanismes deja presents dans `wms/static/wms/planning_communications_helper.js`:
- requetes authentifiees vers Django
- telechargement des pieces jointes
- POST local vers `127.0.0.1:38555`
- gestion de panneau d'installation / reessai

### 5. Flux concernes

Flux a migrer vers le helper local:
- planning workbook joint aux mails Outlook
- print packs issus des templates Excel:
  - `shipment_note`
  - `packing_list_shipment`
  - `donation_certificate`
  - `destination labels`
  - `picking`
  - variantes carton associees

Flux hors scope immediat:
- documents encore rendus en HTML/PDF legacy hors print packs Excel
- archivage OneDrive des artefacts PDF existants
- export PDF cote serveur pour les liens publics ou usages non interactifs

## Archivage et artefacts

Le couple `GeneratedPrintArtifact` + synchro OneDrive a ete pense pour le pipeline Graph cote serveur.

Pour garder une migration simple et robuste, V1 du helper local:
- ne reconstruit pas un pipeline complet d'upload retour navigateur -> Django
- ne tente pas de persister automatiquement chaque PDF localement sur le serveur
- se concentre sur le rendu et l'ouverture locale du PDF

Decision explicite:
- l'archivage serveur automatique des PDF sortis du helper est differe a une phase separee
- les artefacts Graph historiques restent lisibles, mais ne pilotent plus le rendu interactif cible

## UX cible

### Planning communications

Le comportement reste proche de l'existant:
- clic sur "Ouvrir le brouillon"
- si le helper est disponible, Outlook s'ouvre avec les pieces jointes
- si une piece jointe Excel doit devenir PDF, la conversion se fait dans le helper avant attachement

### Impression scan/admin

Les boutons des documents Excel-parity cessent d'etre de simples liens passifs.

Ils deviennent des actions helper:
- si le helper est disponible: conversion locale et ouverture du PDF
- si le helper est absent: message explicite + aide a l'installation + bouton "Reessayer"

Les documents legacy hors scope gardent leur comportement actuel.

## Gestion d'erreurs

Erreurs a gerer explicitement:
- helper local indisponible
- Excel absent ou non pilotable
- workbook non telechargeable
- export PDF partiel ou invalide
- echec de fusion PDF

Regles:
- pas de fallback LibreOffice
- pas de fallback Graph
- pas de bascule silencieuse vers un rendu HTML pour les documents exigeant la parite Excel
- erreurs utilisateur courtes, logs techniques detailles cote helper

## Ajustements indispensables par rapport a la version `asf-planning`

Deux ajustements sont requis pour rendre la solution reutilisable proprement dans `asf-wms`:

1. Generaliser le helper
- sortir d'une semantique purement "planning"
- accepter plusieurs familles de documents Excel
- exposer une route locale generique de rendu PDF

2. Rendre le rendu "strict" pour les cas limites
- recalcul/rafraichissement Excel avant export
- meilleur cadrage des erreurs
- gestion native des lots multi-workbooks avec fusion PDF

## Rollout recommande

1. Generaliser le coeur Excel desktop et ajouter la route helper PDF
2. Migrer les pieces jointes planning vers la semantique generique
3. Migrer les boutons scan/admin des print packs Excel vers le helper local
4. Desactiver Graph sur les flux interactifs concernes
5. Evaluer ensuite, si besoin, une phase separee pour reintroduire de l'archivage serveur

## Non-goals V1

- conversion cote serveur via Excel
- fallback LibreOffice
- retour binaire PDF helper -> navigateur
- reimplementation immediate de l'archivage OneDrive
- travaux sur `frontend-next/`
