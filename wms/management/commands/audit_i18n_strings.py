from __future__ import annotations

import html
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

DEFAULT_PATHS = (
    "templates/portal",
    "templates/scan",
    "templates/admin",
    "templates/emails",
    "templates/print",
)
SCANNABLE_SUFFIXES = {".html", ".txt"}
FRENCH_LITERAL_RE = re.compile(
    r"\b("
    r"connexion|association|mot de passe|oublie|premiere|demande|compte|"
    r"expedition|reception|correspondant|destinataire|colis|carton|document|"
    r"valide|introuvable|erreur|pret|cloture|bonjour|envoyez|aucun"
    r")\b",
    re.IGNORECASE,
)
ACCENT_RE = re.compile(r"[àâçéèêëîïôûùüÿœÀÂÇÉÈÊËÎÏÔÛÙÜŸŒ]")
TEXT_NODE_RE = re.compile(r">([^<]+)<")
VISIBLE_ATTRIBUTE_RE = re.compile(
    r"""\b(?:title|aria-label|placeholder|alt)\s*=\s*['"]([^'"]+)['"]"""
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_path(raw_value: str) -> Path:
    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = _project_root() / path
    return path.resolve()


def _relative_to_project_root(path: Path) -> str:
    try:
        return str(path.relative_to(_project_root()))
    except ValueError:
        return str(path)


def _looks_like_french(text: str) -> bool:
    return bool(ACCENT_RE.search(text) or FRENCH_LITERAL_RE.search(text))


def _contains_visible_text_node(line: str) -> bool:
    for candidate in _iter_visible_candidates(line):
        if re.search(r"[A-Za-zÀ-ÿ]", candidate):
            return True
    return False


def _iter_visible_candidates(line: str):
    for match in TEXT_NODE_RE.findall(line):
        candidate = html.unescape(match).strip()
        if candidate and "{{" not in candidate and "{%" not in candidate:
            yield candidate

    for match in VISIBLE_ATTRIBUTE_RE.findall(line):
        candidate = html.unescape(match).strip()
        if candidate and "{{" not in candidate and "{%" not in candidate:
            yield candidate


def _iter_candidate_files(selected_path: str | None):
    raw_paths = [selected_path] if selected_path else list(DEFAULT_PATHS)
    seen: set[Path] = set()

    for raw_path in raw_paths:
        path = _resolve_path(raw_path)
        if not path.exists():
            raise CommandError(f"Chemin introuvable pour l'audit i18n: {raw_path}")

        if path.is_file():
            if path.suffix in SCANNABLE_SUFFIXES and path not in seen:
                seen.add(path)
                yield path
            continue

        for candidate in sorted(path.rglob("*")):
            if (
                candidate.is_file()
                and candidate.suffix in SCANNABLE_SUFFIXES
                and candidate not in seen
            ):
                seen.add(candidate)
                yield candidate


def _scan_template_file(path: Path):
    findings = []
    inside_blocktrans = False
    inside_script = False
    inside_style = False

    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("{#") or stripped.startswith("<!--"):
                continue

            if inside_script:
                if "</script" in line.lower():
                    inside_script = False
                continue

            if inside_style:
                if "</style" in line.lower():
                    inside_style = False
                continue

            if "<script" in line.lower():
                if "</script" not in line.lower():
                    inside_script = True
                continue

            if "<style" in line.lower():
                if "</style" not in line.lower():
                    inside_style = True
                continue

            if inside_blocktrans:
                if "{% endblocktrans" in line:
                    inside_blocktrans = False
                continue

            if "{% blocktrans" in line:
                if "{% endblocktrans" not in line:
                    inside_blocktrans = True
                continue

            if "{% trans" in line:
                continue

            candidates = list(_iter_visible_candidates(line))
            if _contains_visible_text_node(line) or any(
                _looks_like_french(candidate) for candidate in candidates
            ):
                findings.append((_relative_to_project_root(path), lineno, stripped))

    return findings


class Command(BaseCommand):
    help = (
        "Signale les lignes des templates legacy qui contiennent encore des "
        "textes visibles sans wrapper i18n Django."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=None,
            help=(
                "Chemin relatif ou absolu a auditer. "
                "Par defaut, scanne templates/portal, templates/scan, "
                "templates/admin, templates/emails et templates/print."
            ),
        )

    def handle(self, *args, **options):
        findings = []

        for path in _iter_candidate_files(options.get("path")):
            findings.extend(_scan_template_file(path))

        if findings:
            self.stdout.write(self.style.WARNING("Audit i18n strings: findings"))
            for relative_path, lineno, content in findings:
                self.stdout.write(f"{relative_path}:{lineno}: {content}")

            first_path, first_lineno, _ = findings[0]
            raise CommandError(
                "Chaines visibles non internationalisees detectees. "
                f"Premier finding: {first_path}:{first_lineno}."
            )

        self.stdout.write(self.style.SUCCESS("Audit i18n strings: OK."))
