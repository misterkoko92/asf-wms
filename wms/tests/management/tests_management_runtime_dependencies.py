import tomllib
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class RuntimeDependencyExportsTests(SimpleTestCase):
    def test_pyproject_runtime_dependencies_include_defusedxml(self):
        pyproject_path = Path(settings.BASE_DIR) / "pyproject.toml"
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

        self.assertIn(
            "defusedxml==0.7.1",
            pyproject["project"]["dependencies"],
            "Runtime dependency defusedxml must be declared in pyproject.toml.",
        )

    def test_requirements_txt_includes_defusedxml(self):
        requirements_path = Path(settings.BASE_DIR) / "requirements.txt"
        requirements = requirements_path.read_text(encoding="utf-8").splitlines()

        self.assertIn(
            "defusedxml==0.7.1",
            requirements,
            "Deployment requirements.txt must include defusedxml.",
        )
