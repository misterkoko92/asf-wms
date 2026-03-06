# Python Tooling Standardization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Standardiser le tooling Python du repo legacy Django pour gagner en maintenabilite, securite et reproductibilite, sans casser le gate actuel ni toucher au scope Next/React en pause.

**Architecture:** Faire de `pyproject.toml` + `uv.lock` la source canonique de dependances et de configuration outillage, tout en gardant `requirements.txt` et `requirements-dev.txt` comme artefacts exportes de transition pour le deploiement et les environnements existants. Conserver `mypy` comme type checker bloquant, garder `pyright` en signal secondaire, et ajouter seulement les garde-fous a fort ROI: `djlint`, `detect-secrets`, `Dependabot`, et des hooks `pre-commit` plus complets.

**Tech Stack:** Django 4.2 LTS, Python 3.11/3.12, GitHub Actions, `uv`, `ruff`, `mypy`, `pyright`, `pre-commit`, `bandit`, `pip-audit`, `djlint`, `detect-secrets`.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`, `@superpowers:systematic-debugging`, `@superpowers:requesting-code-review`.

Scope guardrails:
- Legacy Django only.
- Do not touch `frontend-next/`, `wms/views_next_frontend.py`, `wms/ui_mode.py`, or `wms/tests/views/tests_views_next_frontend.py`.
- Keep rollout incremental: one coherent PR per task.

### Task 1: Creer la source canonique de dependances et de config projet

**Files:**
- Create: `pyproject.toml`
- Create: `uv.lock`
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt`
- Modify: `Makefile`
- Modify: `README.md`

**Step 1: Capture the current baseline**

Run:
```bash
make lint
make fmt-check
make typecheck
make typecheck-pyright
make test
make audit-soft
```

Expected: noter les commandes rouges avant migration; ne pas commencer la standardisation sans connaitre le bruit de base.

**Step 2: Write minimal project metadata and dependency groups**

Ajouter un `pyproject.toml` minimal avec:

```toml
[project]
name = "asf-wms"
version = "0.0.0"
requires-python = ">=3.11,<3.13"
dependencies = [
  # recopier exactement les dependances runtime de requirements.txt
]

[dependency-groups]
dev = [
  # recopier exactement les dependances de requirements-dev.txt
]
```

Ne pas deplacer `mypy.ini` ni `pyrightconfig.json` dans ce meme PR. Standardiser d'abord le packaging et Ruff.

**Step 3: Generate the lockfile and export compatibility requirements**

Run:
```bash
uv lock
uv export --no-hashes --format requirements-txt > requirements.txt
uv export --no-hashes --format requirements-txt --group dev > requirements-dev.txt
```

Expected: `uv.lock` versionne et `requirements*.txt` regeneres a partir du lockfile.

**Step 4: Make uv the default local install path while keeping a pip fallback**

Modifier `Makefile` et `README.md` pour que la voie recommandee devienne:

```bash
uv sync --frozen
```

Conserver une voie de secours documentee:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

**Step 5: Run verification**

Run:
```bash
uv sync --frozen
make lint
make fmt-check
make typecheck
make test
```

Expected: meme niveau de signal qu'avant migration, sans drift entre lockfile et requirements exportes.

**Step 6: Commit**

```bash
git add pyproject.toml uv.lock requirements.txt requirements-dev.txt Makefile README.md
git commit -m "build: standardize Python project metadata and uv lock workflow"
```

### Task 2: Unifier le lint et le formatage autour de Ruff

**Files:**
- Delete: `.ruff.toml`
- Modify: `pyproject.toml`
- Modify: `Makefile`
- Modify: `.pre-commit-config.yaml`
- Modify: `.github/workflows/ci.yml`

**Step 1: Snapshot current Ruff behavior**

Run:
```bash
make lint
make fmt-check
```

Expected: disposer d'un point de comparaison avant de deplacer la config.

**Step 2: Move Ruff config into pyproject and widen rules carefully**

Copier la config existante dans `pyproject.toml` puis elargir prudemment:

```toml
[tool.ruff]
target-version = "py311"
line-length = 100
extend-exclude = [
  ".venv",
  "frontend-next",
  "wms/migrations",
  "contacts/migrations",
  "wms/views_next_frontend.py",
  "wms/ui_mode.py",
  "wms/tests/views/tests_views_next_frontend.py",
]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

Si une nouvelle famille de regles cree trop de bruit, ajouter des `per-file-ignores` cibles. Ne pas revenir a une config globale permissive.

**Step 3: Add Ruff format to pre-commit**

Dans `.pre-commit-config.yaml`, garder `ruff` et ajouter `ruff-format` sur le meme scope Python legacy.

**Step 4: Remove the legacy Ruff config file**

Supprimer `.ruff.toml` une fois que `pyproject.toml` produit exactement le meme comportement de base.

**Step 5: Run verification**

Run:
```bash
make fmt
make lint
make fmt-check
pre-commit run ruff --all-files
pre-commit run ruff-format --all-files
```

Expected: zero diff apres `make fmt`, et CI capable d'echouer proprement sur un oubli de formatage.

**Step 6: Commit**

```bash
git add pyproject.toml .pre-commit-config.yaml .github/workflows/ci.yml Makefile
git add -u .ruff.toml
git commit -m "style: consolidate lint and formatting on Ruff"
```

### Task 3: Stabiliser le gate de type checking sans churn inutile

**Files:**
- Modify: `requirements-dev.txt`
- Modify: `mypy.ini`
- Modify: `pyrightconfig.json`
- Modify: `Makefile`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`

**Step 1: Capture the current type-checker outputs**

Run:
```bash
make typecheck
make typecheck-pyright
```

Expected: distinguer le vrai signal metier des ecarts de framework ou de configuration.

**Step 2: Keep mypy authoritative and pyright secondary**

Conserver:
- `make typecheck` bloque en local et en CI,
- `make typecheck-pyright` en mode shadow dans un premier temps,
- le meme perimetre de modules critiques dans `mypy.ini` et `pyrightconfig.json`.

Ne pas remplacer `mypy` par `pyright` dans cette vague.

**Step 3: Improve Django typing only if it reduces noise**

Si les ecarts viennent surtout de Django, ajouter les stubs Django dans `requirements-dev.txt` puis configurer `mypy`:

```ini
[mypy]
plugins = mypy_django_plugin.main

[mypy.plugins.django-stubs]
django_settings_module = asf_wms.settings
```

Ne garder cette etape que si elle diminue le bruit. Si elle augmente le nombre de faux positifs, la sortir du scope et la replanifier.

**Step 4: Tighten Pyright only after local cleanup**

Ne passer `pyrightconfig.json` de `basic` a `standard` qu'apres nettoyage local et seulement si la sortie reste exploitable en review.

**Step 5: Run verification**

Run:
```bash
make typecheck
make typecheck-pyright
```

Expected: `mypy` reste vert et `pyright` apporte du signal utile sans devenir un nouveau centre de bruit.

**Step 6: Commit**

```bash
git add requirements-dev.txt mypy.ini pyrightconfig.json Makefile .github/workflows/ci.yml README.md
git commit -m "typecheck: keep mypy as gate and tune pyright rollout"
```

### Task 4: Renforcer les garde-fous locaux avec pre-commit, templates et secrets

**Files:**
- Create: `.secrets.baseline`
- Modify: `.pre-commit-config.yaml`
- Modify: `README.md`

**Step 1: Expand pre-commit hooks with high-ROI checks**

Ajouter:
- `check-toml`
- `check-json`
- `check-added-large-files`
- `ruff-format`
- `djlint` pour `templates/**/*.html`
- `detect-secrets` avec baseline versionnee

Garder les hooks existants `ruff`, `bandit`, `check-yaml`, `check-merge-conflict`, `end-of-file-fixer`, `trailing-whitespace`.

**Step 2: Create the secret baseline**

Run:
```bash
detect-secrets scan > .secrets.baseline
```

Puis brancher le hook avec:

```bash
detect-secrets-hook --baseline .secrets.baseline
```

Expected: les secrets historiques legitimes sont baselines une fois, les nouveaux secrets cassent le commit.

**Step 3: Run the full local hygiene suite**

Run:
```bash
pre-commit run --all-files
```

Expected: sortir avec une liste finie de corrections locales sur templates, whitespace, conflits et secrets.

**Step 4: Fix or explicitly baseline findings**

Corriger les vrais problemes. Si un faux positif subsiste, le documenter uniquement via la baseline; ne pas desactiver tout le scanner.

**Step 5: Commit**

```bash
git add .pre-commit-config.yaml .secrets.baseline README.md
git commit -m "chore: harden local quality and secret scanning hooks"
```

### Task 5: Durcir la CI et automatiser les mises a jour de dependances

**Files:**
- Create: `.github/dependabot.yml`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`

**Step 1: Add Dependabot for Python and GitHub Actions**

Creer `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

Expected: PRs regulieres et petites pour dependances Python et actions GitHub.

**Step 2: Add a dedicated pre-commit job to CI**

Dans `.github/workflows/ci.yml`, ajouter un job rapide:

```yaml
precommit:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.11"
    - run: python -m pip install pre-commit
    - run: pre-commit run --all-files --show-diff-on-failure
```

Laisser le job de tests actuel pour `check`, Django, `mypy`, couverture et `pip-audit`.

**Step 3: Switch the main CI install path to uv once Task 1 is green**

Remplacer dans `ci.yml`:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

par:

```bash
python -m pip install uv
uv sync --frozen
```

Ne faire ce switch qu'apres au moins un run local vert de `uv sync --frozen`.

**Step 4: Keep security checks layered but low-noise**

Conserver:
- `bandit`
- `pip-audit`
- `manage.py check --deploy`

Reporter `CodeQL` ou d'autres scanners plus lourds a une vague 2, apres stabilisation des checks precedents.

**Step 5: Run verification**

Run:
```bash
pre-commit run --all-files
make ci
```

Expected: CI verte avec le meme gate metier qu'avant, plus un job hygiene rapide qui detecte templates, secrets et formatage.

**Step 6: Commit**

```bash
git add .github/dependabot.yml .github/workflows/ci.yml README.md
git commit -m "ci: add dependency automation and pre-commit gate"
```

### Task 6: Documenter le rollout, la maintenance et le rollback

**Files:**
- Modify: `README.md`
- Modify: `docs/operations.md`
- Modify: `docs/release_checklist.md`
- Modify: `docs/plans/2026-03-06-python-tooling-modernization-ruff-uv-pyright.md`

**Step 1: Update developer documentation**

Documenter clairement:
- `uv sync --frozen` comme setup par defaut,
- `make pre-commit` avant push,
- `make ci` comme gate de verification global,
- `make typecheck` bloquant et `make typecheck-pyright` informatif.

**Step 2: Write rollback procedures**

Ajouter des procedures simples:
- revenir temporairement a `pip install -r requirements*.txt`,
- regenerer `requirements*.txt` depuis `uv.lock`,
- desactiver un hook `pre-commit` individuellement si un faux positif bloque la prod,
- garder `mypy` comme gate meme si `pyright` est bruyant.

**Step 3: Define success metrics**

Noter explicitement:
- 0 secret introduit en review,
- 0 diff de formatage oublie en CI,
- 0 drift lockfile/requirements,
- 4 semaines de CI verte avant toute discussion de remplacement de `mypy`.

**Step 4: Link the modernization narrative**

Mettre a jour le plan existant `2026-03-06-python-tooling-modernization-ruff-uv-pyright.md` pour indiquer que ce document devient le plan d'execution detaille.

**Step 5: Commit**

```bash
git add README.md docs/operations.md docs/release_checklist.md docs/plans/2026-03-06-python-tooling-modernization-ruff-uv-pyright.md
git commit -m "docs: document standardized Python tooling rollout and rollback"
```

## Recommended PR order

1. Task 1 only
2. Task 2 only
3. Task 3 only
4. Task 4 only
5. Task 5 and Task 6 together

## Deferred tools (not in first wave)

- `actionlint`: utile pour les workflows GitHub Actions, mais a ajouter seulement apres stabilisation du job `pre-commit`.
- `CodeQL`: utile, mais a ajouter seulement apres stabilisation des checks actuels.
- `semgrep`: probable bruit excessif a ce stade.
- `pytest` migration: pas necessaire tant que `manage.py test` + couverture repond au besoin.
- remplacement complet de `mypy` par `pyright`: explicitement hors scope de cette vague.
