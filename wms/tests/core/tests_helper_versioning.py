from django.test import SimpleTestCase

from wms.helper_versioning import build_helper_version_policy


class HelperVersioningTests(SimpleTestCase):
    def test_build_helper_version_policy_uses_current_helper_contract(self):
        self.assertEqual(
            build_helper_version_policy(),
            {
                "minimum_helper_version": "0.1.2",
                "latest_helper_version": "0.1.2",
            },
        )
