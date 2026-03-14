# Scan Navbar Tab Order Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reordonner les onglets de la navbar Scan legacy et appliquer une casse titre coherente sur les libelles de premier niveau, tout en conservant les onglets conditionnels a leur place lorsqu'ils sont visibles.

**Architecture:** Garder `templates/scan/base.html` comme source de verite de la navbar. Verrouiller le comportement par tests de rendu dans `wms/tests/views/tests_scan_bootstrap_ui.py` avant de modifier le template, puis ajuster l'ordre des blocs de navigation sans changer les routes ni les sous-menus.

**Tech Stack:** Django legacy, templates Django, tests `manage.py test`.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`.

### Task 1: Couvrir l'ordre des onglets pour les differents profils

**Files:**
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Write the failing test**

Ajouter un helper qui extrait le segment HTML de la navbar Scan, puis ecrire:

- un test pour l'ordre standard sans `Facturation` ni `Admin`;
- un test pour l'ordre d'un profil membre du groupe facturation;
- un test pour l'ordre complet d'un superuser.

Assertions attendues:

```python
expected_labels = [
    "Tableau De Bord",
    "Voir Les Etats",
    "Reception",
    "Preparation",
    "Planning",
    "Suivi Des Expeditions",
    "Gestion",
    "Compte",
]
```

Les assertions doivent verifier l'ordre relatif dans le HTML de la navbar, pas
seulement la presence des chaines.

**Step 2: Run test to verify it fails**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_nav_orders_top_level_tabs_for_standard_staff -v 2`
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_nav_orders_top_level_tabs_for_billing_staff -v 2`
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_nav_orders_top_level_tabs_for_superuser -v 2`

Expected: FAIL tant que le template conserve l'ancien ordre et les anciens
libelles.

### Task 2: Reordonner la navbar et appliquer la casse titre

**Files:**
- Modify: `templates/scan/base.html`

**Step 1: Write minimal implementation**

Reordonner les onglets de premier niveau pour obtenir:

- `Tableau De Bord`
- `Voir Les Etats`
- `Reception`
- `Preparation`
- `Planning`
- `Suivi Des Expeditions`
- `Facturation`
- `Gestion`
- `Admin`
- `Compte`

Details:

- conserver les conditions d'affichage existantes;
- conserver `Compte` en dernier;
- ne pas changer les items internes des dropdowns ni les URLs;
- conserver les accents dans le rendu utilisateur des libelles francais.

**Step 2: Run targeted tests**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests -v 2`

Expected: PASS sur les tests de navbar et absence de regression sur les autres
assertions UI de ce fichier.

### Task 3: Verification finale

**Files:**
- Modify: `templates/scan/base.html`
- Modify: `wms/tests/views/tests_scan_bootstrap_ui.py`

**Step 1: Run final verification**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.views.tests_scan_bootstrap_ui -v 2`

Expected: `OK` avec `0 failures`.

**Step 2: Review diff**

Verifier que le diff final ne touche que:

- la navbar top-level Scan legacy;
- la couverture de test associee;
- les documents `docs/plans` de ce changement.
