from __future__ import annotations

from tools.planning_comm_helper.versioning import HELPER_VERSION

MINIMUM_HELPER_VERSION = HELPER_VERSION
LATEST_HELPER_VERSION = HELPER_VERSION


def build_helper_version_policy() -> dict[str, str]:
    return {
        "minimum_helper_version": MINIMUM_HELPER_VERSION,
        "latest_helper_version": LATEST_HELPER_VERSION,
    }
