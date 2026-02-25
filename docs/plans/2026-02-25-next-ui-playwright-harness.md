# Next UI Playwright Harness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a real browser E2E harness for `/app/*` routes to start closing P2 migration test debt.

**Architecture:** Reuse the existing Python Playwright strategy already present in `wms/tests/core/tests_ui.py` (`StaticLiveServerTestCase` + authenticated session cookie injection). Add a dedicated Next test class focused on browser smoke interactions for scan and portal routes, gated by env flags to keep default CI stable. Update migration docs to reference the new harness and run command.

**Tech Stack:** Django test runner, Python Playwright (`playwright.sync_api`), StaticLiveServerTestCase, existing Next frontend served by Django under `/app/*`.

---

### Task 1: Add Next Browser E2E Tests

**Files:**
- Modify: `wms/tests/core/tests_ui.py`
- Test: `wms/tests/core/tests_ui.py`

**Step 1: Write the failing test**

Add `NextUiTests` with three browser scenarios:
- staff can open `/app/scan/dashboard/` and see Next shell heading,
- staff can trigger invalid Shipment ID validation on `/app/scan/shipment-documents/`,
- portal association user can open `/app/portal/dashboard/`.

**Step 2: Run test to verify it fails**

Run:
```bash
RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests.test_next_scan_dashboard_loads_for_staff
```

Expected: fail before implementation (class missing / test missing).

**Step 3: Write minimal implementation**

Implement `NextUiTests`:
- authenticated users + association profile fixture,
- helper to inject session cookie into Playwright context,
- browser assertions for heading, mode switch, and inline validation message.

**Step 4: Run test to verify it passes**

Run:
```bash
RUN_UI_TESTS=1 .venv/bin/python manage.py test wms.tests.core.tests_ui.NextUiTests
```

Expected:
- pass when Playwright/browser and live server socket are available,
- skip if env flag disabled or Playwright missing.

**Step 5: Commit**

```bash
git add wms/tests/core/tests_ui.py
git commit -m "test: add Playwright smoke harness for Next app routes"
```

### Task 2: Add Execution Entry Point

**Files:**
- Modify: `Makefile`
- Test: `Makefile` target resolution

**Step 1: Write the failing test**

Try to run a missing target:
```bash
make test-next-ui
```

Expected: `No rule to make target`.

**Step 2: Run test to verify it fails**

Confirm command fails as expected.

**Step 3: Write minimal implementation**

Add `test-next-ui` target:
```make
RUN_UI_TESTS=1 $(PYTHON) manage.py test wms.tests.core.tests_ui.NextUiTests
```

**Step 4: Run test to verify it passes**

Run:
```bash
make test-next-ui
```

Expected: command launches the dedicated Next UI browser suite.

**Step 5: Commit**

```bash
git add Makefile
git commit -m "build: add make target for Next Playwright UI tests"
```

### Task 3: Update Migration Documentation

**Files:**
- Modify: `docs/next-react-static-migration/03_matrice_parite_benev_classique.md`
- Modify: `docs/next-react-static-migration/p2_phase2_increment5_2026-02-23.md`

**Step 1: Write the failing test**

Search docs for explicit harness command and file reference:
```bash
rg -n "test-next-ui|NextUiTests|wms/tests/core/tests_ui.py" docs/next-react-static-migration
```

Expected: no dedicated reference.

**Step 2: Run test to verify it fails**

Confirm missing references.

**Step 3: Write minimal implementation**

Document that the browser harness exists and reference run command + test class.

**Step 4: Run test to verify it passes**

Re-run `rg` command and ensure references are found.

**Step 5: Commit**

```bash
git add docs/next-react-static-migration/03_matrice_parite_benev_classique.md docs/next-react-static-migration/p2_phase2_increment5_2026-02-23.md
git commit -m "docs: register Next Playwright browser harness in migration status"
```
