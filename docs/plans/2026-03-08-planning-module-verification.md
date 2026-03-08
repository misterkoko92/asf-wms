# Planning Module Verification

## Scope
Verification finale executee sur la branche `codex/planning-foundation` dans le worktree dedie.

Objectif de cette note:
- conserver les commandes reelles executees
- documenter le resultat obtenu
- fournir une check-list operateur simple pour la recette manuelle
- garder visibles les limites volontaires de cette premiere fondation

## Automated Verification
### Follow-up Solver Port
```bash
ASF_TMP_DIR=/tmp/asf_wms_planning ./.venv/bin/python manage.py test wms.tests.planning wms.tests.views.tests_views_planning wms.tests.management.tests_management_makemigrations_check -v 1
```

Result:
- `31` tests executes
- `OK`

Couverture validee en plus de la fondation initiale:
- solveur `ortools_cp_sat_v1`
- compatibilite horaire benevole/vol
- exclusivite benevole sur vol physique multi-stop
- persistance des metadonnees vol `routing` et `route_pos`
- absence de drift de migration apres ajout des champs vol

### Command 1
```bash
ASF_TMP_DIR=/tmp/asf_wms_planning ./.venv/bin/python manage.py test wms.tests.planning -v 2
```

Result:
- `18` tests executes
- `OK`

Couverture validee:
- sources vols Excel et hybride
- import `ParamDest`
- domaine planning et versioning
- preparation des runs et validation bloquante
- solveur et contrat de persistance
- brouillons de communication et export Excel
- mises a jour expeditions depuis une version publiee
- contrainte benevole `max_colis_vol`

### Command 2
```bash
ASF_TMP_DIR=/tmp/asf_wms_planning ./.venv/bin/python manage.py test wms.tests.views.tests_views_planning wms.tests.views.tests_views_volunteer api.tests.tests -v 2
```

Result:
- `39` tests executes
- `OK`

Couverture validee:
- creation et consultation des runs planning
- lancement du solveur
- edition manuelle des affectations
- publication et duplication de version
- diff entre versions
- application des mises a jour expeditions
- portail benevole et ecrans de contraintes
- integrations API critiques deja presentes dans `asf-wms`

### Consolidated Outcome
- `57` tests executes
- `57` tests `OK`
- aucun drift de schema ni erreur de system check observe pendant cette verification finale

## Operator Checklist
Check-list de recette manuelle recommandee avant diffusion terrain:

1. Creation de run
- creer un run sur une semaine cible avec un `PlanningParameterSet` actif
- verifier le mode vols choisi: `excel`, `api` ou `hybrid`

2. Validation bloquante
- verifier qu'une destination sans `PlanningDestinationRule` remonte une `PlanningIssue`
- confirmer qu'un run en erreur de validation ne peut pas etre solve

3. Solveur
- lancer le solveur sur un run `ready`
- verifier qu'une `PlanningVersion v1` brouillon est creee

4. Correction manuelle
- modifier au moins une affectation dans la version brouillon
- verifier la persistance des notes et de la source `manual`

5. Publication v1
- publier la version
- verifier qu'une version publiee devient non editable

6. Duplication v2
- cloner `v1`
- verifier que `v2` reste en brouillon avec le lien `based_on`

7. Regeneration des brouillons
- publier `v2`
- regenerer les brouillons de communication
- verifier que les brouillons de `v1` et `v2` restent distincts
- verifier qu'un operateur peut retoucher le texte genere avant diffusion

8. Export Excel
- regenerer l'export `Planning.xlsx`
- verifier que le classeur est cree dans le repertoire temp configure

9. Mise a jour expeditions
- depuis une version publiee, lancer la mise a jour des expeditions
- verifier qu'une expedition deja `shipped` n'est pas ramenee en arriere
- verifier la creation de l'evenement de tracking `planned`

## Known Limits
- le solveur implemente dans cette branche est `ortools_cp_sat_v1`; il couvre deja la capacite par vol, la capacite benevole par vol, les horaires et l'exclusivite multi-stop, mais pas encore toute la parite metier du solveur historique
- le connecteur vols API est abstrait derriere `PlanningFlightApiClient`; la branche prepare l'integration, mais pas encore un client de production complet
- l'export `Planning.xlsx` est volontairement minimal et transitoire; il ne reproduit pas encore la structure historique complete du workbook legacy
- les communications sont generees comme brouillons editables dans `asf-wms`, mais l'envoi email ou WhatsApp reste manuel par choix produit
- l'application des mises a jour expeditions est volontairement conservative: seules les expeditions encore `packed` ou deja `planned` sont touchees

## Local Environment Note
Lors d'une verification plus large menee pendant l'implementation, la suite `wms.tests.emailing.tests_emailing` ne passait localement qu'apres compilation des catalogues de traduction:

```bash
./.venv/bin/python manage.py compilemessages -v 1
```

Ce point n'affecte pas les deux commandes de verification finale ci-dessus, mais reste utile a connaitre avant de relancer la suite emailing complete sur un poste neuf.
