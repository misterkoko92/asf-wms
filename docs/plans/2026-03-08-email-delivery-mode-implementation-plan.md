# Email Delivery Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Permettre a PythonAnywhere d'envoyer tous les emails applicatifs en direct sans dependre de la queue mail, tout en conservant le comportement actuel par defaut ailleurs.

**Architecture:** Introduire un reglage `EMAIL_DELIVERY_MODE` dans `settings` et centraliser la decision de transport dans `wms/emailing.py`. En mode `direct_only`, `enqueue_email_safe(...)` delegue a `send_email_safe(...)`; en mode `direct_or_queue`, il garde la creation d'`IntegrationEvent`.

**Tech Stack:** Django 4.2, settings via env vars, tests Django `manage.py test`, templates/env PythonAnywhere.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:systematic-debugging`, `@superpowers:verification-before-completion`, `@superpowers:using-git-worktrees`.

### Task 1: Documenter le design et preparer la baseline

**Files:**
- Create: `docs/plans/2026-03-08-email-delivery-mode-design.md`
- Create: `docs/plans/2026-03-08-email-delivery-mode-implementation-plan.md`

**Step 1: Save the validated design**

Rediger les deux documents de reference avec:
- le probleme PythonAnywhere
- les deux modes `direct_or_queue` et `direct_only`
- le risque assume en `direct_only`

**Step 2: Verify current baseline**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.emailing.tests_emailing wms.tests.emailing.tests_volunteer_email_flows -v 2`

Expected: PASS avant changement.

**Step 3: Commit**

```bash
git add docs/plans/2026-03-08-email-delivery-mode-design.md docs/plans/2026-03-08-email-delivery-mode-implementation-plan.md
git commit -m "docs: add email delivery mode design and plan"
```

### Task 2: Ajouter les tests du nouveau mode

**Files:**
- Modify: `wms/tests/emailing/tests_emailing.py`

**Step 1: Write the failing tests**

Ajouter des tests pour couvrir:
- `enqueue_email_safe(...)` en `direct_only` envoie en direct et ne cree pas d'evenement
- `enqueue_email_safe(...)` en `direct_only` retourne `False` si `send_email_safe(...)` echoue
- `enqueue_email_safe(...)` en mode invalide retombe sur le comportement queue

Exemple:

```python
@override_settings(EMAIL_DELIVERY_MODE="direct_only")
@mock.patch("wms.emailing.send_email_safe", return_value=True)
def test_enqueue_email_safe_sends_directly_in_direct_only_mode(self, send_email_mock):
    queued = enqueue_email_safe(
        subject="Subject",
        message="Body",
        recipient=["dest@example.com"],
    )
    self.assertTrue(queued)
    self.assertEqual(IntegrationEvent.objects.count(), 0)
    send_email_mock.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.emailing.tests_emailing -v 2`

Expected: FAIL because `enqueue_email_safe(...)` still always creates queue events.

**Step 3: Commit**

```bash
git add wms/tests/emailing/tests_emailing.py
git commit -m "test(email): cover configurable delivery mode"
```

### Task 3: Implementer `EMAIL_DELIVERY_MODE`

**Files:**
- Modify: `asf_wms/settings.py`
- Modify: `wms/emailing.py`

**Step 1: Add the setting**

Dans `settings.py`, ajouter:

```python
EMAIL_DELIVERY_MODE = (
    os.environ.get("EMAIL_DELIVERY_MODE", "direct_or_queue").strip().lower()
    or "direct_or_queue"
)
```

**Step 2: Implement the mode switch**

Dans `wms/emailing.py`:
- ajouter les constantes `EMAIL_DELIVERY_MODE_DIRECT_OR_QUEUE` et `EMAIL_DELIVERY_MODE_DIRECT_ONLY`
- ajouter un helper de resolution de mode
- adapter `enqueue_email_safe(...)` pour deleguer a `send_email_safe(...)` en `direct_only`

**Step 3: Run tests to verify they pass**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.emailing.tests_emailing -v 2`
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.emailing.tests_volunteer_email_flows -v 2`

Expected: PASS.

**Step 4: Commit**

```bash
git add asf_wms/settings.py wms/emailing.py
git commit -m "feat(email): add configurable delivery mode"
```

### Task 4: Mettre a jour la doc et les templates PythonAnywhere

**Files:**
- Modify: `deploy/pythonanywhere/asf-wms.env.template`
- Modify: `deploy/pythonanywhere/asf-wms.messmed.env.template`
- Modify: `docs/pythonanywhere_email_setup_step_by_step.md`
- Modify: `docs/operations.md`

**Step 1: Update deployment docs**

Documenter:
- `EMAIL_DELIVERY_MODE='direct_only'` pour PythonAnywhere
- l'absence de besoin de Scheduler email dans ce mode
- le trade-off: pas de retention en queue si echec direct

**Step 2: Run targeted verification**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.emailing.tests_emailing wms.tests.emailing.tests_volunteer_email_flows -v 2`
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python -m ruff check asf_wms/settings.py wms/emailing.py wms/tests/emailing/tests_emailing.py`

Expected: PASS / clean.

**Step 3: Commit**

```bash
git add deploy/pythonanywhere/asf-wms.env.template deploy/pythonanywhere/asf-wms.messmed.env.template docs/pythonanywhere_email_setup_step_by_step.md docs/operations.md
git commit -m "docs(email): document direct delivery mode for pythonanywhere"
```
