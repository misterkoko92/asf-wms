# Scan Import Selectors Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ajouter des sélecteurs dynamiques sur la page legacy `scan/import` pour réutiliser les données existantes, autoriser la saisie libre, auto-remplir les champs liés et corriger l’alignement des radios de gestion du stock produit.

**Architecture:** Le backend enrichit le contexte de `templates/scan/imports.html` avec des jeux de données sérialisés pour produits, catégories, emplacements, entrepôts, contacts, destinations, utilisateurs et tags. Le template référence un composant JS/CSS dédié qui transforme certains `input` en champs autocomplétés à recherche "contient", tout en laissant intacte la soumission texte libre vers les importeurs existants.

**Tech Stack:** Django templates, vues/handlers legacy scan, JavaScript vanilla, CSS scan legacy, tests Django `TestCase`.

---

### Task 1: Encadrer le contrat serveur des sélecteurs

**Files:**
- Modify: `wms/tests/scan/tests_scan_import_handlers.py`
- Modify: `wms/tests/views/tests_views_imports.py`

**Step 1: Write the failing test**

Ajouter un test unitaire sur `render_scan_import` qui exige une clé `import_selector_data` contenant au moins les sections `products`, `locations`, `warehouses`, `categories`, `contacts`, `destinations`, `users`, `product_tags`, `contact_tags`.

Ajouter un test vue qui exige dans le HTML de `/scan/import/`:
- le `json_script` des données de sélecteurs
- les assets JS/CSS dédiés
- le markup Bootstrap des radios de stock (`form-check`)

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test wms.tests.scan.tests_scan_import_handlers wms.tests.views.tests_views_imports -v 2`
Expected: FAIL sur absence des nouvelles clés/contenus.

### Task 2: Construire les datasets de suggestion côté handler

**Files:**
- Modify: `wms/scan_import_handlers.py`

**Step 1: Write minimal implementation**

Créer des helpers privés qui sérialisent:
- produits avec identité, pricing, catégories, tags et emplacement par défaut
- catégories avec chemin L1..L4
- entrepôts avec `name`/`code`
- emplacements avec `warehouse`/`zone`/`aisle`/`shelf`/`rack_color`/`notes`
- contacts avec type, coordonnées, tags, destination et adresse effective
- destinations avec `city`/`iata_code`/`country`
- utilisateurs avec username, email, noms et flags

Injecter `import_selector_data` dans `render_scan_import`.

**Step 2: Run tests**

Run: `.venv/bin/python manage.py test wms.tests.scan.tests_scan_import_handlers wms.tests.views.tests_views_imports -v 2`
Expected: PASS

### Task 3: Brancher le template legacy

**Files:**
- Modify: `templates/scan/imports.html`

**Step 1: Write the failing test**

Étendre le test vue pour attendre:
- inclusion du CSS/JS de sélecteur
- `json_script`
- attributs/points d’ancrage sur les champs importés

**Step 2: Write minimal implementation**

Dans `imports.html`:
- ajouter `{% block extra_head %}` pour le CSS
- déposer `{{ import_selector_data|json_script:"scan-import-selector-data" }}`
- inclure le JS dédié en bas de page
- conserver les `input` existants pour que la saisie libre continue à créer de nouvelles entrées
- remplacer le bloc radio stock par un markup Bootstrap aligné

### Task 4: Implémenter le composant JS/CSS d’autocomplétion

**Files:**
- Create: `wms/static/scan/import_selectors.css`
- Create: `wms/static/scan/import_selectors.js`

**Step 1: Write minimal implementation**

Implémenter un composant vanilla qui:
- s’attache à une liste ciblée d’inputs
- filtre en "contient" de manière insensible à la casse
- affiche un menu de suggestions contextuelles
- laisse la valeur libre si aucune suggestion n’est choisie
- remplit automatiquement les champs liés lors d’une sélection
- gère aussi les champs tags multivaleurs séparés par `|`

### Task 5: Vérification

**Files:**
- Test: `wms/tests/scan/tests_scan_import_handlers.py`
- Test: `wms/tests/views/tests_views_imports.py`
- Optional visual smoke: `templates/scan/imports.html`

**Step 1: Run targeted tests**

Run: `.venv/bin/python manage.py test wms.tests.scan.tests_scan_import_handlers wms.tests.views.tests_views_imports wms.tests.views.tests_scan_bootstrap_ui -v 2`
Expected: PASS

**Step 2: Manual check**

Vérifier sur `/scan/import/`:
- recherche partielle `"on"` retourne des suggestions contenant la chaîne
- sélection d’un produit/contact/utilisateur complète les autres champs liés
- saisie d’une valeur absente reste soumise telle quelle
- les radios "Gestion du stock importé" sont alignés
