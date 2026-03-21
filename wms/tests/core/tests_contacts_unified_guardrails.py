from pathlib import Path

from django.test import SimpleTestCase

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOTS = ("contacts", "wms", "templates")
FORBIDDEN_PATTERNS = (
    "OrganizationRoleAssignment",
    "OrganizationContact",
    "OrganizationRoleContact",
    "ShipperScope",
    "RecipientBinding",
    "organization_role_resolvers",
    "backfill_shipment_parties_from_org_roles",
)
ALLOWLIST_SUFFIXES = {
    "wms/tests/core/tests_contacts_unified_guardrails.py",
    "wms/tests/core/tests_shipment_parties_guardrails.py",
}
ALLOWLIST_PARTS = (
    "/migrations/",
    "/tests/",
)


class ContactsUnifiedGuardrailsTests(SimpleTestCase):
    def test_runtime_code_has_no_org_role_runtime_symbols(self):
        violations: list[str] = []

        for root_name in RUNTIME_ROOTS:
            root_path = REPO_ROOT / root_name
            if not root_path.exists():
                continue
            for path in root_path.rglob("*"):
                if not path.is_file():
                    continue
                relative_path = path.relative_to(REPO_ROOT).as_posix()
                if relative_path in ALLOWLIST_SUFFIXES:
                    continue
                if any(part in f"/{relative_path}" for part in ALLOWLIST_PARTS):
                    continue
                if path.suffix not in {".py", ".html", ".js", ".md"}:
                    continue
                contents = path.read_text(encoding="utf-8")
                for pattern in FORBIDDEN_PATTERNS:
                    if pattern in contents:
                        violations.append(f"{relative_path}: {pattern}")

        self.assertEqual(
            violations,
            [],
            "Runtime code still references org-role runtime symbols:\n- "
            + "\n- ".join(sorted(violations)),
        )

    def test_runtime_code_no_longer_contains_org_role_resolver_module(self):
        self.assertFalse(
            (REPO_ROOT / "wms/organization_role_resolvers.py").exists(),
            "Runtime still ships wms/organization_role_resolvers.py",
        )
