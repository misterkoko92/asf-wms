# Scan Preparateur Profile Design

## Contexte

Le scan legacy Django expose aujourd'hui un acces staff large:
- la racine `/scan/` ouvre le dashboard;
- la page `Preparer des colis` reutilise le flux legacy `scan_pack`;
- le meme utilisateur staff peut naviguer vers le stock, les expeditions, la reception, l'admin scan et les autres vues internes.

Le besoin est d'ajouter un profil operationnel tres restreint, nomme `Preparateur`, sans toucher au scope Next/React en pause.

## Objectif

Un utilisateur `Preparateur` doit pouvoir:
- se connecter avec le mecanisme staff existant;
- arriver directement sur `Preparer des colis`;
- ajouter des produits par liste, QR code ou code-barres comme aujourd'hui;
- mettre un ou plusieurs produits dans un ou plusieurs colis;
- valider la preparation et obtenir immediatement des colis `Disponibles`;
- ranger automatiquement ces colis dans la bonne zone `MM` ou `CN`;
- voir une popup de succes claire avec les numeros de colis a ecrire.

Il ne doit pas pouvoir acceder aux autres ecrans scan.

## Approche retenue

Approche retenue:
- conserver le login staff Django existant;
- materialiser le profil par un groupe Django `Preparateur`;
- ajouter des gardes backend explicites sur les vues scan au lieu de compter sur le menu;
- reutiliser la page et le handler legacy `scan_pack` pour eviter de dupliquer le scan produit, le packing multi-colis et les tests existants;
- ajouter une logique metier specifique au mode preparateur pour classer les lignes par `MM` ou `CN`, appliquer un override manuel si necessaire, puis affecter automatiquement l'emplacement final.

Approches ecartees:
- simple masquage UI: insuffisant pour une restriction forte;
- nouvel ecran de preparation completement separe: plus couteux et plus risque alors que le flux actuel couvre deja le scan produit et le packing;
- maintien du dashboard comme page d'entree: contraire a l'objectif operationnel.

## Profil et securite

Le profil sera detecte via un groupe Django `Preparateur`.

Regles:
- un `Preparateur` reste `is_staff=True` pour continuer a utiliser `/admin/login/`;
- `/scan/` devient un routeur:
  - `Preparateur` -> `/scan/pack/`
  - autre staff -> `/scan/dashboard/`
- les vues scan non autorisees retournent `403` pour un `Preparateur`, meme si l'utilisateur connait l'URL;
- les vues necessaires au chargement de la page pack restent disponibles:
  - `scan_root`
  - `scan_pack`
  - `scan_sync`
  - `scan_service_worker`

Le design exclut tout elargissement implicite du profil a d'autres vues scan.

## Navigation et interface

Pour `Preparateur`, la navigation scan est reduite au strict necessaire:
- entree `Preparer des colis`;
- menu `Compte`.

Doivent disparaitre du menu ou de la page:
- dashboard;
- vues stock, receptions, expeditions, commandes, planning;
- gestion, imports, admin, facturation;
- liens d'impression et de telechargement du helper local;
- champ `Reference expedition`;
- choix manuel d'emplacement final.

La page reste `templates/scan/pack.html`, mais avec un rendu conditionnel simplifie pour ce profil.

## Workflow de preparation

Le preparateur utilise le flux de preparation colis existant:
- selection produit dans la liste;
- scan QR code;
- scan code-barres;
- ajout de plusieurs lignes;
- creation de plusieurs colis si le packing l'impose.

La difference metier est appliquee a la validation:
1. les lignes sont classees par type `MM` ou `CN`;
2. un meme colis ne peut jamais melanger `MM` et `CN`;
3. chaque groupe est ensuite envoye dans le packing existant;
4. chaque colis cree est finalise directement en statut `PACKED`, donc affiche `Disponible`.

Le profil `Preparateur` ne gere pas les expeditions. Tous les colis crees restent hors expedition.

## Resolution MM/CN

La determination automatique du type s'appuie sur la categorie racine du produit, deja utilisee par le code legacy pour typer les colis.

Regles:
- categorie racine `MM` -> type `MM`;
- categorie racine `CN` -> type `CN`;
- toute autre racine, ou absence de categorie racine `MM/CN`, bloque la validation tant que l'operateur n'a pas choisi manuellement `MM` ou `CN`.

Le choix manuel doit etre fait ligne par ligne, uniquement pour les produits non resolus automatiquement.

Le backend reste autoritaire:
- si un override manuel `MM/CN` est present, il est utilise;
- sinon la categorie racine est utilisee;
- si aucune resolution valide n'est possible, la ligne est en erreur et aucun colis n'est cree pour la soumission.

## Emplacements automatiques

Les colis finalises sont ranges automatiquement dans:
- `Colis Prets MM`
- `Colis Prets CN`

Comme `Location` n'a pas de champ `name`, l'implementation doit ajouter un helper de resolution qui traduit ces deux labels operationnels vers des objets `Location` existants.

Le helper doit:
- chercher une correspondance stable dans la configuration existante, en se basant sur les labels operateur disponibles dans le schema actuel;
- echouer explicitement si l'emplacement cible est introuvable.

Il ne faut jamais creer un colis sans emplacement final si le mode preparateur exige ce routage automatique.

## Popup de succes

Le simple message flash actuel n'est pas suffisant pour le preparateur.

Le flux doit afficher une vraie popup de succes apres validation.

Cas mono-colis:
- `Colis cree avec succes.`
- `Ranger le colis dans la zone XXX`
- `Ecrire le numero YYY`

Cas multi-colis:
- titre unique de succes;
- une ligne ou carte par colis cree;
- chaque bloc affiche au minimum:
  - numero de colis;
  - zone de rangement;
  - type `MM` ou `CN` si utile a la lecture.

L'objectif est qu'un operateur puisse prendre plusieurs colis, ecrire le bon numero sur chacun, puis les ranger dans la bonne zone sans ambiguite.

## Impact technique

Les changements se concentrent sur la pile legacy:
- permissions et routage scan;
- template de navigation scan;
- handler de preparation colis;
- rendu de la page pack;
- JavaScript legacy `scan.js` pour conserver les lignes dynamiques et y ajouter le choix manuel `MM/CN` si necessaire;
- tests backend et vues existants.

Le scope explicitement exclu:
- `frontend-next/`
- `wms/views_next_frontend.py`
- `wms/ui_mode.py`
- tout plan ou test de migration Next/React.

## Tests

Les tests a ajouter ou adapter couvrent quatre axes:

1. Profil et securite
- redirection `/scan/` vers `/scan/pack/` pour `Preparateur`;
- acces autorise a `scan_pack` et `scan_sync`;
- acces refuse aux autres vues scan;
- menu reduit pour `Preparateur`.

2. Logique metier pack
- preparation `MM` seule -> colis `PACKED` + emplacement `Colis Prets MM`;
- preparation `CN` seule -> colis `PACKED` + emplacement `Colis Prets CN`;
- soumission mixte `MM` + `CN` -> colis distincts, jamais melanges;
- produit sans racine `MM/CN` -> erreur tant que l'operateur n'a pas choisi manuellement le type;
- override manuel `MM/CN` -> creation dans le bon groupe.

3. UX de preparation
- page pack simplifiee pour `Preparateur`;
- champs non utiles caches;
- select manuel `MM/CN` present seulement quand il faut corriger une ligne non resolue.

4. Recapitulatif de succes
- popup mono-colis avec zone + numero;
- popup multi-colis avec toutes les paires `zone / numero`.

## Risques et garde-fous

Risques principaux:
- oublier une vue secondaire necessaire au chargement de la page pack;
- router un colis vers un emplacement mal resolu;
- casser le JavaScript de lignes dynamiques en ajoutant le champ manuel `MM/CN`;
- laisser un trou de securite si la restriction n'est faite qu'au niveau template.

Garde-fous:
- whitelist backend explicite;
- helper dedie pour les emplacements automatiques;
- tests unitaires du handler de pack avant implementation;
- tests de vue sur le role `Preparateur`;
- aucun changement hors stack legacy scan.
