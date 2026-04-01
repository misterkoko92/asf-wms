# V2 Security Dependency Patches Design

## Goal

Apply the smallest possible dependency update on top of ASF WMS V2 to remove the currently reported advisories on `cryptography` and `pypdf` without reopening broader runtime drift.

## Scope

- direct runtime dependency bump: `pypdf 6.9.1 -> 6.9.2`
- transitive runtime dependency bump in the lock/export set: `cryptography 46.0.5 -> 46.0.6`
- regenerate `uv.lock`, `requirements.txt`, and any compatibility exports derived from the lock
- revalidate the PDF/export-related surfaces most exposed to these packages

Out of scope:

- broad dependency refresh
- Django/runtime/tooling upgrades
- new product behavior
- translation or Next/React scope

## Recommended Approach

Use a narrow lock-refresh strategy:

1. update the direct dependency pin for `pypdf` in `pyproject.toml`
2. run a targeted lock refresh upgrading `pypdf` and `cryptography`
3. re-export compatibility requirements from the updated lock
4. run focused verification on print/export/planning PDF flows plus a quick audit confirmation

This keeps the change auditable and minimizes regression risk compared with a wider dependency refresh.

## Risk Notes

- `pypdf` is part of PDF handling, so print/export tests are the minimum safety net
- `cryptography` is transitive, so the key risk is lock/export drift rather than application code changes
- the repo already treats `pyproject.toml` and `uv.lock` as the canonical dependency sources; `requirements*.txt` must stay in sync

## Expected Artifacts

- `pyproject.toml`
- `uv.lock`
- `requirements.txt`
- any repo-reference or release-checklist note only if the follow-up status or operator guidance changes materially
