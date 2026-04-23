# Audit complet du repo - 2026-04-22

## Synthese executive

Audit realise sur le repo actif `/Users/EdouardGonnu/asf-wms`, branche `main`, en mode
`deep/full`.

Scope inclus :

- legacy Django actif : `asf_wms/`, `wms/`, `api/`, `contacts/`, `templates/`, assets JS/CSS legacy ;
- qualite, securite, dependances, CI, tests, migrations, operations, conformite, flux metier et maintenabilite ;
- revue documentaire via `docs/repo-reference/`.

Scope volontairement exclu par policy repo :

- traduction FR/EN et parite i18n ;
- migration Next/React et `frontend-next/`.

Reprise du 2026-04-22 :

- ce fichier est le rapport courant de l'audit complet du repo ;
- `docs/audit_2026-04-21.md` reste un rapport historique deja modifie localement ;
- reprise verifiee sur branche `main`, commit `e1c0d10f` ;
- les preuves critiques ont ete recontrolees localement : pins vulnerables, `pip-audit`
  informatif, comparaison API key non timing-safe, absence de throttling DRF global,
  absence de commande `check_referential_integrity`, hotspots de taille et liens
  `target="_blank"` sans `rel`.

Verdict :

- **P0 confirme : aucun.**
- **P1-01 ferme localement le 2026-04-23** — pins runtime corriges ; preuve `pip-audit`/CI a
  conserver avec la PR de fermeture.
- **P1 restants : 2** — conformite RGPD/juridique en attente validation humaine,
  monitoring/PRA en cours.
- **P2 ouverts : 4** — securite front/supply-chain, maintenabilite, integrite donnees/migrations, couverture E2E legacy.
- **P3 ouverts : 1** — gouvernance repo.

Les bases securite Django corrigees lors de la phase A sont bien presentes : `DEBUG=false` par
defaut, `DJANGO_SECRET_KEY` obligatoire hors tests, cookies securises en prod-like, HSTS/nosniff,
`DOCUMENT_SCAN_BACKEND=noop` interdit hors tests, Dependabot actif, couverture gatee a 93 %.

## Verifications executees

Commandes lancees pendant l'audit :

```bash
uv run make lint
uv run make typecheck
uv run make bandit
uv run make deploy-check-prod-like
# DJANGO_SECRET_KEY was exported in the shell for prod-like checks.
DJANGO_DEBUG=false \
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
./.venv/bin/python manage.py makemigrations --check --dry-run
# DJANGO_SECRET_KEY was exported in the shell for prod-like checks.
DJANGO_DEBUG=false \
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
./.venv/bin/python manage.py test \
  api.tests.tests_ui_e2e_workflows \
  wms.tests.emailing.tests_notifications_queue \
  wms.tests.emailing.tests_order_status_notifications \
  wms.tests.planning.tests_smoke_planning_flow \
  --parallel 1
./.venv/bin/pip-audit -r requirements.txt --disable-pip --no-deps \
  --format json --output /tmp/asf-wms-pip-audit-report.json
```

Resultats :

- `ruff` : OK.
- `mypy` : OK, 57 fichiers scopes.
- `bandit` : OK, 0 issue, 80 327 lignes scannees.
- `check --deploy` prod-like : OK.
- `makemigrations --check --dry-run` : OK, `No changes detected`.
- smoke tests legacy cibles : OK, 19 tests.
- `pip-audit` : KO, 12 vulnerabilites connues sur 4 paquets.

Note : une tentative initiale de `make migrate-check` sans env a echoue parce que
`DJANGO_SECRET_KEY` est obligatoire hors tests. La relance avec environnement explicite a confirme
que les migrations sont a jour.

Limites de preuve :

- pas de couverture complete relancee pendant cette reprise ; le seuil global reste gate par CI ;
- pas de verification sur base de donnees production, logs reels, PythonAnywhere ou headers HTTP
  reels ;
- le rapport `/tmp/asf-wms-pip-audit-report.json` est une preuve locale temporaire, pas un
  artefact versionne ;
- les findings front CSP/SRI/`innerHTML` doivent etre fermes par audit cible avant remediation
  large.

## Findings confirmes

### P1-01 - Dependances vulnerables en production

**Categorie** : securite dependances
**Statut** : ferme localement le 2026-04-23
**Impact** : exposition a des CVE connues sur des composants runtime utilises par l'application.

Evidence :

- `pip-audit` a trouve 12 vulnerabilites connues.
- Paquets concernes :
  - `django==5.2.12` : 5 vulnerabilites, fix `5.2.13` ;
  - `cryptography==46.0.6` : 1 vulnerabilite, fix `46.0.7` ;
  - `pillow==12.1.1` : 1 vulnerabilite, fix `12.2.0` ;
  - `pypdf==6.9.2` : 5 vulnerabilites, fix minimum `6.10.2`.
- Pins runtime : `pyproject.toml` et `requirements.txt`.
- Le CI execute `pip-audit` en informatif avec `continue-on-error: true` et `|| true` :
  `.github/workflows/ci.yml`.
- Reprise P1-02/P1-03 : P1-01 a ete annonce termine avant cette reprise. Si la preuve n'est pas
  deja rattachee a la PR, conserver comme evidence de fermeture la sortie `pip-audit` sans CVE
  runtime non acceptee et la CI complete verte.
- Reprise P2-01 du 2026-04-23 : les pins runtime visibles sont `django==5.2.13`,
  `cryptography==46.0.7`, `pillow==12.2.0` et `pypdf==6.10.2` dans `pyproject.toml`,
  `requirements.txt` et `uv.lock`.
- Validation locale du 2026-04-23 : `./.venv/bin/pip-audit -r requirements.txt --disable-pip
  --no-deps` retourne `No known vulnerabilities found`.

Remediation :

1. Mettre a jour les pins :
   - Django `5.2.13`,
   - cryptography `46.0.7`,
   - Pillow `12.2.0`,
   - pypdf `6.10.2` ou superieur compatible.
2. Lancer `uv lock`, `make export-requirements`, puis CI complete.
3. Transformer l'audit dependances en gate bloquant au moins pour les CVE High/Critical.

Validation :

```bash
uv lock
make export-requirements
./.venv/bin/pip-audit -r requirements.txt --disable-pip --no-deps
make ci
```

### P1-02 - Conformite RGPD / juridique non cloturee

**Categorie** : conformite
**Statut** : en attente validation humaine
**Impact** : risque legal et operationnel superieur aux optimisations techniques, car le produit
manipule des donnees personnelles, documents sensibles et transferts hors UE probables.

Evidence :

- Le contexte repo liste les donnees personnelles, documents scannes et contenu colis comme sujets
  RGPD/douane sensibles : `docs/repo-reference/00-product-context.md`.
- Points critiques explicites :
  - transferts hors UE ;
  - sous-traitants PythonAnywhere, Brevo, Microsoft Graph, AF-KLM ;
  - durees de conservation a definir.
- Questions ouvertes documentees :
  - DPO ;
  - statut juridique ASF ;
  - mentions legales et CGU.
- Aucun fichier `LICENSE` detecte a la racine ; les documents produit visibles (mentions legales,
  CGU, confidentialite) restent a valider hors code avant publication plus large.
- Reprise P1-02 : `docs/policies/rgpd.md` existe comme brouillon operationnel et
  `docs/release_checklist.md` contient des controles RGPD/release. Le sujet reste non clos tant
  qu'un validateur humain n'a pas confirme DPO/referent, bases legales, retention, sous-traitants,
  transferts hors UE, mentions legales, confidentialite et CGU.
- Reprise textes P1-02 : les brouillons `docs/policies/confidentialite.md`,
  `docs/policies/cgu-portail.md`, `docs/policies/mentions-legales.md`,
  `docs/policies/mentions-information-formulaires.md` et
  `docs/policies/droits-des-personnes.md` ont ete proposes sur base de bonnes pratiques
  CNIL/Service-Public. Ils restent a valider humainement avant publication.

Remediation :

1. Creer `docs/policies/rgpd.md` avec registre de donnees, finalites, bases legales, retention,
   sous-traitants et transferts hors UE.
2. Creer ou valider les mentions legales, politique de confidentialite et CGU.
3. Ajouter une procedure export/suppression/anonymisation des donnees personnelles.
4. Ajouter une section "donnees sensibles" dans les checklists de release.

Validation :

```bash
rg -n "RGPD|retention|sous-traitants|transferts hors UE|DPO" docs/policies docs/release_checklist.md
```

### P1-03 - Monitoring, PRA et backups encore trop faibles pour prod sereine

**Categorie** : operations
**Statut** : en cours
**Impact** : incidents decouverts par les utilisateurs, restauration non prouvee, diagnostic manuel
en cas de regression prod.

Evidence :

- `docs/repo-reference/00-product-context.md` indique : pas de stack de monitoring, incidents
  remontes par utilisateurs.
- `docs/operations.md` contient des commandes backup/restore de base, mais pas de preuve de drill
  periodique ni RPO/RTO.
- `docs/release_checklist.md` demande de confirmer un backup, sans preuve automatique de restore.
- Reprise P1-03 : `docs/operations.md` trace maintenant les cibles RPO/RTO initiales, la
  procedure de restore drill mensuel, les playbooks erreurs 500/restore drill et le chemin de
  monitoring minimal. `docs/release_checklist.md` demande maintenant la preuve DB/media backup,
  restore drill, RPO/RTO et monitoring.
- Reprise P1-03 technique : Sentry est cable cote Django via `sentry-sdk[django]`,
  `SENTRY_DSN` et `python manage.py check_sentry_runtime`, avec PII par defaut desactive,
  request bodies/local variables exclus, et redaction des query strings/secrets avant envoi.
  La fermeture complete reste conditionnee a la configuration DSN hors depot, la verification
  d'un evenement de test dans le projet Sentry et au moins un restore drill DB/media prouve.

Remediation :

1. Ajouter Sentry free tier ou equivalent budget-compatible.
2. Definir RPO/RTO minimal et procedure de restore MySQL documentee.
3. Ajouter un drill mensuel de restauration sur dump anonymise ou environnement local.
4. Ajouter un runbook incident : rollback, queue email, queue document scan, contacts a prevenir.

Validation :

```bash
rg -n "SENTRY|RPO|RTO|restore drill|backup" docs asf_wms
```

## Findings P2

### P2-01 - Durcissement API et acces QR incomplet

**Categorie** : securite application
**Statut** : traite localement le 2026-04-23, en attente CI/merge

Evidence :

- La cle d'integration est comparee avec `==`, pas `hmac.compare_digest` :
  `api/v1/permissions.py`.
- `REST_FRAMEWORK` ne definit pas de throttling global :
  `asf_wms/settings.py`.
- Les grants QR ont `is_active` mais pas d'expiration visible :
  `wms/models_domain/shipment.py`.
- La recuperation d'acces QR ne montre pas de throttle equivalent aux autres formulaires publics :
  `wms/views_shipment_tracking_access.py`.
- `AUTH_PASSWORD_VALIDATORS` utilise `MinimumLengthValidator` sans option explicite ; Django garde
  donc le minimum par defaut.
- Reprise P2-01 du 2026-04-23 : `api/v1/permissions.py` utilise `hmac.compare_digest`,
  `REST_FRAMEWORK` definit des throttles globaux user/anon, les nouveaux
  `ShipmentTrackingAccessGrant` portent `expires_at`, les lookups ignorent les grants expires,
  login/recovery QR sont throttles par identifiant/email + IP (+ token pour recovery), et
  `MinimumLengthValidator` est explicite a 12 caracteres.
- Validation locale du 2026-04-23 : 39 tests cibles OK, `makemigrations --check --dry-run`
  retourne `No changes detected`, et `ruff check` cible retourne `All checks passed`.

Remediation :

1. Remplacer la comparaison de cle API par `hmac.compare_digest`.
2. Ajouter des throttles DRF par defaut pour API authentifiee/integration.
3. Ajouter expiration ou politique de rotation des `ShipmentTrackingAccessGrant`.
4. Ajouter throttle cache sur login/recovery QR par email/IP/token.
5. Monter le minimum password a 12 caracteres si compatible avec les usages.

Validation :

```bash
./.venv/bin/python manage.py test \
  api.tests.tests_permissions \
  wms.tests.core.tests_security_settings \
  wms.tests.shipment.tests_shipment_tracking_access \
  wms.tests.views.tests_views_shipment_tracking_access -v 2
```

### P2-02 - Securite frontend et supply-chain a renforcer

**Categorie** : securite frontend
**Statut** : traite localement, en attente CI/merge

Evidence :

- Initialement, aucun `Content-Security-Policy` visible dans `asf_wms/settings.py`,
  templates ou docs.
- Initialement, plusieurs templates chargent des CDN ; beaucoup ont SRI, mais certaines pages benevole/planning
  et certains assets OCR ne montrent pas de SRI/self-host.
- Initialement, `rg` a trouve plusieurs `target="_blank"` sans `rel` direct, par exemple
  `templates/portal/order_detail.html`.
- Plusieurs `innerHTML` existent dans JS legacy ; certains sont vides/constants, mais il faut
  auditer les chemins ou des donnees serveur/utilisateur peuvent entrer.

Traitement local 2026-04-23 :

- CSP `Report-Only` ajoute via `wms.security_headers.ContentSecurityPolicyReportOnlyMiddleware`,
  active par defaut et configurable par environnement.
- Bootstrap CDN benevole/planning declare SRI + `crossorigin`.
- `target="_blank"` sans `rel` corrige ou aligne pour le scan statique.
- Flux touches `portal/account.html` et `print_pack_mapping_editor.js` bascules vers DOM APIs
  plutot que `insertAdjacentHTML`, `row.innerHTML` ou `.outerHTML`.
- `pip-audit` a detecte puis confirme la correction des advisories `pygments`, `requests` et
  `uv` apres upgrade lock/export/sync.

Remediation :

1. Ajouter CSP en `Report-Only`, puis durcir progressivement.
2. Self-host ou ajouter SRI pour Bootstrap/Tabler/Tesseract quand possible.
3. Corriger tous les liens `target="_blank"` sans `rel="noopener"`.
4. Auditer les `innerHTML` et remplacer par `textContent`/DOM APIs quand la source n'est pas
   strictement constante.

Validation :

```bash
rg -n --pcre2 'target="_blank"(?![^>]*rel=)' templates wms/static
rg -n "Content-Security-Policy" asf_wms templates docs
./.venv/bin/python manage.py test wms.tests.core.tests_security_settings -v 2
./.venv/bin/pip-audit
```

### P2-03 - Maintenabilite : hotspots trop gros

**Categorie** : maintenabilite
**Statut** : ouvert

Evidence :

- `wms/static/scan/scan.js` : 4562 lignes.
- `api/v1/ui_views.py` : 2824 lignes.
- `wms/views_scan_shipments.py` : 1998 lignes.
- `wms/views_portal_account.py` : 1776 lignes.
- `wms/admin.py` : 1650 lignes.

Remediation :

1. Ne pas lancer de refacto global.
2. A chaque modification fonctionnelle, extraire le workflow touche vers service/helper teste.
3. Garder les vues comme orchestration HTTP, deplacer logique metier vers `wms/domain`,
   `wms/application` ou modules specialises existants.
4. Etendre progressivement le scope `mypy`/`pyright` aux modules extraits.

Validation :

```bash
wc -l api/v1/ui_views.py wms/views_scan_shipments.py wms/views_portal_account.py wms/admin.py wms/static/scan/scan.js
make typecheck
make lint
```

### P2-04 - Integrite donnees / migrations : filet periodique absent

**Categorie** : donnees
**Statut** : traite localement, en attente CI/merge

Evidence :

- `wms/migrations` contient 127 fichiers.
- Nombreux `RunPython`, souvent non reversibles ou `noop`, ce qui est normal pour des backfills,
  mais augmente le besoin de controles d'integrite post-migration.
- Initialement, aucune commande `check_referential_integrity` detectee dans
  `wms/management/commands`.

Traitement local 2026-04-23 :

- Commande read-only `check_referential_integrity` ajoutee, bloquante par defaut et disponible en
  `--report-only` pour maintenance mensuelle.
- Invariants couverts : status shipments/cartons/lots, destination shipment non-draft, cartons
  assignes sans shipment, lots/reservations incoherents, grants QR actifs invalides, scan status
  documentaire invalide, recipients actifs synchronises vers contacts invalides.
- Runbook mensuel, restore drill et release checklist mis a jour.

Remediation :

1. Creer `check_referential_integrity`.
2. Controler au minimum :
   - shipments sans destination/contact incoherent ;
   - cartons orphelins ou statuts impossibles ;
   - stock/lots/reservations incoherents ;
   - grants QR actifs sans user/contact/volunteer valide ;
   - documents sensibles sans scan status coherent ;
   - recipients/contacts desynchronises.
3. Ajouter la commande au runbook mensuel et a la release checklist.

Validation :

```bash
./.venv/bin/python manage.py check_referential_integrity
./.venv/bin/python manage.py test wms.tests.management -v 2
```

### P2-05 - Couverture E2E navigateur legacy incomplete

**Categorie** : tests fonctionnels
**Statut** : ouvert

Evidence :

- Il existe 321 fichiers de tests Python et des smoke tests legacy utiles.
- Le harness navigateur Playwright existe surtout dans `wms/tests/core/tests_ui.py`, avec 9 tests
  `ScanUiTests`, mais la CI navigateur visible cible surtout Next/React, scope actuellement pause.

Remediation :

1. Ajouter 3 scenarios Playwright legacy critiques :
   - scan stock/reception/pack ;
   - creation expedition + documents ;
   - portail destinataire commande/profil.
2. Les garder opt-in local ou scheduled CI hebdo pour ne pas ralentir la CI principale.
3. Documenter la commande dans `docs/release_checklist.md`.

Validation :

```bash
RUN_UI_TESTS=1 ./.venv/bin/python manage.py test wms.tests.core.tests_ui.ScanUiTests -v 2
```

## Finding P3

### P3-01 - Gouvernance repo minimale absente

**Categorie** : gouvernance
**Statut** : ouvert

Evidence :

- Absence detectee de `LICENSE`, `CONTRIBUTING`, `CHANGELOG`, `CODEOWNERS`, PR template.
- Le repo depend fortement de travail assiste par agents ; des conventions explicites reduiraient
  les regressions et le bruit de revue.

Remediation :

1. Ajouter `CONTRIBUTING.md` avec commandes CI, scopes geles, workflow de review.
2. Ajouter `.github/pull_request_template.md`.
3. Ajouter `CODEOWNERS` si les proprietaires reels sont connus.
4. Decider et ajouter une licence si le repo doit etre partage.

Validation :

```bash
find .github -maxdepth 3 -type f -print
test -f CONTRIBUTING.md
test -f LICENSE
```

## Points positifs confirmes

- `DEBUG` est false par defaut et `DJANGO_SECRET_KEY` est obligatoire hors tests.
- Cookies session/CSRF securises en prod-like, HSTS/nosniff et `X_FRAME_OPTIONS=DENY`.
- `DOCUMENT_SCAN_BACKEND=noop` interdit hors tests.
- Uploads documentaires limites par extension, taille et signature magique.
- Document scan runtime dispose d'une queue et d'une commande de health check.
- Dependabot existe pour pip et GitHub Actions.
- `ruff`, `mypy`, `bandit`, deploy check, migrations check et smoke tests cibles passent.
- Couverture globale gatee a 93 % dans CI.

## Matrice de priorisation et fermeture

| ID | Severite | PR cible | Dependances | Critere de fermeture |
|----|----------|----------|-------------|----------------------|
| P1-01 | P1 | PR 1 | aucune | ferme localement ; conserver `pip-audit` sans CVE runtime non acceptee et CI complete verte |
| P1-02 | P1 | PR 2 | validation humaine juridique/RGPD | registre RGPD, retention, sous-traitants, transferts et textes visibles traces |
| P1-03 | P1 | PR 3 | DSN production + restore drill | Sentry configure/verifie, RPO/RTO, restore drill et runbook incident documentes |
| P2-01 | P2 | PR 4 | CI/merge | traite localement ; tests permissions/API/QR couvrent compare-digest, throttles et grants |
| P2-02 | P2 | PR 5 | CI/merge | traite localement ; plus de `_blank` sans `rel`, CSP report-only et audit `innerHTML` trace |
| P2-04 | P2 | PR 6 | CI/merge | traite localement ; commande `check_referential_integrity` testee et ajoutee au runbook |
| P2-03/P2-05 | P2 | PR 7+ | modifications fonctionnelles futures | extractions opportunistes et 3 smoke navigateur legacy documentes |
| P3-01 | P3 | opportuniste | decision proprietaires/licence | `CONTRIBUTING`, PR template, `CODEOWNERS`/licence si applicables |

Regle d'execution :

- PR 1 est fermee localement ; rattacher la preuve `pip-audit`/CI avant toute release prod
  significative si elle n'est pas deja dans la PR ;
- demarrer PR 2 et PR 3 sans attendre les chantiers P2, car ce sont des risques P1 non
  techniques ;
- PR 4 est traite localement avec TTL configurable des grants QR ; conserver la preuve de tests et
  CI avant merge ;
- ne rendre `pip-audit` bloquant qu'apres patch ou acceptation explicite des vulnerabilites
  restantes, sinon la CI bloquera `main` immediatement.

## Plan de remediation priorise

### PR 1 - Patch dependances et gate audit

Objectif : fermer P1-01.

Taches :

- mettre a jour Django, cryptography, Pillow, pypdf ;
- regenerer lock et requirements ;
- rendre `pip-audit` bloquant pour vulnerabilites runtime non acceptees ;
- verifier smoke legacy + CI.

Validation :

```bash
uv lock
make export-requirements
./.venv/bin/pip-audit -r requirements.txt --disable-pip --no-deps
make ci
```

Statut 2026-04-23 : ferme localement, preuve finale `pip-audit`/CI a rattacher.

### PR 2 - Conformite RGPD et legal

Objectif : cadrer P1-02.

Taches :

- creer `docs/policies/rgpd.md` ;
- definir la retention par categorie de donnees ;
- documenter sous-traitants et transferts hors UE ;
- tracer les decisions DPO, mentions legales, confidentialite et CGU ;
- ajouter la checklist "donnees sensibles" dans la release checklist.

Validation :

```bash
rg -n "RGPD|retention|sous-traitants|transferts|DPO|CGU|confidentialite" docs
```

### PR 3 - Ops, monitoring et PRA

Objectif : fermer P1-03.

Taches :

- cabler Sentry cote Django et configurer le DSN production hors depot ;
- documenter backup/restore DB + MEDIA + secrets avec RPO/RTO ;
- ajouter procedure de restore drill mensuel ;
- ajouter runbook incident : rollback, queues email/document scan, contacts a prevenir ;
- lier la preuve de backup/restore a `docs/release_checklist.md`.

Validation :

```bash
rg -n "SENTRY|RPO|RTO|restore drill|incident|rollback|backup" docs asf_wms
python manage.py check_sentry_runtime --allow-missing
python manage.py check_sentry_runtime --send-test  # apres configuration du DSN reel
```

### PR 4 - Durcissement API/QR

Objectif : fermer P2-01.

Taches :

- `hmac.compare_digest` pour cle integration ;
- throttles DRF globaux ou scopes explicites ;
- throttle recovery/login QR par email/IP/token ;
- champ ou politique d'expiration/rotation des grants QR ;
- tests permissions et vues QR.

Validation :

```bash
./.venv/bin/python manage.py test \
  api.tests.tests_permissions \
  wms.tests.core.tests_security_settings \
  wms.tests.shipment.tests_shipment_tracking_access \
  wms.tests.views.tests_views_shipment_tracking_access -v 2
```

Statut 2026-04-23 : traite localement, en attente CI/merge.

### PR 5 - Front security cleanup

Objectif : reduire P2-02.

Taches :

- corriger `target="_blank"` sans `rel` ; fait localement
- CSP report-only ; fait localement
- SRI/self-host des CDN prioritaires ; Bootstrap benevole/planning fait localement
- audit `innerHTML` sur flux utilisateurs ; flux touches couverts localement

Validation :

```bash
rg -n --pcre2 'target="_blank"(?![^>]*rel=)' templates wms/static
rg -n "Content-Security-Policy" asf_wms templates docs
./.venv/bin/python manage.py test wms.tests.core.tests_security_settings -v 2
./.venv/bin/pip-audit
```

Statut 2026-04-23 : traite localement, en attente CI/merge.

### PR 6 - Integrity check

Objectif : fermer P2-04.

Taches :

- creer `check_referential_integrity` ; fait localement
- ajouter tests management ; fait localement
- documenter dans operations/release checklist ; fait localement

Validation :

```bash
./.venv/bin/python manage.py check_referential_integrity
./.venv/bin/python manage.py test wms.tests.management -v 2
```

Statut 2026-04-23 : traite localement, en attente CI/merge.

### PR 7+ - Refactors opportunistes et E2E legacy

Objectif : reduire P2-03 et P2-05 sans big bang.

Taches :

- extraire les workflows touches lors des features ;
- ajouter smoke navigateur legacy sur les 3 parcours critiques ;
- etendre typing aux modules extraits.

Validation :

```bash
make lint
make typecheck
RUN_UI_TESTS=1 ./.venv/bin/python manage.py test wms.tests.core.tests_ui.ScanUiTests -v 2
```

## Risques residuels et hypotheses

- Pas d'audit sur base de donnees production ni logs reels.
- Pas de pentest externe.
- Pas de verification runtime PythonAnywhere, domaine, TLS, headers HTTP reels.
- Pas de couverture complete lancee pendant cet audit ; la CI la gate deja a 93 %.
- Les scopes traduction et Next/React restent geles et n'ont pas ete audites en detail.

## Decision release recommandee

Decision : **go conditionnel**, pas de blocage P0. P1-01 est ferme localement ; conserver la preuve
`pip-audit`/CI de fermeture avant release prod significative. Les sujets RGPD/PRA avancent en
parallele, mais ils ne doivent pas rester ouverts avant une generalisation d'usage ou exposition
plus large du portail.

## Checklist de cloture de cet audit

- [ ] PR 1 mergee avec preuve `pip-audit`/CI, ou vulnerabilites runtime acceptees avec
  justification datee.
- [ ] PR 2 a un validateur humain identifie pour RGPD/legal.
- [ ] PR 3 prouve au moins un chemin de detection d'erreur et un restore drill.
- [ ] Les P2 non traites sont soit planifies, soit deplaces dans un registre de risques acceptes.
- [ ] `docs/repo-reference/` est mis a jour si une remediation modifie route, contrat partage,
  smoke test, runbook operationnel ou regle metier critique.
- [ ] Les commandes de validation de chaque PR sont collees dans la description de PR ou le
  changelog de remediation.
