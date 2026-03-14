import base64
import io
import platform
import textwrap
import zipfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.core import signing
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse

from tools.planning_comm_helper.autostart import MACOS_APP_BUNDLE_NAME
from tools.planning_comm_helper.versioning import HELPER_VERSION

from .helper_versioning import build_helper_version_policy

HELPER_RUNTIME_REQUIREMENTS = """pypdf==6.7.5
pywin32>=306; platform_system == "Windows"
"""
HELPER_INSTALL_TOKEN_QUERY_PARAM = "installer_token"  # nosec B105
HELPER_INSTALL_TOKEN_SALT = "wms.helper_install"  # nosec B105
HELPER_INSTALL_TOKEN_MAX_AGE_SECONDS = 3600
HELPER_BUNDLE_FILES = (
    "tools/planning_comm_helper/__init__.py",
    "tools/planning_comm_helper/autostart.py",
    "tools/planning_comm_helper/excel_pdf.py",
    "tools/planning_comm_helper/outlook.py",
    "tools/planning_comm_helper/pdf_render.py",
    "tools/planning_comm_helper/planning_pdf.py",
    "tools/planning_comm_helper/server.py",
    "tools/planning_comm_helper/versioning.py",
    "tools/planning_comm_helper/whatsapp.py",
)


def _helper_repo_root():
    return Path(__file__).resolve().parent.parent


def _macos_installed_app_path() -> Path:
    return Path.home() / "Applications" / MACOS_APP_BUNDLE_NAME


def _absolute_install_url(*, install_url: str, request=None) -> str:
    if not install_url:
        return ""
    if request is None:
        return install_url
    return request.build_absolute_uri(install_url)


def _install_url_path(install_url: str) -> str:
    return urlsplit(install_url).path


def _signed_helper_install_token(*, install_url: str, app_label: str, system_name: str) -> str:
    return signing.dumps(
        {
            "app_label": app_label,
            "install_path": _install_url_path(install_url),
            "system": system_name,
        },
        salt=HELPER_INSTALL_TOKEN_SALT,
    )


def _append_query_param(url: str, *, name: str, value: str) -> str:
    if not url:
        return ""
    parsed = urlsplit(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.append((name, value))
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )


def _signed_install_url(
    *,
    install_url: str,
    app_label: str,
    system_name: str,
    request=None,
    absolute: bool = False,
) -> str:
    if not install_url or not system_name:
        return ""
    base_url = (
        _absolute_install_url(install_url=install_url, request=request) if absolute else install_url
    )
    token = _signed_helper_install_token(
        install_url=install_url,
        app_label=app_label,
        system_name=system_name,
    )
    return _append_query_param(
        base_url,
        name=HELPER_INSTALL_TOKEN_QUERY_PARAM,
        value=token,
    )


def _normalize_platform_hint(value):
    normalized = str(value or "").strip().strip('"').lower()
    if normalized in {"macos", "mac os", "darwin"}:
        return "Darwin"
    if normalized in {"windows", "win32"}:
        return "Windows"
    if normalized:
        return normalized.title()
    return ""


def _request_client_system(request):
    if request is None:
        return ""
    platform_hint = _normalize_platform_hint(
        getattr(request, "META", {}).get("HTTP_SEC_CH_UA_PLATFORM")
    )
    if platform_hint in {"Darwin", "Windows"}:
        return platform_hint

    user_agent = str(getattr(request, "META", {}).get("HTTP_USER_AGENT") or "").lower()
    if "windows" in user_agent:
        return "Windows"
    if "macintosh" in user_agent or "mac os x" in user_agent:
        return "Darwin"
    return ""


def _resolved_system(*, request=None, system=None):
    return _request_client_system(request) or system or platform.system()


def resolve_helper_installer_access(request, *, app_label: str):
    if request is None:
        return None
    raw_token = str(getattr(request, "GET", {}).get(HELPER_INSTALL_TOKEN_QUERY_PARAM) or "").strip()
    if not raw_token:
        return None
    try:
        payload = signing.loads(
            raw_token,
            salt=HELPER_INSTALL_TOKEN_SALT,
            max_age=HELPER_INSTALL_TOKEN_MAX_AGE_SECONDS,
        )
    except signing.BadSignature:
        return None
    expected_path = request.path
    install_path = str(payload.get("install_path") or "")
    signed_app_label = str(payload.get("app_label") or "")
    system_name = _normalize_platform_hint(payload.get("system"))
    if install_path != expected_path or signed_app_label != app_label:
        return None
    if system_name not in {"Darwin", "Windows"}:
        return None
    return {
        "app_label": signed_app_label,
        "install_path": install_path,
        "system": system_name,
    }


def _helper_bundle_archive(repo_root: Path | None = None) -> bytes:
    resolved_repo_root = Path(repo_root or _helper_repo_root())
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_path in HELPER_BUNDLE_FILES:
            source_path = resolved_repo_root / relative_path
            archive.writestr(relative_path, source_path.read_bytes())
        archive.writestr("requirements-helper.txt", HELPER_RUNTIME_REQUIREMENTS)
        archive.writestr("helper-version.txt", f"{HELPER_VERSION}\n")
    return buffer.getvalue()


def _helper_bundle_base64(repo_root: Path | None = None) -> str:
    return base64.b64encode(_helper_bundle_archive(repo_root)).decode("ascii")


def _wrapped_base64_lines(payload: str) -> str:
    return "\n".join(textwrap.wrap(payload, 88))


def _macos_install_command(install_url: str) -> str:
    return f'curl -fsSL "{install_url}" | zsh'


def _windows_install_command(install_url: str, *, app_label: str) -> str:
    escaped_url = install_url.replace("'", "''")
    safe_filename = f"install-{app_label}-helper.cmd"
    return (
        "powershell -NoProfile -ExecutionPolicy Bypass -Command "
        f"\"$tmp = Join-Path $env:TEMP '{safe_filename}'; "
        f"iwr -UseBasicParsing '{escaped_url}' -OutFile $tmp; "
        'cmd /c $tmp"'
    )


def _build_macos_installer_script(*, bundle_base64: str) -> str:
    return f"""#!/bin/zsh
set -euo pipefail

INSTALL_ROOT="$HOME/Library/Application Support/ASF/planning_comm_helper"
REPO_ROOT="$INSTALL_ROOT/repo"
BUNDLE_B64="$INSTALL_ROOT/helper-bundle.b64"

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
fi

if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python 3 est requis pour installer le helper local."
  exit 1
fi

mkdir -p "$INSTALL_ROOT"
cat > "$BUNDLE_B64" <<'__ASF_HELPER_BUNDLE__'
{_wrapped_base64_lines(bundle_base64)}
__ASF_HELPER_BUNDLE__

"$PYTHON_BIN" - <<'PY' "$INSTALL_ROOT"
import base64
import pathlib
import shutil
import sys
import zipfile

install_root = pathlib.Path(sys.argv[1])
repo_root = install_root / "repo"
bundle_path = install_root / "helper-bundle.b64"
archive_path = install_root / "helper-bundle.zip"
archive_path.write_bytes(base64.b64decode(bundle_path.read_text(encoding="utf-8")))
shutil.rmtree(repo_root, ignore_errors=True)
repo_root.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(archive_path) as archive:
    archive.extractall(repo_root)
PY

"$PYTHON_BIN" -m venv "$REPO_ROOT/.venv"
"$REPO_ROOT/.venv/bin/python" -m pip install -r "$REPO_ROOT/requirements-helper.txt"
cd "$REPO_ROOT"
"$REPO_ROOT/.venv/bin/python" -m tools.planning_comm_helper.autostart install

echo "Helper local installe."
"""


def _build_windows_installer_script(*, bundle_base64: str) -> str:
    return f"""@echo off
setlocal

set "INSTALL_ROOT=%LOCALAPPDATA%\\ASF\\planning_comm_helper"
set "REPO_ROOT=%INSTALL_ROOT%\\repo"
set "BUNDLE_B64=%INSTALL_ROOT%\\helper-bundle.b64"

set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD where python >nul 2>nul && set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
  echo Python 3 est requis pour installer le helper local.
  exit /b 1
)

mkdir "%INSTALL_ROOT%" 2>nul
> "%BUNDLE_B64%" (
{_build_windows_echo_block(bundle_base64)}
)

%PYTHON_CMD% -c "import base64, pathlib, shutil, sys, zipfile; install_root = pathlib.Path(sys.argv[1]); repo_root = install_root / 'repo'; bundle_path = install_root / 'helper-bundle.b64'; archive_path = install_root / 'helper-bundle.zip'; archive_path.write_bytes(base64.b64decode(bundle_path.read_text(encoding='utf-8'))); shutil.rmtree(repo_root, ignore_errors=True); repo_root.mkdir(parents=True, exist_ok=True); zipfile.ZipFile(archive_path).extractall(repo_root)" "%INSTALL_ROOT%"
%PYTHON_CMD% -m venv "%REPO_ROOT%\\.venv"
"%REPO_ROOT%\\.venv\\Scripts\\python.exe" -m pip install -r "%REPO_ROOT%\\requirements-helper.txt"
pushd "%REPO_ROOT%"
"%REPO_ROOT%\\.venv\\Scripts\\python.exe" -m tools.planning_comm_helper.autostart install
popd

echo Helper local installe.
"""


def _build_windows_echo_block(bundle_base64: str) -> str:
    lines = []
    for chunk in textwrap.wrap(bundle_base64, 88):
        escaped_chunk = (
            chunk.replace("^", "^^")
            .replace("&", "^&")
            .replace("|", "^|")
            .replace(">", "^>")
            .replace("<", "^<")
        )
        lines.append(f"  echo {escaped_chunk}")
    return "\n".join(lines)


def build_helper_installer_payload(
    *, app_label="asf-wms", system=None, repo_root=None, request=None, install_url=None
):
    signed_access = resolve_helper_installer_access(request, app_label=app_label)
    system_name = _resolved_system(
        request=None if signed_access else request,
        system=signed_access["system"] if signed_access else system,
    )
    signed_install_url = _signed_install_url(
        install_url=install_url or "",
        app_label=app_label,
        system_name=system_name,
        request=request,
    )
    absolute_install_url = _signed_install_url(
        install_url=install_url or "",
        app_label=app_label,
        system_name=system_name,
        request=request,
        absolute=True,
    )
    if system_name == "Darwin":
        bundle_base64 = _helper_bundle_base64(repo_root=repo_root)
        installed_app_path = _macos_installed_app_path()
        return {
            "available": True,
            "platform_label": "macOS",
            "download_label": "Installer le helper (macOS)",
            "filename": f"install-{app_label}-helper.command",
            "command": _macos_install_command(absolute_install_url) if absolute_install_url else "",
            "install_url": signed_install_url,
            "script": _build_macos_installer_script(bundle_base64=bundle_base64),
            "installed_app_path": str(installed_app_path),
            "post_install_guidance": (
                "Au premier lancement, macOS peut demander d'autoriser "
                "ASF Planning Communication Helper a controler Microsoft Excel. "
                f"Validez une fois pour ce poste. L'app stable sera installee dans {installed_app_path}. "
                "Si macOS bloque le fichier telecharge, utilisez Copier la commande ou Faites clic droit > Ouvrir."
            ),
        }
    if system_name == "Windows":
        bundle_base64 = _helper_bundle_base64(repo_root=repo_root)
        return {
            "available": True,
            "platform_label": "Windows",
            "download_label": "Installer le helper (Windows)",
            "filename": f"install-{app_label}-helper.cmd",
            "command": (
                _windows_install_command(absolute_install_url, app_label=app_label)
                if absolute_install_url
                else ""
            ),
            "install_url": signed_install_url,
            "script": _build_windows_installer_script(bundle_base64=bundle_base64),
            "installed_app_path": "",
            "post_install_guidance": "",
        }
    raise ValidationError("Installation du helper indisponible sur ce poste.")


def build_helper_install_context(
    *,
    install_url,
    app_label="asf-wms",
    system=None,
    repo_root=None,
    request=None,
):
    version_policy = build_helper_version_policy()
    try:
        payload = build_helper_installer_payload(
            app_label=app_label,
            system=system,
            repo_root=repo_root,
            request=request,
            install_url=install_url,
        )
    except ValidationError as exc:
        return {
            **version_policy,
            "available": False,
            "platform_label": "ce poste",
            "download_label": "",
            "install_url": "",
            "command": "",
            "installed_app_path": "",
            "post_install_guidance": "",
            "error": _validation_error_message(exc),
        }
    return {
        **payload,
        **version_policy,
        "install_url": payload.get("install_url", install_url),
        "error": "",
    }


def build_helper_installer_response(
    *,
    request=None,
    app_label="asf-wms",
    system=None,
    repo_root=None,
    extra_headers=None,
):
    try:
        payload = build_helper_installer_payload(
            app_label=app_label,
            system=system,
            repo_root=repo_root,
            request=request,
        )
    except ValidationError as exc:
        return JsonResponse({"error": _validation_error_message(exc)}, status=409)
    response = HttpResponse(payload["script"], content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="{filename}"'.format(
        filename=payload["filename"],
    )
    for header_name, header_value in (extra_headers or {}).items():
        response[header_name] = header_value
    return response


def _validation_error_message(exc):
    if getattr(exc, "messages", None):
        return "; ".join(exc.messages)
    return str(exc)
