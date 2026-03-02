# Gestion Etiquette Produit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ajouter une page legacy scan `Gestion > Etiquette Produit` (superuser) pour imprimer etiquettes/QR a l'unite, sur selection ou sur tous les produits filtres, avec bouton `Imprimer les deux`.

**Architecture:** Factoriser la logique actuelle d'impression produit de l'admin dans un service partage, puis la reutiliser dans une nouvelle vue scan. La navigation `Gestion` pointe vers cette page et expose des liens vers l'editeur templates XLSX existant pour garder la modification des templates sans dupliquer l'outil.

**Tech Stack:** Django 4.2, templates Django, JS vanilla leger, ORM, tests `manage.py test`.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`, `@superpowers:systematic-debugging`, `@superpowers:requesting-code-review`.

### Task 1: Ajouter des tests en echec pour la nouvelle page Gestion > Etiquette Produit

**Files:**
- Modify: `wms/tests/views/tests_views_scan_admin.py`

**Step 1: Write the failing test**

Ajouter des tests pour:
- acces auth (anonyme redirect login, staff non-superuser 403, superuser 200),
- rendu boutons `Imprimer etiquettes`, `Imprimer QR`, `Imprimer les deux`,
- presence lien menu vers `scan_product_labels`.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin.ScanAdminViewTests.test_scan_admin_product_labels_page_renders_and_requires_superuser -v 2`
Expected: FAIL (route/vue inexistante).

**Step 3: Write minimal implementation**

Creer route/vue/template minimale renvoyant 200 pour superuser et integrer le lien menu.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2`
Expected: PASS des nouveaux tests de base.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_scan_admin.py wms/scan_urls.py wms/views.py wms/views_scan.py wms/views_scan_admin.py templates/scan/base.html templates/scan/admin_product_labels.html
git commit -m "feat(scan): add superuser product labels management page"
```

### Task 2: Ajouter des tests en echec pour les actions d'impression (selection, all_filtered, empty)

**Files:**
- Modify: `wms/tests/views/tests_views_scan_admin.py`

**Step 1: Write the failing test**

Ajouter des tests POST sur la nouvelle page:
- `print_labels` sur selection -> template labels,
- `print_qr` sur selection -> template QR,
- `selection` vide -> warning + redirect,
- `all_filtered` -> utilise tous les produits du filtre.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin.ScanAdminViewTests.test_scan_admin_product_labels_print_selection_actions -v 2`
Expected: FAIL (actions non implementees).

**Step 3: Write minimal implementation**

Implementer le parsing formulaire (mode selection/all_filtered + action) et la selection des produits.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2`
Expected: PASS des tests impression.

**Step 5: Commit**

```bash
git add wms/tests/views/tests_views_scan_admin.py wms/views_scan_admin.py templates/scan/admin_product_labels.html
git commit -m "feat(scan): add product labels print actions for selected or filtered products"
```

### Task 3: Factoriser la logique admin d'impression produit dans un service partage

**Files:**
- Create: `wms/product_label_printing.py`
- Modify: `wms/admin.py`
- Add tests: `wms/tests/views/tests_views_scan_admin.py` (assertions comportement) et/ou `wms/tests/print/tests_product_label_printing.py`

**Step 1: Write the failing test**

Ajouter un test qui verifie que la vue scan et l'action admin produisent les memes templates de rendu et gerent rack_color/QR manquants.

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2`
Expected: FAIL (service non partage / logique dupliquee).

**Step 3: Write minimal implementation**

Creer fonctions:
- `render_product_labels_response(request, products)`
- `render_product_qr_labels_response(request, products)`

Migrer `ProductAdmin.print_product_labels` et `ProductAdmin.print_product_qr_labels` vers ce service.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add wms/product_label_printing.py wms/admin.py wms/tests/views/tests_views_scan_admin.py
git commit -m "refactor(print): share product labels and qr rendering between admin and scan"
```

### Task 4: Finaliser UX page + bouton Imprimer les deux + liens templates

**Files:**
- Modify: `templates/scan/admin_product_labels.html`
- Modify: `wms/views_scan_admin.py`
- Modify: `templates/scan/base.html`
- Modify: `wms/tests/views/tests_views_scan_admin.py`

**Step 1: Write the failing test**

Ajouter tests de rendu:
- presence du mode `selection`/`all_filtered`,
- presence des liens `Gestion > Templates` et editions template produit,
- `print_both` expose les deux endpoints (liens/cibles distinctes).

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2`
Expected: FAIL (UI incomplete).

**Step 3: Write minimal implementation**

Completer template + formulaire + event JS minimal pour ouvrir les deux impressions.

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2`
Expected: PASS.

**Step 5: Commit**

```bash
git add templates/scan/admin_product_labels.html wms/views_scan_admin.py templates/scan/base.html wms/tests/views/tests_views_scan_admin.py
git commit -m "feat(scan): complete product label management ux with dual-print action"
```

### Task 5: Verification complete

**Files:**
- Modify if needed after fixes from verification

**Step 1: Run targeted tests**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_scan_admin -v 2`
Expected: PASS.

**Step 2: Run adjacent regression tests**

Run: `./.venv/bin/python manage.py test wms.tests.print.tests_print_context wms.tests.views.tests_views_print_templates -v 2`
Expected: PASS.

**Step 3: Run full quality checks used in repo (if needed)**

Run: `make test-next-ui` (or nearest existing CI subset if cheaper).
Expected: PASS or documented failures unrelated.

**Step 4: Summarize evidence**

Document exact commands run, what passed, and any skipped checks.

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(scan): add Gestion > Etiquette Produit with shared print logic"
```
