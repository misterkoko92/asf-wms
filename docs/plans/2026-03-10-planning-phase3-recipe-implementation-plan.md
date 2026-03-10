# Planning Phase 3 Recipe Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Formaliser puis executer une recette operateur reelle du module planning en deux paliers, base isolee puis PythonAnywhere reel, afin de statuer sur son readiness d'exploitation.

**Architecture:** Produire d'abord les artefacts de recette versionnes: protocole operateur, grille d'observation, note de resultat isolee et note de resultat PythonAnywhere. N'ajouter un outillage minimal que si un frottement reel de recette le justifie. Executer ensuite le protocole sur une semaine reelle choisie, d'abord hors risque, puis sur la vraie base sans diffusion effective.

**Tech Stack:** Documentation Markdown versionnee dans `docs/plans/`, eventuel outillage Django minimal si necessaire, verification via commandes `manage.py`, execution manuelle encadree sur environnement cible.

---

### Task 1: Poser le protocole de recette operateur

**Files:**
- Create: `docs/plans/2026-03-10-planning-phase3-recipe-runbook.md`
- Modify: `docs/plans/2026-03-08-planning-module-verification.md`
- Test: `docs/plans/2026-03-10-planning-phase3-recipe-design.md`

**Step 1: Write the failing checklist**

Define the sections the runbook must contain:
- prerequis
- choix de la semaine
- palier A base isolee
- palier B PythonAnywhere reel
- garde-fous
- checkpoints de validation
- conclusion et classification de readiness

Expected gap before writing:
- no dedicated phase 3 runbook exists yet

**Step 2: Verify the gap**

Run:
```bash
rg -n "phase3|phase 3|runbook|recette operateur" docs/plans
```

Expected:
- no existing document fully covers the planned two-stage recipe workflow

**Step 3: Write the minimal implementation**

- Create `docs/plans/2026-03-10-planning-phase3-recipe-runbook.md`.
- Keep it action-oriented and operator-readable.
- Update `docs/plans/2026-03-08-planning-module-verification.md` to reference the phase 3 runbook once it exists.

**Step 4: Verify the runbook exists and is coherent**

Run:
```bash
sed -n '1,260p' docs/plans/2026-03-10-planning-phase3-recipe-runbook.md
```

Expected:
- clear operator sequence
- both paliers present
- explicit decision section at the end

**Step 5: Commit**

```bash
git add docs/plans/2026-03-10-planning-phase3-recipe-runbook.md docs/plans/2026-03-08-planning-module-verification.md
git commit -m "docs(planning): add phase 3 recipe runbook"
```

### Task 2: Poser la grille d'observation et les notes de resultat

**Files:**
- Create: `docs/plans/2026-03-10-planning-phase3-recipe-observation-grid.md`
- Create: `docs/plans/2026-03-10-planning-phase3-isolated-result.md`
- Create: `docs/plans/2026-03-10-planning-phase3-pythonanywhere-result.md`
- Test: `docs/plans/2026-03-10-planning-phase3-recipe-runbook.md`

**Step 1: Write the failing checklist**

Define the required fields:
- semaine cible
- environnement
- sequence executee
- observations
- ecarts
- contournements
- decision

Expected gap before writing:
- no standard result sheet exists for the two recipe stages

**Step 2: Verify the gap**

Run:
```bash
rg -n "observation|decision|pret pour usage|pret avec reserves|pas encore pret" docs/plans
```

Expected:
- no dedicated reusable phase 3 result note structure exists

**Step 3: Write the minimal implementation**

- Create a compact observation grid markdown file.
- Create two result-note templates:
  - one for isolated run
  - one for PythonAnywhere real run
- Keep them mostly empty but structured for execution.

**Step 4: Verify the files are usable**

Run:
```bash
sed -n '1,240p' docs/plans/2026-03-10-planning-phase3-recipe-observation-grid.md
sed -n '1,260p' docs/plans/2026-03-10-planning-phase3-isolated-result.md
sed -n '1,260p' docs/plans/2026-03-10-planning-phase3-pythonanywhere-result.md
```

Expected:
- each file is concrete enough to execute without inventing structure during the recipe

**Step 5: Commit**

```bash
git add docs/plans/2026-03-10-planning-phase3-recipe-observation-grid.md docs/plans/2026-03-10-planning-phase3-isolated-result.md docs/plans/2026-03-10-planning-phase3-pythonanywhere-result.md
git commit -m "docs(planning): add phase 3 recipe result templates"
```

### Task 3: Evaluer le besoin d'outillage minimal avant execution

**Files:**
- Modify: `docs/plans/2026-03-10-planning-phase3-recipe-runbook.md`
- Optionally create: exact file only if a real blocker is identified
- Test: manual verification of runbook against current planning commands/views

**Step 1: Write the failing checklist**

List the minimum actions the current product must already support for the runbook:
- create run
- generate planning
- publish version
- generate drafts
- clone to v2
- export workbook
- inspect cockpit

Expected gap:
- any missing or awkward action discovered while mapping the runbook to current commands/UI

**Step 2: Verify the current surface**

Run:
```bash
rg -n "planning_run_|planning_version_|generate_version_drafts|export_version_workbook|publish_version|clone_version" wms
```

Expected:
- current code paths identified
- decision possible on whether extra tooling is truly needed

**Step 3: Write the minimal implementation**

- If no blocker exists, update the runbook to state that no extra tooling is required for the first execution.
- If one blocker exists, add only the smallest possible helper and document it.

**Step 4: Verify the conclusion**

Run:
```bash
git diff -- docs/plans/2026-03-10-planning-phase3-recipe-runbook.md wms
```

Expected:
- either docs-only clarification
- or one minimal, justified helper

**Step 5: Commit**

```bash
git add docs/plans/2026-03-10-planning-phase3-recipe-runbook.md wms
git commit -m "docs(planning): finalize phase 3 recipe execution path"
```

### Task 4: Executer le palier A sur base isolee et consigner le resultat

**Files:**
- Modify: `docs/plans/2026-03-10-planning-phase3-isolated-result.md`
- Optionally modify: `docs/plans/2026-03-10-planning-phase3-recipe-observation-grid.md`
- Test: current planning workflow on isolated environment

**Step 1: Prepare the execution**

Choose and record:
- the target week
- data source mode
- operator account used
- any prerequisite setup

**Step 2: Execute the runbook on isolated data**

Perform the documented sequence:
- create run
- generate planning
- review v1
- make manual adjustments
- publish v1
- generate drafts
- clone v2
- modify/publish/regenerate
- export workbook

**Step 3: Record the actual observations**

In `docs/plans/2026-03-10-planning-phase3-isolated-result.md`, document:
- what worked directly
- what was awkward
- what blocked
- whether palier B can proceed

**Step 4: Verify the result note is decision-ready**

Expected:
- explicit verdict for isolated stage
- actionable list of follow-ups if any

**Step 5: Commit**

```bash
git add docs/plans/2026-03-10-planning-phase3-isolated-result.md docs/plans/2026-03-10-planning-phase3-recipe-observation-grid.md
git commit -m "docs(planning): record isolated phase 3 recipe result"
```

### Task 5: Executer le palier B sur PythonAnywhere reel et conclure

**Files:**
- Modify: `docs/plans/2026-03-10-planning-phase3-pythonanywhere-result.md`
- Modify: `docs/plans/2026-03-10-planning-phase3-recipe-observation-grid.md`
- Modify: `docs/plans/2026-03-08-planning-module-verification.md`
- Test: real operator recipe on PythonAnywhere without actual diffusion

**Step 1: Prepare the guarded execution**

Record before execution:
- week used
- exact environment/date
- no-send/no-diffusion rule
- rollback or caution notes if relevant

**Step 2: Execute the real recipe**

Replay the same protocol on PythonAnywhere:
- run generation
- cockpit review
- v1 publication
- drafts generation
- v2 diff check
- workbook export

**Step 3: Record the real outcome**

Update `docs/plans/2026-03-10-planning-phase3-pythonanywhere-result.md` with:
- evidence
- blockers
- reserves
- final readiness decision

**Step 4: Update the master verification note**

- Add a short summary in `docs/plans/2026-03-08-planning-module-verification.md` pointing to the two phase 3 result notes and the readiness conclusion.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-10-planning-phase3-pythonanywhere-result.md docs/plans/2026-03-10-planning-phase3-recipe-observation-grid.md docs/plans/2026-03-08-planning-module-verification.md
git commit -m "docs(planning): record phase 3 real recipe decision"
```
