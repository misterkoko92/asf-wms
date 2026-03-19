# Bootstrap-Only UI Cleanup - Design

## Contexte

Le depot conserve aujourd'hui:
- l'UI Django actuelle (`templates/scan/*`, `templates/portal/*`, `templates/benevole/*`, `templates/home.html`),
- un frontend Next/React parallele en veille (`frontend-next/`, `/app/*`, `wms/views_next_frontend.py`, `wms/ui_mode.py`),
- une couche de themes/styles historiques dans `wms/static/scan/scan.css`,
- une couche `Design` d'administration permettant de modifier les variables de rendu.

Le besoin valide est de ne garder qu'une seule UI web, basee sur Django + Bootstrap, sans second frontend ni themes alternatifs. L'ecran `Design` doit rester disponible pour regler directement l'UI.

## Objectif

Converger vers une UI unique avec les proprietes suivantes:
- rendu exclusivement servi par Django,
- socle visuel unique Bootstrap,
- suppression des couches Next/React et `ui_mode`,
- suppression des themes et presets integres concurrents,
- conservation de `scan/admin/design/` comme editeur runtime des variables visuelles du socle Bootstrap/WMS.

## Decisions Validees

- UI conservee: UI Django + Bootstrap.
- Frontend parallelle: suppression complete de Next/React cote produit.
- Theme system: suppression des themes alternatifs (`studio`, `benev`, `timeline`, `spreadsheet`, `atelier`, etc.).
- Design admin: conserve, mais recentre sur un seul socle Bootstrap parametable.
- Presets integres: suppression, car ils incarnent encore des variantes de theme packagées.
- Toggle Bootstrap: suppression de la logique de desactivation; Bootstrap devient inconditionnel.

## Perimetre

### A supprimer

- `frontend-next/`
- routes `/app/*`
- routes `/ui/mode/*`
- vue `frontend_log_event` si elle n'est plus consommee une fois `/app/*` retire
- `wms/views_next_frontend.py`
- `wms/ui_mode.py`
- tests `wms/tests/views/tests_views_next_frontend.py`
- branches et selecteurs CSS de themes non Bootstrap dans `wms/static/scan/scan.css`
- presets integres et gestion de presets personnalises si leur seul role est de dupliquer un systeme de themes
- branches `scan_bootstrap_enabled` devenues mortes dans templates/tests/contexte

### A conserver

- templates Django Scan / Portal / Benevole / Home / Admin personnalises
- CSS de pont Bootstrap (`scan-bootstrap.css`, `portal-bootstrap.css`, `admin-bootstrap.css`)
- variables de design runtime exposees via `includes/design_vars_style.html`
- page `scan/admin/design/` comme editeur direct de tokens/variables

## Architecture Technique

### 1. UI unique cote routage

Le routeur principal ne doit plus exposer de surface `/app/*` ni de mode d'interface selectionnable. `asf_wms/urls.py` est reduit aux entrees Django legacy utiles (`/`, `/scan/`, `/portal/`, `/benevole/`, `/planning/`, `/admin/`, `/api/`).

### 2. UI unique cote contexte

Le context processor continue d'exposer:
- `wms_design_tokens`
- visibilites metier existantes (`scan_billing_visible`, `scan_billing_admin_visible`)

Il ne doit plus exposer de notion de mode (`wms_ui_mode`, `wms_ui_mode_is_next`) ni de feature flag Bootstrap des lors que Bootstrap est toujours actif.

### 3. Bootstrap toujours actif

Les templates ne doivent plus brancher conditionnellement:
- les assets Bootstrap,
- les classes `scan-bootstrap-enabled`, `portal-bootstrap-enabled`, `home-bootstrap-enabled`, `admin-bootstrap-enabled`,
- les classes Bootstrap appliquees aux composants.

Le rendu cible est la version aujourd'hui active avec Bootstrap, mais rendue inconditionnellement.

### 4. Design recentre sur un seul systeme

`scan/admin/design/` reste l'outil d'edition runtime, mais il doit piloter un seul systeme visuel:
- couleurs,
- typographies,
- densite,
- boutons,
- champs,
- cartes,
- navigation,
- tableaux,
- etats metier.

Le formulaire reste utile, mais la logique de presets integres (`Rectangulaire`, `Contraste`, `Stream`) et la sauvegarde de themes derivables doit etre retiree pour eviter de reintroduire plusieurs UI concurrentes.

### 5. CSS simplifie

`wms/static/scan/scan.css` doit etre purgee des blocs lies a des selectors comme:
- `:root[data-theme=...]`
- `:root[data-ui=...]`
- composants de toggle associes a ces themes

Le CSS conserve la base commune necessaire au shell Django et le pont Bootstrap local.

## Donnees et Migration

- Les tables liees a `UserUiPreference` ne seront plus utilisees une fois `ui_mode` retire.
- Les champs runtime `scan_bootstrap_enabled`, `design_selected_preset`, `design_custom_presets` deviennent candidats a suppression ou neutralisation selon le cout de migration.
- Le nettoyage doit privilegier la simplicite du runtime actuel sans casser les pages d'administration design.

## Strategie de Tests

### Red-Green cible

- ajouter/adapter des tests qui prouvent que les routes `/app/*` et `/ui/mode/*` ne sont plus presentes,
- verifier que les templates rendent toujours les assets/classes Bootstrap sans dependre d'un flag,
- verifier que l'admin Design ne propose plus de presets de themes,
- verifier que les CSS ne contiennent plus les selectors de themes retires.

### Regression ciblee

- `wms.tests.views.tests_scan_bootstrap_ui`
- `wms.tests.views.tests_portal_bootstrap_ui`
- `wms.tests.views.tests_views_home`
- `wms.tests.admin.tests_admin_bootstrap_ui`
- `wms.tests.views.tests_views_scan_admin`

## Risques

- quelques tests existants valident encore des chemins de compatibilite `SCAN_BOOTSTRAP_ENABLED=False`; ils devront etre reecrits vers une UI Bootstrap toujours active;
- l'admin Design reference aujourd'hui des presets et snapshots; il faudra supprimer cette logique sans perdre l'edition directe des tokens;
- certaines pages standalone (print/public) utilisent encore des branches conditionnelles Bootstrap qu'il faudra convertir proprement.
