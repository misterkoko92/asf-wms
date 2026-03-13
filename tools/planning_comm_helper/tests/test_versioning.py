from unittest import TestCase, mock

from tools.planning_comm_helper.versioning import (
    HELPER_CAPABILITIES,
    HELPER_VERSION,
    get_helper_runtime_metadata,
)


class PlanningCommunicationHelperVersioningTests(TestCase):
    @mock.patch("tools.planning_comm_helper.versioning.platform.system", return_value="Darwin")
    def test_get_helper_runtime_metadata_returns_version_platform_and_capabilities(
        self,
        _platform_mock,
    ):
        payload = get_helper_runtime_metadata()

        self.assertEqual(
            payload,
            {
                "helper_version": HELPER_VERSION,
                "platform": "Darwin",
                "capabilities": list(HELPER_CAPABILITIES),
            },
        )
