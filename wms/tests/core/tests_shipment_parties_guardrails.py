from pathlib import Path

from django.test import SimpleTestCase

REPO_ROOT = Path(__file__).resolve().parents[3]


class ShipmentPartiesGuardrailsTests(SimpleTestCase):
    def test_runtime_shipment_paths_no_longer_import_org_role_resolvers(self):
        forbidden_patterns_by_file = {
            "wms/domain/orders.py": [
                "organization_role_resolvers",
            ],
            "wms/order_scan_handlers.py": [
                "organization_role_resolvers",
            ],
        }

        violations = []
        for relative_path, patterns in forbidden_patterns_by_file.items():
            contents = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
            for pattern in patterns:
                if pattern in contents:
                    violations.append(f"{relative_path}: {pattern}")

        self.assertEqual(
            violations,
            [],
            "Shipment runtime files still import org-role resolvers:\n- " + "\n- ".join(violations),
        )

    def test_shipment_party_rules_resolve_runtime_validation_from_shipment_registry(self):
        contents = (REPO_ROOT / "wms/shipment_party_rules.py").read_text(encoding="utf-8")

        self.assertIn("eligible_shippers_for_stopover", contents)
        self.assertIn("eligible_recipient_organizations_for_shipper", contents)
        self.assertNotIn("OrganizationRoleAssignment", contents)
        self.assertNotIn("ShipperScope", contents)
        self.assertNotIn("RecipientBinding", contents)
