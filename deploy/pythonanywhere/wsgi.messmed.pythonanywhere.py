import os
import sys
from pathlib import Path

PROJECT_ROOT = "/home/messmed/asf-wms"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

ENV_FILE = os.environ.get(
    "ASF_WMS_ENV_FILE",
    "/home/messmed/.asf-wms.env",
)


def load_export_env_file(path: str) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    with env_path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :]
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key:
                os.environ[key] = value


load_export_env_file(ENV_FILE)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "asf_wms.settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
