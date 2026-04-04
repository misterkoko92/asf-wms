from pathlib import Path

from django.test import SimpleTestCase


class V33RuntimeMapsTests(SimpleTestCase):
    def test_v33_runtime_maps_reference_parties_and_artifacts(self):
        base = Path(__file__).resolve().parents[3]
        parties_map = (
            base / "docs" / "plans" / "2026-04-02-v33-parties-runtime-map.md"
        ).read_text()
        artifacts_map = (
            base / "docs" / "plans" / "2026-04-02-v33-artifacts-runtime-map.md"
        ).read_text()

        self.assertIn("wms/parties/", parties_map)
        self.assertIn("wms/artifacts/", artifacts_map)
