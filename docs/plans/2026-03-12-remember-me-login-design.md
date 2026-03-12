# Remember Me Login Design

## Contexte

Sur l'instance PythonAnywhere `messmed.pythonanywhere.com`, les formulaires de connexion custom:
- `/`
- `/portal/login/`
- `/benevole/login/`

ne proposent pas de mode explicite `Rester connecté`.

L'utilisateur confirme que le comportement actuel de `/admin/` lui convient et ne doit pas etre modifie.

Contrainte de scope:
- implementation strictement sur le stack Django legacy
- aucun travail sur `frontend-next/` ni sur la migration Next/React en pause

## Objectif

Ajouter une case a cocher `Rester connecté` sur les trois formulaires de connexion custom afin de:
- conserver une session persistante pendant 14 jours lorsque la case est cochee
- fermer la session a la fermeture du navigateur lorsque la case n'est pas cochee
- ne rien changer au comportement direct de `/admin/`

## Approches considerees

### Option 1: gestion centralisee via signal Django

Ajouter la checkbox dans les formulaires custom et gerer l'expiration de session au moment du login via le signal `user_logged_in`.

Avantages:
- laisse `/admin/` intact
- couvre aussi la home qui poste deja vers `/admin/login/`
- evite de dupliquer la logique d'expiration dans chaque vue

Inconvenients:
- demande un petit protocole commun entre formulaires (`remember_me_supported`)

### Option 2: logique dans chaque vue custom

Ajouter `request.session.set_expiry(...)` dans chaque vue de login.

Avantages:
- tres explicite dans les vues

Inconvenients:
- ne couvre pas la home qui passe par `/admin/login/`
- oblige a traiter le cas staff a part

### Recommendation

Retenir l'option 1.

## Design cible

### UI

Chaque formulaire custom affiche:
- une checkbox `Rester connecté`
- un champ cache `remember_me_supported=1`

Le champ cache permet de distinguer:
- les formulaires qui supportent cette option
- le login admin direct `/admin/`, qui doit rester inchange

### Session

Au login:
- si `remember_me_supported` est absent: ne rien changer
- si `remember_me_supported` est present et `remember_me` est coche: `set_expiry(14 jours)`
- si `remember_me_supported` est present et `remember_me` n'est pas coche: `set_expiry(0)`

La duree de 14 jours reste alignee sur la valeur Django par defaut `SESSION_COOKIE_AGE`.

### Portee fonctionnelle

- `/portal/login/`: case visible et etat preserve en cas d'erreur de formulaire
- `/benevole/login/`: case visible et etat preserve en cas d'erreur de formulaire
- `/`: case visible et transmise au login staff via `/admin/login/`
- `/admin/`: aucun changement visuel ni comportemental

### Tests

Ajouter des tests verifies:
- checkbox presente sur les trois formulaires
- login portail coche => session persistante
- login portail non coche => session navigateur
- login benevole coche/non coche => meme comportement
- login home staff coche/non coche => meme comportement en passant par `/admin/login/`
- login admin direct sans marqueur => comportement inchange
