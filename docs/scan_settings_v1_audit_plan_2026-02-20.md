# Audit et plan d'action - Onglet Parametres (V1)

Date: 2026-02-20
Projet: ASF WMS
Scope: `/scan/settings/` (logique, regles, flux, couverture tests)

## 1) Decision produit

- Validation de l'audit et des actions proposees.
- Exception confirmee: **le point 5 (permissions fines dediees)** n'est pas retenu.

## 2) Constats d'audit

### C1 - Incoherence de validation minimum (corrige)

Constat:
- L'interface affichait `min=1`, mais le serveur acceptait `0` sur plusieurs champs.
- Le runtime applique ensuite un clamp `>=1`, ce qui masquait l'erreur de saisie.

Impact:
- Incoherence entre ce que l'utilisateur saisit, ce qui est persiste, et ce qui est effectivement utilise.

References:
- `wms/forms_scan_settings.py`
- `wms/runtime_settings.py`

Statut:
- **Corrige**: validation serveur stricte `>=1` appliquee au formulaire.

### C2 - Tracabilite des changements incomplete (corrige)

Constat:
- Seuls `updated_by` et `updated_at` sont stockes.
- Pas d'historique detaille des anciennes/nouvelles valeurs.

Impact:
- Investigation et audit operationnel limites.

Reference:
- `wms/models_domain/integration.py` (`WmsRuntimeSettings`)

Statut:
- **Corrige**: journal d'audit runtime ajoute (historique des changements).

### C3 - Couverture de tests transverses insuffisante (corrige)

Constat initial:
- Bonne couverture de la vue `scan_settings`, mais couverture transversale partielle des effets reels.

Statut:
- **Corrige**: couverture intermediaire + E2E etendue sur flux parametres.

## 3) Changements implementes

### 3.1 Validation formulaire runtime

Fichier:
- `wms/forms_scan_settings.py`

Actions:
- Ajout d'un groupe de champs a contrainte minimale (`MIN_ONE_FIELDS`).
- Application de validation serveur `MinValueValidator(1)` pour ces champs.
- Uniformisation du message d'erreur min-value.
- Conservation de la regle metier `retry_max >= retry_base`.

### 3.2 Tests formulaire (intermediaire)

Fichier:
- `wms/tests/forms/tests_forms_scan_settings.py`

Tests ajoutes:
- accepte les valeurs minimales a 1.
- refuse les valeurs < 1.
- refuse `retry_max < retry_base`.

### 3.3 Tests runtime (intermediaire)

Fichier:
- `wms/tests/core/tests_runtime_settings.py`

Tests ajoutes:
- fallback correct si la table runtime est indisponible.
- clamp correct des valeurs runtime invalides persistees.
- verification de la regle effective legacy: `env_flag AND runtime_flag`.

### 3.4 Tests vue + E2E Parametres

Fichier:
- `wms/tests/views/tests_views_scan_settings.py`

Ajouts:
- redirection anonyme vers login admin.
- exposition correcte des flags `legacy_env_disabled` et `legacy_effective_enabled`.
- rejet des valeurs < 1 au POST.
- E2E: changement `stale_drafts_age_days` repercute sur `scan_shipments_ready`.
- E2E: desactivation runtime legacy => endpoint legacy de tracking en `404`.

### 3.5 Journal d'audit runtime

Fichiers:
- `wms/models_domain/integration.py`
- `wms/migrations/0051_wmsruntimesettingsaudit.py`
- `wms/views_scan_settings.py`

Actions:
- Ajout du modele `WmsRuntimeSettingsAudit`:
  - `changed_at`, `changed_by`, `change_note`,
  - `changed_fields`, `previous_values`, `new_values`.
- Creation automatique d'une entree d'audit a chaque sauvegarde effective.
- Affichage d'un historique recent directement dans l'onglet Parametres.

### 3.6 Preview d'impact + presets + garde-fous UX

Fichiers:
- `wms/views_scan_settings.py`
- `templates/scan/settings.html`
- `wms/forms_scan_settings.py`

Actions:
- Ajout d'une action `Previsualiser impact` (sans sauvegarde).
- Apercu calcule:
  - brouillons stale selon `stale_drafts_age_days`,
  - queue email bloquee selon `email_queue_processing_timeout_seconds`,
  - etat effectif legacy (env AND runtime).
- Ajout de presets operationnels:
  - `standard`,
  - `incident_email_queue`.
- Garde-fou UX:
  - `change_note` obligatoire si au moins un parametre runtime est modifie.

### 3.7 Extension E2E queue email

Fichier:
- `wms/tests/views/tests_views_scan_settings.py`

Ajout:
- E2E `email_queue_processing_timeout_seconds` -> effet visible sur la carte
  dashboard `Queue email bloquee (timeout)`.

## 4) Validation execution tests

Suites lancees et resultat:
- `manage.py test wms.tests.forms.tests_forms_scan_settings wms.tests.views.tests_views_scan_settings` -> OK
- `manage.py test wms.tests.core.tests_runtime_settings` -> OK
- `manage.py test wms.tests.views.tests_views_scan_dashboard wms.tests.views.tests_views_scan_shipments wms.tests.views.tests_views` -> OK

## 5) Plan d'action (mis a jour)

1. [x] Journal d'audit runtime (qui/quand/avant/apres/commentaire).
2. [x] Previsualisation d'impact avant sauvegarde.
3. [x] Garde-fous UX (commentaire obligatoire en cas de changement).
4. [x] Presets operationnels (standard, incident queue email).
5. [x] E2E queue email sur timeout de processing.

## 6) Notes de suivi

- Ce document est la reference de suivi pour l'onglet Parametres V1.
- En cas de nouvelles evolutions, completer ce fichier (historique des decisions + statut des actions).
