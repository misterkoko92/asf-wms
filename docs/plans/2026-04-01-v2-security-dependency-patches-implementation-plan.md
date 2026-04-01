# V2 Security Dependency Patches Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the current V2 dependency advisories by bumping `pypdf` and `cryptography` with the smallest possible dependency drift.

**Architecture:** Keep `pyproject.toml` plus `uv.lock` as the source of truth, apply a narrow direct pin update for `pypdf`, refresh the lock for both packages, then regenerate `requirements*.txt` from that lock and rerun the PDF/export-focused checks. Avoid any unrelated dependency movement.

**Tech Stack:** Python 3.11, uv, requirements export workflow, Django planning/print tests, pip-audit

---

### Task 1: Update the direct dependency pin

**Files:**
- Modify: `pyproject.toml`

**Step 1: Update the runtime dependency**

- change `pypdf==6.9.1` to `pypdf==6.9.2`

**Step 2: Save only that direct pin change**

- do not manually edit the lock or exported requirements

### Task 2: Refresh the lock and exports

**Files:**
- Modify: `uv.lock`
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt` only if the export changes it

**Step 1: Refresh the lock with targeted upgrades**

Run:

```bash
uv lock --upgrade-package pypdf --upgrade-package cryptography
```

**Step 2: Re-export compatibility requirements**

Run:

```bash
make export-requirements
```

**Step 3: Inspect the dependency diff**

Confirm:

- `pypdf==6.9.2`
- `cryptography==46.0.6`
- no unrelated broad churn

### Task 3: Verify PDF/export safety

**Files:**
- Test: `wms/tests/planning/tests_outputs.py`
- Test: `wms/tests/planning/tests_communication_actions.py`
- Test: `wms/tests/views/tests_views_planning.py`
- Test: `wms/tests/print/tests_print_pack_pdf.py`

**Step 1: Run the focused test slice**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.planning.tests_outputs \
  wms.tests.planning.tests_communication_actions \
  wms.tests.views.tests_views_planning \
  wms.tests.print.tests_print_pack_pdf \
  -v 2
```

**Step 2: Run lint if any generated/exported file required follow-up formatting**

Run:

```bash
uv run ruff check pyproject.toml
```

### Task 4: Reconfirm the advisory closure

**Files:**
- Modify only if needed: `docs/release_checklist.md`

**Step 1: Run the soft audit path**

Run:

```bash
make audit-soft
```

**Step 2: Check that the previous `cryptography` and `pypdf` advisories are gone**

If new advisories remain, document them explicitly before merging.

### Task 5: Commit and update PR follow-up

**Files:**
- Stage only the dependency and optional doc changes from this lot

**Step 1: Commit**

```bash
git add pyproject.toml uv.lock requirements.txt requirements-dev.txt
git commit -m "build: patch v2 pdf security dependencies"
```

**Step 2: Update the open V2 PR**

- mention the follow-up dependency patch
- mention focused validation and audit status
