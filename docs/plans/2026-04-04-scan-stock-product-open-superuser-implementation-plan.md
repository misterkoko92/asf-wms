# Scan Stock Product Open Superuser Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ajouter dans la vue stock un bouton `Ouvrir` par produit vers l'admin Django, visible uniquement pour les superusers.

**Architecture:** Le changement reste strictement dans le template de la vue stock. La permission s'appuie sur `request.user.is_superuser`, et l'edition continue de vivre dans `admin:wms_product_change`.

**Tech Stack:** Django templates, Django admin, `manage.py test`

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`.

### Task 1: Ecrire les tests de visibilite du bouton

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`
- Modify: `wms/tests/views/tests_views_scan_stock.py`

**Step 1: Write the failing test**

Ajouter:
- un test superuser qui verifie la colonne `Actions`, le libelle `Ouvrir`, et l'URL `admin:wms_product_change`
- un test staff standard qui verifie l'absence du bouton et de la colonne

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_stock_shows_product_open_action_for_superuser wms.tests.views.tests_views_scan_stock.ScanStockViewsTests.test_scan_stock_hides_product_open_action_for_non_superuser -v 2`
Expected: FAIL

**Step 3: Write minimal implementation**

Modifier `templates/scan/stock.html` pour rendre la colonne et le bouton uniquement pour les superusers.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_stock_shows_product_open_action_for_superuser wms.tests.views.tests_views_scan_stock.ScanStockViewsTests.test_scan_stock_hides_product_open_action_for_non_superuser -v 2`
Expected: PASS

### Task 2: Verifier les regressions proches

**Files:**
- Modify if needed after failures

**Step 1: Run targeted stock tests**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_stock wms.tests.views.tests_scan_bootstrap_ui -v 2`
Expected: PASS

**Step 2: Summarize evidence**

Document exact commands run and whether any adjacent failures remain.
