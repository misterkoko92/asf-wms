# Migration Bootstrap (Scan UI) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Moderniser l'interface Scan avec Bootstrap 5 sans réécriture Next/React, en migrant d'abord `Vue stock` et `Préparation expédition` avec un rollout progressif et réversible.

**Architecture:** Adopter Bootstrap en mode incrémental sur le frontend Django actuel, activation via feature flag, conservation des hooks existants (`id`, `data-*`, classes `scan-*`) pour préserver `scan.js` et les workflows métier. Les templates pilotes sont migrés vers des composants Bootstrap (`card`, `form`, `table-responsive`, `btn`) pendant que la logique Python reste inchangée.

**Tech Stack:** Django templates, Django staticfiles, Bootstrap 5.3 (CSS/JS bundle), `wms/static/scan/scan.css`, `wms/static/scan/scan.js`, Django TestCase.

---

## Execution tracking (2026-02-27)

- Status global: `IN_PROGRESS` (phase scan avancée, rollout doc prêt, lot suivant = migration hors scan).
- Branch: `codex/bootstrap-migration-scan`.
- Commits réalisés:
  - `990b706` `feat(scan): bootstrap migration checkpoint`
  - `e57da00` `style(scan): polish bootstrap visual language`
- Adaptation validée vs plan initial:
  - Task 2 exécutée en mode CDN conditionnel (`bootstrap@5.3.3` via jsDelivr) au lieu d’assets locaux versionnés.
  - Raison: simplifier le rollout/rollback et éviter l’embarquement binaire Bootstrap dans le repo.
- Avancement des tâches:
  - [x] Task 1
  - [x] Task 2 (variante CDN)
  - [x] Task 3
  - [x] Task 4
  - [x] Task 5
  - [x] Task 6
  - [x] Task 7
- Suivi lot suivant (portal): `docs/plans/2026-02-27-bootstrap-portal-lot2.md`.
- Suivi lot public complémentaire: `docs/plans/2026-02-27-bootstrap-public-lot3.md`.
- Suivi lot admin complémentaire: `docs/plans/2026-02-27-bootstrap-admin-lot4.md`.
- Suivi lot app fallback complémentaire: `docs/plans/2026-02-27-bootstrap-app-lot5.md`.
- Suivi lot print preview complémentaire: `docs/plans/2026-02-27-bootstrap-print-lot6.md`.
- Suivi lot scan public final complémentaire: `docs/plans/2026-02-27-bootstrap-scan-public-lot7.md`.
- Suivi lot foundations design complémentaire: `docs/plans/2026-02-27-design-foundations-lot8.md`.

---

### Task 1: Ajouter un feature flag de migration Bootstrap

**Files:**
- Modify: `asf_wms/settings.py`
- Modify: `wms/context_processors.py`
- Modify: `.env.example`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Créer `ScanBootstrapUiTests` avec un test qui attend `scan_bootstrap_enabled=True` dans le contexte d'une page scan quand le setting est actif.

```python
@override_settings(SCAN_BOOTSTRAP_ENABLED=True)
def test_scan_context_exposes_bootstrap_flag(self):
    response = self.client.get(reverse("scan:scan_stock"))
    self.assertTrue(response.context["scan_bootstrap_enabled"])
```

**Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_context_exposes_bootstrap_flag -v 2
```

Expected: FAIL (`KeyError` / flag missing).

**Step 3: Write minimal implementation**

- Ajouter dans `asf_wms/settings.py`:
```python
SCAN_BOOTSTRAP_ENABLED = _env_bool("SCAN_BOOTSTRAP_ENABLED", False)
```
- Exposer la valeur dans `wms/context_processors.py`:
```python
from django.conf import settings

def ui_mode_context(request):
    ...
    return {
        ...
        "scan_bootstrap_enabled": getattr(settings, "SCAN_BOOTSTRAP_ENABLED", False),
    }
```
- Documenter la variable dans `.env.example`.

**Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_context_exposes_bootstrap_flag -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add asf_wms/settings.py wms/context_processors.py .env.example wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat(ui): add bootstrap rollout feature flag for scan templates"
```

### Task 2: Intégrer Bootstrap en assets statiques locaux

**Files:**
- Create: `wms/static/scan/vendor/bootstrap/bootstrap.min.css`
- Create: `wms/static/scan/vendor/bootstrap/bootstrap.bundle.min.js`
- Modify: `templates/scan/base.html`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Ajouter un test qui vérifie l'inclusion conditionnelle des assets Bootstrap quand `SCAN_BOOTSTRAP_ENABLED=True`.

```python
@override_settings(SCAN_BOOTSTRAP_ENABLED=True)
def test_scan_base_includes_bootstrap_assets_when_enabled(self):
    response = self.client.get(reverse("scan:scan_stock"))
    self.assertContains(response, "scan/vendor/bootstrap/bootstrap.min.css")
    self.assertContains(response, "scan/vendor/bootstrap/bootstrap.bundle.min.js")
```

**Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_base_includes_bootstrap_assets_when_enabled -v 2
```

Expected: FAIL (assets non référencés).

**Step 3: Write minimal implementation**

- Ajouter les fichiers Bootstrap minifiés dans `wms/static/scan/vendor/bootstrap/`.
- Mettre à jour `templates/scan/base.html`:
```django
{% if scan_bootstrap_enabled %}
  <link rel="stylesheet" href="{% static 'scan/vendor/bootstrap/bootstrap.min.css' %}">
{% endif %}
```
et avant `</body>`:
```django
{% if scan_bootstrap_enabled %}
  <script src="{% static 'scan/vendor/bootstrap/bootstrap.bundle.min.js' %}"></script>
{% endif %}
```

**Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_base_includes_bootstrap_assets_when_enabled -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add templates/scan/base.html wms/static/scan/vendor/bootstrap/bootstrap.min.css wms/static/scan/vendor/bootstrap/bootstrap.bundle.min.js wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat(ui): wire local bootstrap assets in scan base template"
```

### Task 3: Ajouter une couche de design tokens Bootstrap

**Files:**
- Create: `wms/static/scan/scan-bootstrap.css`
- Modify: `templates/scan/base.html`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Ajouter un test qui vérifie le chargement de `scan-bootstrap.css` quand le flag est actif.

```python
@override_settings(SCAN_BOOTSTRAP_ENABLED=True)
def test_scan_base_loads_bootstrap_bridge_css(self):
    response = self.client.get(reverse("scan:scan_stock"))
    self.assertContains(response, "scan/scan-bootstrap.css")
```

**Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_base_loads_bootstrap_bridge_css -v 2
```

Expected: FAIL.

**Step 3: Write minimal implementation**

Créer `scan-bootstrap.css` avec une base minimale:

```css
:root {
  --bs-body-font-family: var(--font-body);
  --bs-body-color: var(--ink);
  --bs-body-bg: var(--bg);
  --bs-primary: var(--accent);
  --bs-secondary: var(--accent-2);
  --bs-border-color: var(--border);
}

.scan-main .card {
  border-color: var(--border);
  box-shadow: 0 8px 20px var(--shadow);
}
```

Inclure ce fichier après Bootstrap dans `templates/scan/base.html` si le flag est actif.

**Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_base_loads_bootstrap_bridge_css -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/static/scan/scan-bootstrap.css templates/scan/base.html wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat(ui): add bootstrap token bridge stylesheet for scan"
```

### Task 4: Migrer `Vue stock` vers composants Bootstrap

**Files:**
- Modify: `templates/scan/stock.html`
- Modify: `wms/static/scan/scan-bootstrap.css`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views_scan_stock.py`

**Step 1: Write the failing test**

Ajouter des assertions HTML:

```python
@override_settings(SCAN_BOOTSTRAP_ENABLED=True)
def test_scan_stock_uses_bootstrap_layout_and_keeps_table_tools(self):
    response = self.client.get(reverse("scan:scan_stock"))
    self.assertContains(response, "class=\"row g-3\"")
    self.assertContains(response, "class=\"table table-sm")
    self.assertContains(response, "data-table-tools=\"1\"")
```

**Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_stock_uses_bootstrap_layout_and_keeps_table_tools -v 2
```

Expected: FAIL.

**Step 3: Write minimal implementation**

Refactor `templates/scan/stock.html`:
- formulaire filtres en `row g-3` + `col-*`,
- champs en `form-label`, `form-control`, `form-select`,
- actions en `btn btn-primary` / `btn btn-outline-secondary`,
- tableau en `table-responsive` + `table table-sm table-hover`,
- conserver classes/hook existants (`scan-table`, `data-table-tools="1"`).

Compléter `scan-bootstrap.css` pour aligner spacing/couleurs sur les tokens actuels.

**Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_stock_uses_bootstrap_layout_and_keeps_table_tools -v 2
.venv/bin/python manage.py test wms.tests.views.tests_views_scan_stock -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add templates/scan/stock.html wms/static/scan/scan-bootstrap.css wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat(ui): migrate scan stock page to bootstrap components"
```

### Task 5: Migrer `Préparation expédition` vers composants Bootstrap

**Files:**
- Modify: `templates/scan/shipment_create.html`
- Modify: `wms/static/scan/scan-bootstrap.css`
- Test: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`
- Test: `wms/tests/views/tests_views.py`

**Step 1: Write the failing test**

Ajouter un test de rendu avec invariants:

```python
@override_settings(SCAN_BOOTSTRAP_ENABLED=True)
def test_scan_shipment_create_uses_bootstrap_and_preserves_js_hooks(self):
    response = self.client.get(reverse("scan:scan_shipment_create"))
    self.assertContains(response, "id=\"shipment-form\"")
    self.assertContains(response, "id=\"shipment-lines\"")
    self.assertContains(response, "class=\"btn btn-primary")
    self.assertContains(response, "id=\"shipment-details-section\"")
```

**Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_shipment_create_uses_bootstrap_and_preserves_js_hooks -v 2
```

Expected: FAIL.

**Step 3: Write minimal implementation**

Refactor `templates/scan/shipment_create.html`:
- card/header/actions en layout Bootstrap,
- formulaires séquentiels avec `form-control`, `form-select`, `invalid-feedback` style,
- boutons principaux en `btn btn-primary` / secondaires en `btn btn-outline-*`,
- sections documents en `row` + `col` + `d-flex flex-wrap gap-*`,
- conserver tous les identifiants/classes attendus par `scan.js`.

Ajouter dans `scan-bootstrap.css` les ajustements ciblés pour `.shipment-lines`, `.scan-docs`, et mix classes `scan-*` + Bootstrap.

**Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_shipment_create_uses_bootstrap_and_preserves_js_hooks -v 2
.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2
.venv/bin/python manage.py test wms.tests.views.tests_views.ScanViewTests.test_scan_shipment_create_assigns_carton -v 2
.venv/bin/python manage.py test wms.tests.views.tests_views.ScanViewTests.test_scan_shipment_create_from_product -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add templates/scan/shipment_create.html wms/static/scan/scan-bootstrap.css wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "feat(ui): migrate shipment create page to bootstrap components"
```

### Task 6: Vérifier les régressions globales Scan

**Files:**
- Modify (if needed): `wms/static/scan/scan-bootstrap.css`
- Test: `wms/tests/views/tests_views.py`
- Test: `wms/tests/views/tests_views_scan_stock.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`

**Step 1: Write the failing test**

Ajouter une smoke assertion route-level sur présence du shell scan avec flag actif.

```python
@override_settings(SCAN_BOOTSTRAP_ENABLED=True)
def test_scan_routes_still_render_shell_with_bootstrap_enabled(self):
    response = self.client.get(reverse("scan:scan_dashboard"))
    self.assertContains(response, "class=\"scan-shell")
```

**Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2
```

Expected: FAIL sur un ou plusieurs templates non compatibles.

**Step 3: Write minimal implementation**

Corriger uniquement les conflits CSS bloquants dans `scan-bootstrap.css` (inputs, tables, boutons, nav), sans modifier la logique métier côté Python.

**Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2
.venv/bin/python manage.py test wms.tests.views.tests_views_scan_stock -v 2
.venv/bin/python manage.py test wms.tests.views.tests_views_scan_shipments -v 2
.venv/bin/python manage.py test wms.tests.views.tests_views.ScanViewTests.test_scan_internal_routes_require_staff -v 2
```

Expected: PASS.

**Step 5: Commit**

```bash
git add wms/static/scan/scan-bootstrap.css wms/tests/views/tests_scan_bootstrap_ui.py
git commit -m "test(ui): add scan bootstrap regression smoke checks"
```

### Task 7: Documenter rollout + déploiement PythonAnywhere

**Files:**
- Modify: `README.md`
- Modify: `docs/operations.md`

**Step 1: Write the failing test**

Vérifier que la variable de rollout n'est pas documentée:

```bash
rg -n "SCAN_BOOTSTRAP_ENABLED|bootstrap@5.3.3|scan-bootstrap.css" README.md docs/operations.md
```

Expected: pas de section dédiée.

**Step 2: Run test to verify it fails**

Confirmer l'absence des références.

**Step 3: Write minimal implementation**

Ajouter:
- dans `README.md`: variable `SCAN_BOOTSTRAP_ENABLED` + comportement attendu,
- dans `docs/operations.md`: séquence de rollout
  - activer flag en staging,
  - `python manage.py collectstatic --noinput`,
  - smoke `/scan/stock/` + `/scan/shipment/create/`,
  - activer prod + rollback simple (`SCAN_BOOTSTRAP_ENABLED=false`).

**Step 4: Run test to verify it passes**

Run:
```bash
rg -n "SCAN_BOOTSTRAP_ENABLED|bootstrap@5.3.3|scan-bootstrap.css" README.md docs/operations.md
```

Expected: références trouvées.

**Step 5: Commit**

```bash
git add README.md docs/operations.md
git commit -m "docs(ui): document bootstrap rollout and pythonanywhere deployment steps"
```

---

Plan complete and saved to `docs/plans/2026-02-26-bootstrap-migration-plan.md`. Two execution options:

1. Subagent-Driven (this session) - I dispatch fresh subagent per task, review between tasks, fast iteration
2. Parallel Session (separate) - Open new session with executing-plans, batch execution with checkpoints

Which approach?
