# Admin Contacts Org-Role Cockpit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remplacer `Admin > Contacts` par un cockpit metier org-role permettant de gerer roles, personnes, scopes et bindings sans dependre de l'admin Django au quotidien.

**Architecture:** Conserver la route `scan:scan_admin_contacts` et deplacer la logique metier dans un module dedie (`wms/scan_admin_contacts_cockpit.py`) + formulaires dedies (`wms/forms_scan_admin_contacts_cockpit.py`). La vue legacy devient un orchestrateur (GET read model + POST commands). Le template `templates/scan/admin_contacts.html` est remplace par une UI orientee actions metier avec panneaux par domaine.

**Tech Stack:** Django 4.2, ORM, templates Django, formulaires Django, tests `manage.py test`.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:systematic-debugging`, `@superpowers:verification-before-completion`, `@superpowers:requesting-code-review`.

### Task 1: Installer le squelette cockpit et les tests de rendu

**Files:**
- Create: `wms/scan_admin_contacts_cockpit.py`
- Modify: `wms/views_scan_admin.py`
- Modify: `templates/scan/admin_contacts.html`
- Create: `wms/tests/views/tests_views_scan_admin_contacts_cockpit.py`

**Step 1: Write the failing test**

Ajouter un test qui exige les marqueurs cockpit (sections + active tab):

```python
def test_scan_admin_contacts_renders_org_role_cockpit(self):
    self.client.force_login(self.superuser)
    response = self.client.get(reverse("scan:scan_admin_contacts"))
    self.assertContains(response, "Pilotage contacts org-role")
    self.assertContains(response, "Recherche et filtres")
    self.assertContains(response, "Actions metier")
    self.assertEqual(response.context["active"], "admin_contacts")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: FAIL (contenu cockpit absent).

**Step 3: Write minimal implementation**

- Ajouter dans `scan_admin_contacts` un contexte cockpit minimal via helper `build_cockpit_context(...)`.
- Remplacer le contenu du template par structure 4 blocs (filtres, tableau, actions, creation guidee).

```python
# wms/scan_admin_contacts_cockpit.py

def build_cockpit_context(*, query: str, filters: dict) -> dict:
    return {
        "query": query,
        "filters": filters,
        "rows": [],
        "mode": "cockpit",
    }
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/scan_admin_contacts_cockpit.py wms/views_scan_admin.py templates/scan/admin_contacts.html wms/tests/views/tests_views_scan_admin_contacts_cockpit.py
git commit -m "feat(scan): add admin contacts org-role cockpit skeleton"
```

### Task 2: Implementer les filtres cockpit et la table resultat

**Files:**
- Modify: `wms/scan_admin_contacts_cockpit.py`
- Modify: `templates/scan/admin_contacts.html`
- Modify: `wms/tests/views/tests_views_scan_admin_contacts_cockpit.py`

**Step 1: Write the failing test**

Ajouter les cas:
- filtre par role actif,
- filtre shipper -> destinataires,
- recherche par nom/ASF ID.

```python
def test_filter_shipper_recipient_returns_only_linked_recipients(self):
    response = self.client.get(reverse("scan:scan_admin_contacts"), {
        "role": "recipient",
        "shipper_org_id": str(self.shipper.id),
    })
    rows = response.context["cockpit_rows"]
    self.assertEqual([row["organization"].id for row in rows], [self.recipient.id])
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: FAIL (filtres non appliques).

**Step 3: Write minimal implementation**

- Ajouter `parse_cockpit_filters(request)`.
- Ajouter `build_cockpit_rows(...)` avec `OrganizationRoleAssignment`, `RecipientBinding`, `ShipperScope`.
- Hydrater colonnes: roles, primary email par role, nb recipients, scopes.

```python
rows_qs = Contact.objects.filter(contact_type=ContactType.ORGANIZATION, is_active=True)
if filters["role"]:
    rows_qs = rows_qs.filter(organization_role_assignments__role=filters["role"], organization_role_assignments__is_active=True)
if filters["shipper_org_id"]:
    rows_qs = rows_qs.filter(recipient_bindings_as_recipient__shipper_org_id=filters["shipper_org_id"], recipient_bindings_as_recipient__is_active=True)
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/scan_admin_contacts_cockpit.py templates/scan/admin_contacts.html wms/tests/views/tests_views_scan_admin_contacts_cockpit.py
git commit -m "feat(scan): add org-role cockpit filters and result rows"
```

### Task 3: Gerer activation/desactivation des roles organisation

**Files:**
- Modify: `wms/scan_admin_contacts_cockpit.py`
- Modify: `wms/views_scan_admin.py`
- Modify: `templates/scan/admin_contacts.html`
- Modify: `wms/tests/views/tests_views_scan_admin_contacts_cockpit.py`

**Step 1: Write the failing test**

Couvrir:
- activation role valide,
- rejet activation sans primary email,
- desactivation role.

```python
def test_assign_role_requires_primary_email_contact(self):
    response = self.client.post(reverse("scan:scan_admin_contacts"), {
        "action": "assign_role",
        "organization_id": str(self.org.id),
        "role": "shipper",
    }, follow=True)
    self.assertContains(response, "contact principal")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Ajouter commandes `assign_role`/`unassign_role`.
- `assign_role`: `get_or_create` puis `is_active=True` + `save()` (la validation modele impose primary email).
- Capturer `ValidationError` et remonter message UX.

```python
assignment, _ = OrganizationRoleAssignment.objects.get_or_create(...)
assignment.is_active = True
assignment.save()  # ValidationError si primary email manquant
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/scan_admin_contacts_cockpit.py wms/views_scan_admin.py templates/scan/admin_contacts.html wms/tests/views/tests_views_scan_admin_contacts_cockpit.py
git commit -m "feat(scan): add role activation and deactivation actions"
```

### Task 4: Gerer personnes organisation et liens role-contact

**Files:**
- Create: `wms/forms_scan_admin_contacts_cockpit.py`
- Modify: `wms/scan_admin_contacts_cockpit.py`
- Modify: `wms/views_scan_admin.py`
- Modify: `templates/scan/admin_contacts.html`
- Modify: `wms/tests/views/tests_views_scan_admin_contacts_cockpit.py`

**Step 1: Write the failing test**

Couvrir:
- creation `OrganizationContact`,
- liaison `OrganizationRoleContact`,
- bascule `is_primary`,
- contrainte meme organisation.

```python
def test_link_role_contact_rejects_contact_from_other_org(self):
    response = self.client.post(reverse("scan:scan_admin_contacts"), {
        "action": "link_role_contact",
        "role_assignment_id": str(self.assignment.id),
        "organization_contact_id": str(self.other_org_contact.id),
    }, follow=True)
    self.assertContains(response, "meme organisation")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Creer formulaires dedies pour chaque action panneau.
- Implementer:
1. `upsert_org_contact`
2. `link_role_contact`
3. `unlink_role_contact`
4. `set_primary_role_contact`

```python
role_contact, _ = OrganizationRoleContact.objects.get_or_create(...)
if set_primary:
    OrganizationRoleContact.objects.filter(role_assignment=assignment).update(is_primary=False)
    role_contact.is_primary = True
role_contact.save()
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/forms_scan_admin_contacts_cockpit.py wms/scan_admin_contacts_cockpit.py wms/views_scan_admin.py templates/scan/admin_contacts.html wms/tests/views/tests_views_scan_admin_contacts_cockpit.py
git commit -m "feat(scan): add organization contacts and role-contact linking"
```

### Task 5: Gerer scopes expediteur depuis le cockpit

**Files:**
- Modify: `wms/forms_scan_admin_contacts_cockpit.py`
- Modify: `wms/scan_admin_contacts_cockpit.py`
- Modify: `templates/scan/admin_contacts.html`
- Modify: `wms/tests/views/tests_views_scan_admin_contacts_cockpit.py`

**Step 1: Write the failing test**

Couvrir:
- creation scope global,
- creation scope destination,
- rejection XOR invalide,
- desactivation scope.

```python
def test_upsert_shipper_scope_requires_global_xor_destination(self):
    response = self.client.post(reverse("scan:scan_admin_contacts"), {
        "action": "upsert_shipper_scope",
        "role_assignment_id": str(self.shipper_assignment.id),
        "all_destinations": "1",
        "destination_id": str(self.destination.id),
    }, follow=True)
    self.assertContains(response, "soit")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Action `upsert_shipper_scope` et `disable_shipper_scope`.
- Utiliser validation modele `ShipperScope.clean()`.

```python
scope = ShipperScope(...)
scope.save()  # ValidationError geree dans la vue
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/forms_scan_admin_contacts_cockpit.py wms/scan_admin_contacts_cockpit.py templates/scan/admin_contacts.html wms/tests/views/tests_views_scan_admin_contacts_cockpit.py
git commit -m "feat(scan): add shipper scope management in cockpit"
```

### Task 6: Gerer bindings shipper-recipient-destination

**Files:**
- Modify: `wms/forms_scan_admin_contacts_cockpit.py`
- Modify: `wms/scan_admin_contacts_cockpit.py`
- Modify: `templates/scan/admin_contacts.html`
- Modify: `wms/tests/views/tests_views_scan_admin_contacts_cockpit.py`

**Step 1: Write the failing test**

Couvrir:
- creation binding actif,
- cloture binding (`valid_to`),
- rejection coherence temporelle,
- vue "destinataires d'un shipper".

```python
def test_close_recipient_binding_sets_valid_to_and_inactive(self):
    response = self.client.post(reverse("scan:scan_admin_contacts"), {
        "action": "close_recipient_binding",
        "binding_id": str(self.binding.id),
        "valid_to": "2030-01-01T10:00",
    }, follow=True)
    self.binding.refresh_from_db()
    self.assertFalse(self.binding.is_active)
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Actions `upsert_recipient_binding` / `close_recipient_binding`.
- Versioning simple: conserver historique en creant nouvelle version pour changement majeur.

```python
RecipientBinding.objects.create(
    shipper_org=shipper,
    recipient_org=recipient,
    destination=destination,
    is_active=True,
    valid_from=timezone.now(),
)
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/forms_scan_admin_contacts_cockpit.py wms/scan_admin_contacts_cockpit.py templates/scan/admin_contacts.html wms/tests/views/tests_views_scan_admin_contacts_cockpit.py
git commit -m "feat(scan): add recipient binding management in cockpit"
```

### Task 7: Ajouter la creation guidee contact/organisation

**Files:**
- Modify: `wms/forms_scan_admin_contacts_cockpit.py`
- Modify: `wms/scan_admin_contacts_cockpit.py`
- Modify: `templates/scan/admin_contacts.html`
- Modify: `wms/tests/views/tests_views_scan_admin_contacts_cockpit.py`

**Step 1: Write the failing test**

Couvrir:
- creation organisation + role immediate,
- creation personne + rattachement org,
- options conditionnelles scopes/bindings.

```python
def test_create_guided_person_links_to_existing_organization(self):
    response = self.client.post(reverse("scan:scan_admin_contacts"), {
        "action": "create_guided_contact",
        "entity_kind": "person",
        "organization_id": str(self.org.id),
        "first_name": "Aya",
        "last_name": "Diallo",
        "email": "aya@example.org",
    }, follow=True)
    self.assertTrue(Contact.objects.filter(first_name="Aya", organization=self.org).exists())
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Implementer formulaire guide + rendu conditionnel template.
- Action unique `create_guided_contact` qui delegue selon `entity_kind`.

```python
if entity_kind == "organization":
    contact = Contact.objects.create(contact_type=ContactType.ORGANIZATION, ...)
else:
    contact = Contact.objects.create(contact_type=ContactType.PERSON, organization=organization, ...)
```

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/forms_scan_admin_contacts_cockpit.py wms/scan_admin_contacts_cockpit.py templates/scan/admin_contacts.html wms/tests/views/tests_views_scan_admin_contacts_cockpit.py
git commit -m "feat(scan): add guided contact creation workflow"
```

### Task 8: Activer la sortie legacy via runtime flag et finaliser la non-regression

**Files:**
- Modify: `wms/views_scan_admin.py`
- Modify: `templates/scan/admin_contacts.html`
- Modify: `wms/tests/views/tests_views_scan_admin_contacts_cockpit.py`
- Modify: `wms/tests/views/tests_views_scan_admin.py`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Couvrir:
- masquage sections legacy quand `legacy_contact_write_enabled=False`,
- rejet explicite des actions legacy,
- conservation liens fallback admin Django.

```python
def test_legacy_actions_blocked_when_runtime_flag_disabled(self):
    runtime = WmsRuntimeSettings.load()
    runtime.legacy_contact_write_enabled = False
    runtime.save(update_fields=["legacy_contact_write_enabled"])
    response = self.client.post(reverse("scan:scan_admin_contacts"), {
        "action": "create_contact",
    }, follow=True)
    self.assertContains(response, "legacy desactive")
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit wms.tests.views.tests_views_scan_admin -v 2`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Brancher `is_legacy_contact_write_enabled()` dans la vue.
- Bloquer les actions legacy et afficher message.
- Conserver liens admin Django dans un panneau "Secours".

```python
if action in LEGACY_ACTIONS and not is_legacy_contact_write_enabled():
    messages.error(request, "Mode legacy desactive: utilisez les actions org-role.")
    return redirect(...)
```

**Step 4: Run test to verify it passes**

Run:
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2`
- `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/views_scan_admin.py templates/scan/admin_contacts.html wms/tests/views/tests_views_scan_admin_contacts_cockpit.py wms/tests/views/tests_views_scan_admin.py wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat(scan): gate legacy contact actions and finalize org-role cockpit"
```

### Task 9: Verification finale et handoff

**Files:**
- Modify: `docs/plans/2026-03-04-admin-contacts-cockpit-org-roles-design.md`
- Create: `docs/plans/2026-03-04-admin-contacts-cockpit-org-roles-verification.md`

**Step 1: Write the failing test**

Ajouter une checklist de verification executable (pas de code applicatif):

```text
- cockpit route loads
- role actions pass
- org contact links pass
- scope/binding flows pass
- legacy gate pass
```

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit -v 2`
Expected: FAIL tant que toutes taches 1-8 ne sont pas implementees.

**Step 3: Write minimal implementation**

Executer l'ensemble des suites ciblees et documenter les preuves dans le rapport.

```bash
./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin_contacts_cockpit wms.tests.views.tests_views_scan_admin wms.tests.views.tests_scan_bootstrap_ui -v 2
```

**Step 4: Run test to verify it passes**

Run: meme commande.
Expected: PASS.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-04-admin-contacts-cockpit-org-roles-design.md docs/plans/2026-03-04-admin-contacts-cockpit-org-roles-verification.md
git commit -m "docs(plan): add verification evidence for admin contacts cockpit rollout"
```
