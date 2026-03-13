import platform
from pathlib import Path

from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse

from tools.planning_comm_helper.autostart import MACOS_APP_BUNDLE_NAME


def _helper_repo_root():
    return Path(__file__).resolve().parent.parent


def _macos_installed_app_path() -> Path:
    return Path.home() / "Applications" / MACOS_APP_BUNDLE_NAME


def build_helper_installer_payload(*, app_label="asf-wms", system=None, repo_root=None):
    system_name = system or platform.system()
    resolved_repo_root = Path(repo_root or _helper_repo_root())
    if system_name == "Darwin":
        python_path = resolved_repo_root / ".venv" / "bin" / "python"
        installed_app_path = _macos_installed_app_path()
        command = (
            f'cd "{resolved_repo_root}" && '
            f'"{python_path}" -m tools.planning_comm_helper.autostart install'
        )
        script = f"""#!/bin/zsh
set -e
cd "{resolved_repo_root}"
"{python_path}" -m tools.planning_comm_helper.autostart install
"""
        return {
            "available": True,
            "platform_label": "macOS",
            "download_label": "Installer le helper (macOS)",
            "filename": f"install-{app_label}-helper.command",
            "command": command,
            "script": script,
            "installed_app_path": str(installed_app_path),
            "post_install_guidance": (
                "Au premier lancement, macOS peut demander d'autoriser "
                "ASF Planning Communication Helper a controler Microsoft Excel. "
                f"Validez une fois pour ce poste. L'app stable sera installee dans {installed_app_path}."
            ),
        }
    if system_name == "Windows":
        python_path = resolved_repo_root / ".venv" / "Scripts" / "python.exe"
        command = (
            f'cd /d "{resolved_repo_root}" && '
            f'"{python_path}" -m tools.planning_comm_helper.autostart install'
        )
        script = f"""@echo off
cd /d "{resolved_repo_root}"
"{python_path}" -m tools.planning_comm_helper.autostart install
"""
        return {
            "available": True,
            "platform_label": "Windows",
            "download_label": "Installer le helper (Windows)",
            "filename": f"install-{app_label}-helper.cmd",
            "command": command,
            "script": script,
            "installed_app_path": "",
            "post_install_guidance": "",
        }
    raise ValidationError("Installation du helper indisponible sur ce poste.")


def build_helper_install_context(*, install_url, app_label="asf-wms", system=None, repo_root=None):
    try:
        payload = build_helper_installer_payload(
            app_label=app_label,
            system=system,
            repo_root=repo_root,
        )
    except ValidationError as exc:
        return {
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
        "install_url": install_url,
        "error": "",
    }


def build_helper_installer_response(
    *,
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
