# Planning Flight API Provider Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ajouter un systeme de providers API de vols interchangeable dans `asf-wms`, avec Air France-KLM comme premier backend concret, tout en preservant l'import Excel et le fallback `HYBRID`.

**Architecture:** `wms/planning/flight_sources.py` reste l'orchestrateur des imports et de la persistance. Les integrations externes sont deplacees dans `wms/planning/flight_providers/`, avec une interface simple, un provider Air France-KLM concret, et une selection du provider par settings runtime.

**Tech Stack:** Django 4.2, ORM Django, `urllib.request`, tests Django `manage.py test`, import Excel existant `openpyxl`.

---

Skill refs during execution: `@superpowers:test-driven-development`, `@superpowers:systematic-debugging`, `@superpowers:verification-before-completion`, `@superpowers:requesting-code-review`, `@superpowers:using-git-worktrees`.

### Task 1: Poser le contrat provider et la configuration runtime

**Files:**
- Create: `wms/planning/flight_providers/__init__.py`
- Create: `wms/planning/flight_providers/base.py`
- Modify: `wms/runtime_settings.py`
- Modify: `wms/tests/planning/tests_flight_sources.py`

**Step 1: Write the failing test**

Ajouter un test de configuration qui exprime le contrat attendu.

```python
from django.test import SimpleTestCase, override_settings

from wms.runtime_settings import get_planning_flight_api_config


class PlanningFlightApiConfigTests(SimpleTestCase):
    @override_settings(
        PLANNING_FLIGHT_API_PROVIDER="airfrance_klm",
        PLANNING_FLIGHT_API_BASE_URL="https://example.test/flights",
        PLANNING_FLIGHT_API_KEY="test-api-key",  # pragma: allowlist secret
        PLANNING_FLIGHT_API_TIMEOUT_SECONDS=17,
        PLANNING_FLIGHT_API_ORIGIN_IATA="CDG",
        PLANNING_FLIGHT_API_AIRLINE_CODE="AF",
        PLANNING_FLIGHT_API_TIME_ORIGIN_TYPE="M",
    )
    def test_runtime_config_exposes_provider_specific_fields(self):
        config = get_planning_flight_api_config()
        assert config.provider == "airfrance_klm"
        assert config.origin_iata == "CDG"
        assert config.operating_airline_code == "AF"
        assert config.time_origin_type == "M"
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_flight_sources -v 2`
Expected: FAIL because the runtime config does not yet expose provider selection and provider-specific fields.

**Step 3: Write minimal implementation**

- Add `PlanningFlightProvider` and domain errors in `wms/planning/flight_providers/base.py`
- Extend `PlanningFlightApiConfig` in `wms/runtime_settings.py` with:
  - `provider`
  - `origin_iata`
  - `operating_airline_code`
  - `time_origin_type`
- Keep defaults conservative and ASCII-only

**Step 4: Run tests to verify it passes**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_flight_sources -v 2`

Expected: PASS with config fields available for the provider factory.

**Step 5: Commit**

```bash
git add wms/planning/flight_providers/__init__.py wms/planning/flight_providers/base.py wms/runtime_settings.py wms/tests/planning/tests_flight_sources.py
git commit -m "feat(planning): add flight provider base contract"
```

### Task 2: Implementer le provider Air France-KLM

**Files:**
- Create: `wms/planning/flight_providers/airfrance_klm.py`
- Modify: `wms/tests/planning/tests_flight_sources.py`
- Read: `/Users/EdouardGonnu/asf-wms/.worktrees/codex/planning-ortools-solver/wms/planning/flight_sources.py`

**Step 1: Write the failing test**

Ajouter un test qui verrouille la normalisation du payload Air France-KLM.

```python
def test_airfrance_provider_expands_multistop_payload(self):
    payload = {
        "operationalFlights": [
            {
                "route": ["CDG", "NKC", "CKY"],
                "airline": {"code": "AF"},
                "flightNumber": 1234,
            }
        ]
    }
    provider = AirFranceKlmFlightProvider(...)
    records = provider._extract_records(payload)
    assert [row["destination_iata"] for row in records] == ["NKC", "CKY"]
    assert [row["route_pos"] for row in records] == [1, 2]
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_flight_sources -v 2`
Expected: FAIL because the provider does not exist yet.

**Step 3: Write minimal implementation**

- Port only the concrete Air France-KLM logic needed from the old worktree:
  - URL building
  - request headers
  - JSON parsing
  - `404` => empty payload
  - route expansion
  - departure time extraction
- Keep the provider output normalized for `normalize_flight_record(...)`
- Raise explicit provider errors on malformed payloads or request failures

**Step 4: Run tests to verify it passes**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_flight_sources -v 2`

Expected: PASS with real provider behavior covered by unit tests.

**Step 5: Commit**

```bash
git add wms/planning/flight_providers/airfrance_klm.py wms/tests/planning/tests_flight_sources.py
git commit -m "feat(planning): add air france klm flight provider"
```

### Task 3: Raccorder l'orchestrateur `flight_sources` au provider interchangeable

**Files:**
- Modify: `wms/planning/flight_sources.py`
- Modify: `wms/tests/planning/tests_flight_sources.py`

**Step 1: Write the failing test**

Ajouter un test qui verrouille la resolution du provider configure.

```python
@override_settings(PLANNING_FLIGHT_API_PROVIDER="airfrance_klm")
def test_build_planning_flight_api_client_returns_configured_provider(self):
    client = build_planning_flight_api_client()
    self.assertIsInstance(client, AirFranceKlmFlightProvider)
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_flight_sources -v 2`
Expected: FAIL because the factory still returns the abstract placeholder client.

**Step 3: Write minimal implementation**

- Move the generic orchestration responsibilities into `wms/planning/flight_sources.py`
- Add provider factory selection based on `config.provider`
- Keep `import_api_flights(...)` and `collect_flight_batches(...)` signatures stable
- Preserve the existing Excel import path unchanged

**Step 4: Run tests to verify it passes**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_flight_sources -v 2`

Expected: PASS with provider resolution and existing Excel behavior intact.

**Step 5: Commit**

```bash
git add wms/planning/flight_sources.py wms/tests/planning/tests_flight_sources.py
git commit -m "feat(planning): resolve flight api providers from settings"
```

### Task 4: Implementer le fallback `HYBRID` et les erreurs explicites

**Files:**
- Modify: `wms/planning/flight_sources.py`
- Modify: `wms/tests/planning/tests_flight_sources.py`
- Modify: `docs/plans/2026-03-10-planning-flight-api-provider-design.md`

**Step 1: Write the failing test**

Ajouter deux tests de comportement:

```python
def test_collect_hybrid_flight_batches_keeps_excel_when_api_provider_fails(self):
    ...
    self.assertEqual([batch.source for batch in batches], ["excel"])

def test_collect_api_flight_batches_raises_when_provider_fails_without_excel(self):
    ...
    with self.assertRaises(PlanningFlightProviderError):
        collect_flight_batches(...)
```

**Step 2: Run test to verify it fails**

Run: `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_flight_sources -v 2`
Expected: FAIL because API failures are not yet handled differently between `API` and `HYBRID`.

**Step 3: Write minimal implementation**

- In `collect_flight_batches(...)`, handle provider errors explicitly:
  - `API`: re-raise
  - `HYBRID` with Excel batch: keep Excel only and trace the API failure in batch notes
- Keep behavior deterministic and easy to diagnose

**Step 4: Run tests to verify it passes**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_flight_sources -v 2`

Expected: PASS with fallback behavior covered.

**Step 5: Commit**

```bash
git add wms/planning/flight_sources.py wms/tests/planning/tests_flight_sources.py docs/plans/2026-03-10-planning-flight-api-provider-design.md
git commit -m "feat(planning): add hybrid fallback for flight api provider"
```

### Task 5: Verification finale et documentation de configuration

**Files:**
- Modify: `docs/plans/2026-03-10-planning-flight-api-provider-design.md`
- Optional modify: `docs/plans/2026-03-08-planning-module-verification.md`

**Step 1: Write the failing test**

Pas de nouveau test applicatif. Ecrire plutot une checklist de verification operateur a executer avec les tests existants.

**Step 2: Run verification commands**

Run:
- `/Users/EdouardGonnu/asf-wms/.venv/bin/python manage.py test wms.tests.planning.tests_flight_sources wms.tests.planning.tests_run_preparation wms.tests.views.tests_views_planning wms.tests.management.tests_management_makemigrations_check -v 1`
- `/Users/EdouardGonnu/asf-wms/.venv/bin/ruff check wms/planning wms/tests/planning wms/views_planning.py`

Expected: PASS, no migration drift, no lint regressions.

**Step 3: Write minimal documentation updates**

- Document required settings for the Air France-KLM provider
- Document `HYBRID` fallback behavior
- Document operator expectations when the API returns no flights or errors

**Step 4: Re-run the final checks if docs changed code references**

Run the same commands again only if code changed during verification.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-10-planning-flight-api-provider-design.md docs/plans/2026-03-08-planning-module-verification.md
git commit -m "docs(planning): document flight api provider rollout"
```
