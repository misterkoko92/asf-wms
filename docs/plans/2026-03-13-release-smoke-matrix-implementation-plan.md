# Release Smoke Matrix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** documenter une matrice smoke minimale qui sépare les garde-fous CI des checks post-deploy legacy Django.

**Architecture:** la mise en oeuvre reste documentaire. Elle met à jour la checklist de release et le runbook d'operations pour décrire un petit noyau de smoke CI déterministes et une matrice post-deploy courte avec des checks conditionnels par domaine.

**Tech Stack:** Markdown, documentation de release, runbook operations

---

### Task 1: Update Release Checklist Smoke Policy

**Files:**
- Modify: `docs/release_checklist.md`
- Test: `docs/release_checklist.md`

**Step 1: Add the CI smoke policy**

Ajouter dans la section "Before merge" une note qui limite les smoke CI aux chaînes critiques déterministes déjà utilisées comme garde-fous transverses.

**Step 2: Refine the post-deploy smoke checklist**

Réorganiser la section "After deploy" avec:

- un bloc `Always-on smoke`
- un bloc `Conditional smoke`
- une distinction explicite entre flux scan obligatoires et domaines optionnels (`portal`, `planning`, `billing`)

**Step 3: Review the updated section**

Run: `sed -n '1,200p' docs/release_checklist.md`
Expected: la section montre une matrice smoke courte, compréhensible, et non exhaustive.

**Step 4: Commit**

```bash
git add docs/release_checklist.md
git commit -m "docs: refine release smoke matrix"
```

### Task 2: Mirror the Smoke Policy in Operations Runbook

**Files:**
- Modify: `docs/operations.md`
- Test: `docs/operations.md`

**Step 1: Add a smoke scope policy note**

Documenter que les smoke ne doivent pas couvrir tous les flux utilisateur, mais seulement les chaînes nominales critiques.

**Step 2: Expand the post-deploy runbook**

Ajouter les vérifications `always-on` et `conditional` dans la section "Post-deploy smoke tests", cohérentes avec la release checklist.

**Step 3: Review the updated section**

Run: `sed -n '140,260p' docs/operations.md`
Expected: la politique smoke et la matrice post-deploy sont alignées avec la checklist de release.

**Step 4: Commit**

```bash
git add docs/operations.md
git commit -m "docs: document smoke policy in operations"
```

### Task 3: Validate Documentation Consistency

**Files:**
- Modify: `docs/plans/2026-03-13-release-smoke-matrix-design.md`
- Modify: `docs/plans/2026-03-13-release-smoke-matrix-implementation-plan.md`
- Test: `docs/release_checklist.md`
- Test: `docs/operations.md`

**Step 1: Save the design note and implementation plan**

Créer les deux notes sous `docs/plans/` pour laisser une trace explicite de la décision et de son exécution.

**Step 2: Run a whitespace and diff sanity check**

Run: `git diff --check`
Expected: aucune erreur d'espaces ou de format dans les fichiers Markdown modifiés.

**Step 3: Inspect the final diff**

Run: `git diff -- docs/release_checklist.md docs/operations.md docs/plans/2026-03-13-release-smoke-matrix-design.md docs/plans/2026-03-13-release-smoke-matrix-implementation-plan.md`
Expected: les changements sont purement documentaires et cohérents entre eux.

**Step 4: Commit**

```bash
git add docs/plans/2026-03-13-release-smoke-matrix-design.md docs/plans/2026-03-13-release-smoke-matrix-implementation-plan.md
git commit -m "docs: capture release smoke strategy"
```
