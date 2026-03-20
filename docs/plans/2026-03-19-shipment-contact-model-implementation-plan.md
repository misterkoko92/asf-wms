# Shipment Contact Model Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remplacer le moteur `org-roles` pour le sous-domaine expedition par un modele dedie centre sur expediteurs, structures destinataires partagees, liens explicites et referents autorises, sans toucher a la migration Next/React.

**Architecture:** Garder `contacts.Contact` comme referentiel personne/structure, introduire un nouveau sous-domaine Django legacy pour les parties d'expedition, backfiller les donnees depuis l'existant, puis rebrancher progressivement scan, portail, admin et rendu d'expedition sur cette nouvelle source de verite. La migration est incrementale: coexistence transitoire, bascule du runtime expedition, puis retrait des lectures `org-roles` sur ce perimetre.

**Tech Stack:** Django 4.2, ORM, migrations Django, templates Django legacy, formulaires Django, services Python, `manage.py test`.

---

### Task 1: Introduire les modeles dedies aux parties d'expedition

**Files:**
- Create: `wms/models_domain/shipment_parties.py`
- Modify: `wms/models.py`
- Create: `wms/tests/shipment/tests_shipment_party_models.py`

**Step 1: Write the failing test**

Ajouter des tests modeles pour:
- `ShipmentShipper`,
- `ShipmentRecipientOrganization`,
- `ShipmentRecipientContact`,
- `ShipmentShipperRecipientLink`,
- `ShipmentAuthorizedRecipientContact`,
- unicite d'un seul referent par defaut actif par lien,
- unicite d'un seul correspondant actif par escale.

```python
def test_authorized_recipient_contact_enforces_single_default_per_link():
    ...
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.shipment.tests_shipment_party_models -v 2`
Expected: FAIL because the models do not exist yet.

**Step 3: Write minimal implementation**

Implementer dans `wms/models_domain/shipment_parties.py`:
- les enums de validation ASF,
- `ShipmentShipper`,
- `ShipmentRecipientOrganization`,
- `ShipmentRecipientContact`,
- `ShipmentShipperRecipientLink`,
- `ShipmentAuthorizedRecipientContact`,
- les contraintes d'unicite et validations `clean()`.

Exporter les nouveaux modeles via `wms/models.py`.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.shipment.tests_shipment_party_models -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/shipment_parties.py wms/models.py wms/tests/shipment/tests_shipment_party_models.py
git commit -m "feat(shipment): add dedicated shipment party models"
```

### Task 2: Ajouter les resolvers et filtres runtime du nouveau modele

**Files:**
- Create: `wms/shipment_party_registry.py`
- Create: `wms/tests/shipment/tests_shipment_party_registry.py`

**Step 1: Write the failing test**

Ajouter des tests de service pour:
- expediteurs eligibles par escale,
- structures destinataires eligibles par expediteur + escale,
- referents eligibles par lien,
- referent par defaut par lien,
- exception `can_send_to_all` pour ASF.

```python
def test_eligible_recipient_organizations_filter_by_shipper_and_stopover():
    ...
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.shipment.tests_shipment_party_registry -v 2`
Expected: FAIL because the registry service does not exist yet.

**Step 3: Write minimal implementation**

Implementer dans `wms/shipment_party_registry.py`:
- `eligible_shippers_for_stopover(...)`,
- `eligible_recipient_organizations_for_shipper(...)`,
- `eligible_recipient_contacts_for_link(...)`,
- `default_recipient_contact_for_link(...)`,
- helpers de resolution du correspondant d'escale.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.shipment.tests_shipment_party_registry -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/shipment_party_registry.py wms/tests/shipment/tests_shipment_party_registry.py
git commit -m "feat(shipment): add shipment party registry services"
```

### Task 3: Backfiller les nouvelles tables depuis org-roles

**Files:**
- Create: `wms/management/commands/backfill_shipment_parties_from_org_roles.py`
- Create: `wms/tests/management/tests_management_backfill_shipment_parties.py`
- Modify: `contacts/correspondent_recipient_promotion.py`

**Step 1: Write the failing test**

Ajouter des tests de commande couvrant:
- creation des expediteurs depuis l'existant,
- creation des structures destinataires depuis les bindings,
- backfill des referents destinataire,
- backfill du correspondant d'escale,
- support `--dry-run`.

```python
def test_backfill_creates_shared_recipient_structure_and_authorized_contacts():
    ...
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.management.tests_management_backfill_shipment_parties -v 2`
Expected: FAIL because the command does not exist yet.

**Step 3: Write minimal implementation**

Implementer la commande:
- lecture de `ShipperScope`,
- lecture de `RecipientBinding`,
- lecture de `Destination.correspondent_contact`,
- creation ou rapprochement des structures expediteur/destinataire,
- creation des referents et des liens autorises,
- rapport de synthese.

Adapter `contacts/correspondent_recipient_promotion.py` pour ne pas recreer de semantics contraires au nouveau modele pendant la phase transitoire.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.management.tests_management_backfill_shipment_parties -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/management/commands/backfill_shipment_parties_from_org_roles.py wms/tests/management/tests_management_backfill_shipment_parties.py contacts/correspondent_recipient_promotion.py
git commit -m "feat(shipment): backfill shipment parties from org roles"
```

### Task 4: Brancher le formulaire scan sur le nouveau modele

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/scan_shipment_handlers.py`
- Modify: `wms/shipment_form_helpers.py`
- Modify: `wms/shipment_helpers.py`
- Create: `wms/tests/forms/tests_forms_shipment_parties.py`

**Step 1: Write the failing test**

Ajouter des tests formulaire/handler pour:
- filtrage `escale -> expediteur -> structure destinataire -> referent`,
- preselection du referent destinataire par defaut,
- correspondant derive automatiquement de l'escale,
- blocage si la structure ou le lien ne sont pas valides ASF / actifs.

```python
def test_scan_shipment_form_prefills_default_recipient_contact_for_shipper_link():
    ...
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.forms.tests_forms_shipment_parties -v 2`
Expected: FAIL because scan still reads org-roles.

**Step 3: Write minimal implementation**

Modifier:
- `wms/forms.py` pour remplacer les querysets `org-roles` par les resolvers du nouveau registre,
- `wms/scan_shipment_handlers.py` pour valider et resoudre via `ShipmentShipperRecipientLink`,
- `wms/shipment_form_helpers.py` et `wms/shipment_helpers.py` pour fournir le JSON frontend aligne.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.forms.tests_forms_shipment_parties -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/forms.py wms/scan_shipment_handlers.py wms/shipment_form_helpers.py wms/shipment_helpers.py wms/tests/forms/tests_forms_shipment_parties.py
git commit -m "feat(scan): switch shipment selection to shipment party model"
```

### Task 5: Stocker l'instantane immuable des parties sur l'expedition

**Files:**
- Modify: `wms/models_domain/shipment.py`
- Create: `wms/shipment_party_snapshot.py`
- Modify: `wms/order_scan_handlers.py`
- Modify: `wms/scan_shipment_handlers.py`
- Create: `wms/tests/shipment/tests_shipment_party_snapshot.py`

**Step 1: Write the failing test**

Ajouter des tests pour:
- sauvegarde d'un instantane `referent + structure` pour expediteur, destinataire, correspondant,
- non-regression quand les fiches source changent ensuite,
- priorite de lecture de l'instantane sur les ecrans et exports.

```python
def test_shipment_keeps_party_snapshot_after_registry_change():
    ...
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.shipment.tests_shipment_party_snapshot -v 2`
Expected: FAIL because shipment still depends mainly on current contact refs and names.

**Step 3: Write minimal implementation**

Ajouter le minimum de champs necessaires sur `Shipment` pour figer:
- structure expediteur,
- referent expediteur,
- structure destinataire,
- referent destinataire,
- structure correspondant,
- referent correspondant,
- libelles figes.

Implementer `wms/shipment_party_snapshot.py` pour construire ces valeurs lors de la creation / mise a jour initiale.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.shipment.tests_shipment_party_snapshot -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/shipment.py wms/shipment_party_snapshot.py wms/order_scan_handlers.py wms/scan_shipment_handlers.py wms/tests/shipment/tests_shipment_party_snapshot.py
git commit -m "feat(shipment): persist immutable shipment party snapshot"
```

### Task 6: Corriger les libelles et vues pour lire l'instantane

**Files:**
- Modify: `wms/contact_labels.py`
- Modify: `wms/shipment_view_helpers.py`
- Modify: `wms/planning/sources.py`
- Modify: `wms/print_context.py`
- Create: `wms/tests/shipment/tests_shipment_party_labels.py`

**Step 1: Write the failing test**

Ajouter des tests pour:
- affichage `referent + structure`,
- lecture prioritaire de l'instantane dans les listes, impressions et exports planning,
- absence de regression pour les expeditions historiques sans instantane complet.

```python
def test_build_shipments_ready_rows_prefers_snapshot_label():
    ...
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.shipment.tests_shipment_party_labels -v 2`
Expected: FAIL because current helpers still collapse to organization names.

**Step 3: Write minimal implementation**

Mettre a jour:
- `wms/contact_labels.py`,
- `wms/shipment_view_helpers.py`,
- `wms/planning/sources.py`,
- `wms/print_context.py`,

pour privilegier l'instantane et rendre le format cible `referent + structure`.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.shipment.tests_shipment_party_labels -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/contact_labels.py wms/shipment_view_helpers.py wms/planning/sources.py wms/print_context.py wms/tests/shipment/tests_shipment_party_labels.py
git commit -m "fix(shipment): render shipment party snapshots in views and exports"
```

### Task 7: Refaire le portail destinataires autour de la structure partagee

**Files:**
- Modify: `wms/models_domain/portal.py`
- Modify: `wms/views_portal_account.py`
- Modify: `wms/views_portal_orders.py`
- Replace logic in: `wms/portal_recipient_sync.py`
- Create: `wms/tests/portal/tests_portal_shipment_parties.py`

**Step 1: Write the failing test**

Ajouter des tests portail pour:
- creation ou reutilisation d'une structure destinataire globale,
- ajout d'un referent a la structure,
- autorisation du referent pour l'expediteur courant,
- choix du referent par defaut,
- suggestions de doublons,
- maintien du statut ASF de la structure apres modification.

```python
def test_portal_adds_authorized_contact_to_existing_recipient_structure():
    ...
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_portal_shipment_parties -v 2`
Expected: FAIL because portal still syncs through `AssociationRecipient` and org-roles.

**Step 3: Write minimal implementation**

Modifier:
- le modele et/ou les formulaires portail pour centrer l'UX sur la structure destinataire,
- `wms/portal_recipient_sync.py` pour ecrire dans le nouveau sous-domaine,
- `wms/views_portal_account.py` et `wms/views_portal_orders.py` pour relire le nouveau registre.

Reduire `AssociationRecipient` a un role transitoire ou le remplacer selon la meilleure migration observee.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_portal_shipment_parties -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/portal.py wms/views_portal_account.py wms/views_portal_orders.py wms/portal_recipient_sync.py wms/tests/portal/tests_portal_shipment_parties.py
git commit -m "feat(portal): manage recipient structures and authorized contacts"
```

### Task 8: Refaire le cockpit admin contacts pour l'expedition

**Files:**
- Modify: `wms/forms_scan_admin_contacts_cockpit.py`
- Modify: `wms/scan_admin_contacts_cockpit.py`
- Modify: `templates/scan/admin_contacts.html`
- Create: `wms/tests/views/tests_views_scan_admin_shipment_parties.py`

**Step 1: Write the failing test**

Ajouter des tests vue/admin pour:
- liste des expediteurs,
- liste des structures destinataires,
- edition des liens expediteur -> destinataire,
- edition des referents autorises,
- designation du correspondant unique d'escale,
- fusion de structures.

```python
def test_admin_can_set_default_authorized_recipient_contact():
    ...
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_shipment_parties -v 2`
Expected: FAIL because the admin cockpit still exposes org-role concepts.

**Step 3: Write minimal implementation**

Refactoriser le cockpit pour montrer:
- expediteurs,
- structures destinataires,
- referents,
- liens,
- statut ASF,
- fusion et overrides admin.

Retirer de l'UX expedition les notions `role contact`, `shipper scope`, `recipient binding` du vocabulaire visible.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_shipment_parties -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/forms_scan_admin_contacts_cockpit.py wms/scan_admin_contacts_cockpit.py templates/scan/admin_contacts.html wms/tests/views/tests_views_scan_admin_shipment_parties.py
git commit -m "feat(admin): expose shipment party cockpit instead of org roles"
```

### Task 9: Basculer notifications, planning et impressions sur le nouveau modele

**Files:**
- Modify: `wms/signals.py`
- Modify: `wms/notification_policy.py`
- Modify: `wms/planning/communications.py`
- Modify: `wms/planning/communication_plan.py`
- Modify: `wms/print_pack_engine.py`
- Create: `wms/tests/emailing/tests_shipment_party_notifications.py`

**Step 1: Write the failing test**

Ajouter des tests pour:
- emails expediteur / destinataire / correspondant en lisant l'instantane et le nouveau registre,
- compatibilite des notifications avec le correspondant-destinataire,
- non-regression des documents et impressions.

```python
def test_correspondent_notifications_use_stopover_correspondent_snapshot():
    ...
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.emailing.tests_shipment_party_notifications -v 2`
Expected: FAIL because downstream domains still assume org-roles and current contact refs.

**Step 3: Write minimal implementation**

Mettre a jour les domaines secondaires pour:
- lire l'instantane d'expedition,
- utiliser le nouveau registre si une resolution live reste necessaire,
- ne plus dependre des contacts primaires `org-roles` pour l'expedition.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.emailing.tests_shipment_party_notifications -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/signals.py wms/notification_policy.py wms/planning/communications.py wms/planning/communication_plan.py wms/print_pack_engine.py wms/tests/emailing/tests_shipment_party_notifications.py
git commit -m "feat(shipment): route notifications and outputs through shipment party model"
```

### Task 10: Retirer les lectures org-roles du perimetre expedition et verifier la migration

**Files:**
- Modify: `wms/organization_role_resolvers.py`
- Modify: `wms/shipment_party_rules.py`
- Modify: `wms/tests/core/tests_org_roles_only_guardrails.py`
- Create: `wms/tests/core/tests_shipment_parties_guardrails.py`
- Modify: `README.md`

**Step 1: Write the failing test**

Ajouter des guardrails pour garantir que:
- scan, portail expedition et rendu shipment ne lisent plus `org-roles`,
- les modules `org-roles` restent acceptes seulement hors expedition,
- le nouveau registre est la seule source de verite sur ce perimetre.

```python
def test_runtime_shipment_paths_no_longer_import_org_role_resolvers():
    ...
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_shipment_parties_guardrails -v 2`
Expected: FAIL because legacy imports are still present.

**Step 3: Write minimal implementation**

Retirer ou isoler les lectures `org-roles` dans:
- `wms/organization_role_resolvers.py`,
- `wms/shipment_party_rules.py`,

et documenter la nouvelle source de verite dans `README.md`.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_shipment_parties_guardrails -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/organization_role_resolvers.py wms/shipment_party_rules.py wms/tests/core/tests_org_roles_only_guardrails.py wms/tests/core/tests_shipment_parties_guardrails.py README.md
git commit -m "refactor(shipment): remove org roles runtime from shipment flows"
```

### Task 11: Verification finale

**Files:**
- Modify if needed: any failing test targets discovered during final verification
- Create if needed: `docs/plans/2026-03-19-shipment-contact-model-verification.md`

**Step 1: Run targeted suites**

Run:
- `./.venv/bin/python manage.py test wms.tests.shipment -v 2`
- `./.venv/bin/python manage.py test wms.tests.forms -v 2`
- `./.venv/bin/python manage.py test wms.tests.portal -v 2`
- `./.venv/bin/python manage.py test wms.tests.views -v 2`
- `./.venv/bin/python manage.py test wms.tests.emailing -v 2`

Expected: PASS or a short list of targeted regressions.

**Step 2: Run broader verification**

Run:
- `./.venv/bin/python manage.py test wms.tests.core.tests_shipment_parties_guardrails -v 2`
- `./.venv/bin/python manage.py test wms.tests.core.tests_flow -v 2`
- `uv run make check`

Expected: PASS.

**Step 3: Write verification note**

Document:
- suites run,
- scope covered,
- known residual risks,
- migration notes,

in `docs/plans/2026-03-19-shipment-contact-model-verification.md`.

**Step 4: Commit**

```bash
git add docs/plans/2026-03-19-shipment-contact-model-verification.md
git commit -m "docs(shipment): record shipment contact model verification"
```
