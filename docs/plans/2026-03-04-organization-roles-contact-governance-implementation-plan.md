# Organization Roles and Contact Governance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrer la gestion des contacts legacy vers un modele base sur `Organization` + roles metiers + bindings destinataire/expediteur/escale, avec notifications fines, revue ASF et blocages documentaires.

**Architecture:** Ajouter un nouveau sous-domaine de modeles role-based dans `wms.models_domain.portal` (pour limiter les imports transverses), puis brancher progressivement les flux metiers avec feature flags. Conserver une phase de compatibilite legacy en lecture seule, alimentee par un backfill non bloquant et un ecran admin de revue. Resoudre les notifications via une matrice globale par role, des subscriptions filtrables, et des regles de dedup/fallback principal.

**Tech Stack:** Django 4.2, ORM, migrations SQL Django, Django admin, templates Django, services metier Python, tests `manage.py test`.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`, `@superpowers:systematic-debugging`, `@superpowers:requesting-code-review`.

### Task 1: Introduire les enums et modeles role-based de base

**Files:**
- Modify: `wms/models_domain/portal.py`
- Modify: `wms/models.py`
- Create: `wms/tests/portal/tests_organization_roles_models.py`

**Step 1: Write the failing test**

Ajouter des tests modeles pour:
- roles disponibles (`SHIPPER`, `RECIPIENT`, `CORRESPONDENT`, `DONOR`, `TRANSPORTER`),
- obligation d'un contact principal unique par `(organization, role)`,
- interdiction d'activer un role sans principal email valide.

```python
class OrganizationRoleModelTests(TestCase):
    def test_role_assignment_requires_single_primary_contact(self):
        ...
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_organization_roles_models -v 2`
Expected: FAIL (modeles inexistants).

**Step 3: Write minimal implementation**

Ajouter dans `portal.py`:
- `OrganizationRole` (`TextChoices`),
- `OrganizationRoleAssignment`,
- `OrganizationContact` (V1: FK unique vers organization),
- `OrganizationRoleContact` avec contrainte `UniqueConstraint(..., condition=Q(is_primary=True, is_active=True))`.

Exporter via `wms/models.py`.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_organization_roles_models -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/portal.py wms/models.py wms/tests/portal/tests_organization_roles_models.py
git commit -m "feat(roles): add organization role assignment and role contacts"
```

### Task 2: Ajouter scope expediteur et binding destinataire versionne

**Files:**
- Modify: `wms/models_domain/portal.py`
- Create: `wms/tests/portal/tests_recipient_binding_models.py`

**Step 1: Write the failing test**

Ajouter des tests pour:
- `ShipperScope` avec `all_destinations=True` xor `destination` renseignee,
- `RecipientBinding` obligatoire sur `shipper_org`, `recipient_org`, `destination`,
- historisation (`valid_from`, `valid_to`) + pas de binding global.

```python
def test_recipient_binding_requires_destination(self):
    with self.assertRaises(ValidationError):
        RecipientBinding(..., destination=None).full_clean()
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_recipient_binding_models -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

Ajouter modeles:
- `ShipperScope`
- `RecipientBinding`
- validation `clean()` pour invariants metiers.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_recipient_binding_models -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/portal.py wms/tests/portal/tests_recipient_binding_models.py
git commit -m "feat(roles): add shipper scope and versioned recipient binding"
```

### Task 3: Ajouter modele correspondant par escale (default + overrides union)

**Files:**
- Modify: `wms/models_domain/portal.py`
- Create: `wms/correspondent_routing.py`
- Create: `wms/tests/shipment/tests_correspondent_routing.py`

**Step 1: Write the failing test**

Couvrir:
- resolution union: correspondant par defaut escale + overrides shipper/recipient,
- pas de doublons,
- message de coordination listant autres correspondants.

```python
def test_resolver_returns_union_default_and_overrides(self):
    resolved = resolve_correspondents(...)
    self.assertEqual({c.id for c in resolved}, {default.id, dedicated.id})
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.shipment.tests_correspondent_routing -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

Ajouter modeles:
- `DestinationCorrespondentDefault`
- `DestinationCorrespondentOverride`

Implementer service `resolve_correspondent_organizations(...)` avec union.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.shipment.tests_correspondent_routing -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/portal.py wms/correspondent_routing.py wms/tests/shipment/tests_correspondent_routing.py
git commit -m "feat(correspondent): add default and override routing with union resolution"
```

### Task 4: Ajouter matrice role/evenement et subscriptions filtrables

**Files:**
- Modify: `wms/models_domain/portal.py`
- Create: `wms/notification_policy.py`
- Create: `wms/tests/emailing/tests_notification_policy.py`

**Step 1: Write the failing test**

Couvrir:
- `RoleEventPolicy` globale,
- `ContactSubscription` filtres AND,
- fallback sur principal si aucun abonne,
- dedup par email/evenement.

```python
def test_notify_uses_fallback_primary_when_no_subscription(self):
    recipients = resolve_notification_recipients(...)
    self.assertEqual(recipients, ["primary@example.org"])
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.emailing.tests_notification_policy -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

Ajouter modeles:
- `RoleEventType` (enum),
- `RoleEventPolicy`,
- `ContactSubscription`.

Ajouter service `resolve_notification_recipients(...)`.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.emailing.tests_notification_policy -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/portal.py wms/notification_policy.py wms/tests/emailing/tests_notification_policy.py
git commit -m "feat(notification): add role policy, subscriptions, fallback and dedup"
```

### Task 5: Ajouter conformite documentaire et override temporaire

**Files:**
- Modify: `wms/models_domain/portal.py`
- Create: `wms/compliance.py`
- Create: `wms/tests/portal/tests_document_compliance.py`

**Step 1: Write the failing test**

Couvrir:
- checklist documentaire configurable,
- blocage strict operations si non conforme,
- override temporaire obligatoire (`expires_at` + `reason`),
- rappels J-3/J-1.

```python
def test_override_requires_expiration_and_reason(self):
    with self.assertRaises(ValidationError):
        ComplianceOverride(..., expires_at=None).full_clean()
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_document_compliance -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

Ajouter modeles:
- `DocumentRequirementTemplate`
- `OrganizationRoleDocument`
- `ComplianceOverride`

Ajouter services:
- `is_role_compliant(...)`
- `can_bypass_with_override(...)`.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_document_compliance -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/portal.py wms/compliance.py wms/tests/portal/tests_document_compliance.py
git commit -m "feat(compliance): add document requirements and temporary compliance overrides"
```

### Task 6: Migrer les flux portail SHIPPER/RECIPIENT en mode revue ASF

**Files:**
- Modify: `wms/views_portal_account.py`
- Modify: `wms/views_portal_orders.py`
- Modify: `wms/portal_order_handlers.py`
- Modify: `wms/view_permissions.py`
- Create: `wms/tests/portal/tests_portal_role_review_gate.py`

**Step 1: Write the failing test**

Couvrir:
- creation expediteur -> statut `PENDING_REVIEW`,
- creation destinataire -> actif mais review + docs obligatoires,
- blocage usage commandes/expeditions si revue/doc incomplets.

```python
def test_shipper_pending_review_blocks_order_creation(self):
    response = self.client.post(...)
    self.assertContains(response, "review pending", status_code=200)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_portal_role_review_gate -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

Ajouter gate metier centralisee dans `view_permissions.py` + appels depuis vues portail.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.portal.tests_portal_role_review_gate -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_portal_account.py wms/views_portal_orders.py wms/portal_order_handlers.py wms/view_permissions.py wms/tests/portal/tests_portal_role_review_gate.py
git commit -m "feat(portal): enforce ASF review and compliance gates for shipper and recipient flows"
```

### Task 7: Ajouter runtime flags de bascule et seuil de revue

**Files:**
- Modify: `wms/models_domain/integration.py`
- Modify: `wms/runtime_settings.py`
- Modify: `wms/admin.py`
- Create: `wms/tests/core/tests_runtime_role_migration_flags.py`

**Step 1: Write the failing test**

Ajouter tests pour:
- `org_roles_engine_enabled`,
- `legacy_contact_write_enabled`,
- `org_roles_review_max_open_percent` (default 20),
- lecture via `get_runtime_config()`.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_runtime_role_migration_flags -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

Ajouter champs runtime + mapping dataclass runtime config + edition admin.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.core.tests_runtime_role_migration_flags -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/models_domain/integration.py wms/runtime_settings.py wms/admin.py wms/tests/core/tests_runtime_role_migration_flags.py
git commit -m "feat(runtime): add org role migration feature flags and review threshold setting"
```

### Task 8: Implementer backfill legacy -> nouveau modele + queue de revue

**Files:**
- Create: `wms/management/commands/migrate_contacts_to_org_roles.py`
- Create: `wms/organization_roles_backfill.py`
- Create: `wms/tests/management/tests_management_migrate_contacts_to_org_roles.py`

**Step 1: Write the failing test**

Couvrir:
- mapping depuis `Contact`/`linked_shippers`/`destinations`,
- aucun binding global cree,
- cas ambigus envoyes en queue de revue,
- migration non bloquante.

```python
def test_backfill_routes_ambiguous_recipient_to_review_queue(self):
    call_command("migrate_contacts_to_org_roles")
    self.assertEqual(MigrationReviewItem.objects.count(), 1)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.management.tests_management_migrate_contacts_to_org_roles -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

Implementer service de backfill idempotent + commande management avec rapport final.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.management.tests_management_migrate_contacts_to_org_roles -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/management/commands/migrate_contacts_to_org_roles.py wms/organization_roles_backfill.py wms/tests/management/tests_management_migrate_contacts_to_org_roles.py
git commit -m "feat(migration): add non-blocking backfill from legacy contacts to org role models"
```

### Task 9: Creer ecran admin de revue migration (validation manuelle)

**Files:**
- Create: `wms/admin_organization_roles_review.py`
- Modify: `wms/admin.py`
- Create: `templates/admin/wms/organization_roles_review.html`
- Create: `wms/tests/admin/tests_admin_organization_roles_review.py`

**Step 1: Write the failing test**

Couvrir:
- acces admin ASF,
- liste cas a revoir,
- suggestions auto pre-remplies (historique + matching),
- action de validation manuelle qui cree bindings finaux.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_organization_roles_review -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

Ajouter vue admin personnalisee + template + actions valider/rejeter/attribuer.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.admin.tests_admin_organization_roles_review -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/admin_organization_roles_review.py wms/admin.py templates/admin/wms/organization_roles_review.html wms/tests/admin/tests_admin_organization_roles_review.py
git commit -m "feat(admin): add organization role migration review dashboard"
```

### Task 10: Geler les ecritures legacy et brancher les nouveaux resolvers metier

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/order_scan_handlers.py`
- Modify: `wms/domain/orders.py`
- Modify: `wms/scan_shipment_handlers.py`
- Modify: `wms/views_portal_orders.py`
- Modify: `wms/public_order_helpers.py`
- Create: `wms/tests/domain/tests_domain_orders_org_roles.py`
- Create: `wms/tests/forms/tests_forms_org_roles_gate.py`

**Step 1: Write the failing test**

Couvrir:
- blocage creation/edition legacy quand `legacy_contact_write_enabled=False`,
- selection expediteur/destinataire issue des nouveaux bindings,
- blocage usage destinataire non revu/non conforme.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.domain.tests_domain_orders_org_roles wms.tests.forms.tests_forms_org_roles_gate -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

Introduire facade de resolution:
- `resolve_shipper_for_operation(...)`
- `resolve_recipient_binding_for_operation(...)`

et brancher les flux creation commande/expedition.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.domain.tests_domain_orders_org_roles wms.tests.forms.tests_forms_org_roles_gate -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/forms.py wms/order_scan_handlers.py wms/domain/orders.py wms/scan_shipment_handlers.py wms/views_portal_orders.py wms/public_order_helpers.py wms/tests/domain/tests_domain_orders_org_roles.py wms/tests/forms/tests_forms_org_roles_gate.py
git commit -m "feat(flow): route order and shipment flows through organization role engine"
```

### Task 11: Integrer notifications et coordination correspondants dans signaux

**Files:**
- Modify: `wms/signals.py`
- Modify: `wms/emailing.py` (si utilitaire dedup central)
- Create: `wms/tests/emailing/tests_signals_org_role_notifications.py`

**Step 1: Write the failing test**

Couvrir:
- matrice role/evenement appliquee,
- fallback principal,
- dedup un envoi par email/evenement,
- inclusion message "autres correspondants impliques" sur chaque event notifie.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.emailing.tests_signals_org_role_notifications -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

Remplacer resolution legacy des destinataires d'email par le service notification policy.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.emailing.tests_signals_org_role_notifications -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/signals.py wms/emailing.py wms/tests/emailing/tests_signals_org_role_notifications.py
git commit -m "feat(notification): wire shipment and order notifications to role-based policy engine"
```

### Task 12: Verification complete and rollout checklist

**Files:**
- Modify: `docs/plans/2026-03-04-organization-roles-contact-governance-rollout-checklist.md`
- Modify if needed after test fixes

**Step 1: Run targeted suites**

Run:
- `./.venv/bin/python manage.py test wms.tests.portal.tests_organization_roles_models -v 2`
- `./.venv/bin/python manage.py test wms.tests.portal.tests_recipient_binding_models -v 2`
- `./.venv/bin/python manage.py test wms.tests.shipment.tests_correspondent_routing -v 2`
- `./.venv/bin/python manage.py test wms.tests.emailing.tests_notification_policy -v 2`
- `./.venv/bin/python manage.py test wms.tests.management.tests_management_migrate_contacts_to_org_roles -v 2`

Expected: PASS.

**Step 2: Run integration suites**

Run:
- `./.venv/bin/python manage.py test wms.tests.portal wms.tests.domain.tests_domain_orders_extra wms.tests.forms.tests_forms -v 2`

Expected: PASS or documented unrelated failures.

**Step 3: Dry-run migration and review metrics**

Run:
- `./.venv/bin/python manage.py migrate_contacts_to_org_roles --dry-run`
- `./.venv/bin/python manage.py migrate_contacts_to_org_roles --report-json /tmp/org-role-report.json`

Expected:
- migration non bloquante,
- `% active recipients pending review <= runtime threshold` ou blocage de bascule.

**Step 4: Summarize evidence**

Documenter:
- commandes executees,
- preuves de dedup notifications,
- volume de revue restant,
- decision de bascule feature flag.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-04-organization-roles-contact-governance-rollout-checklist.md
git commit -m "docs(rollout): add org role migration verification and rollout checklist"
```
