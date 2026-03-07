from __future__ import annotations

import html
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

DEFAULT_PATHS = (
    "templates/portal",
    "templates/emails",
    "templates/print",
    "templates/admin",
    # Final gate scope: legacy surfaces migrated in Tasks 2-8.
    "templates/scan/base.html",
    "templates/scan/cartons_ready.html",
    "templates/scan/dashboard.html",
    "templates/scan/faq.html",
    "templates/scan/order.html",
    "templates/scan/orders_view.html",
    "templates/scan/pack.html",
    "templates/scan/prepare_kits.html",
    "templates/scan/public_account_request.html",
    "templates/scan/public_order.html",
    "templates/scan/receive.html",
    "templates/scan/receive_association.html",
    "templates/scan/receive_pallet.html",
    "templates/scan/settings.html",
    "templates/scan/shipment_create.html",
    "templates/scan/shipment_tracking.html",
    "templates/scan/shipments_ready.html",
    "templates/scan/shipments_tracking.html",
    "templates/scan/stock.html",
    "templates/scan/stock_update.html",
)
SCANNABLE_SUFFIXES = {".html", ".txt"}
FRENCH_LITERAL_RE = re.compile(
    r"\b("
    r"connexion|association|mot de passe|oublie|premiere|demande|compte|"
    r"expedition|expediteur|reception|correspondant|destinataire|colis|carton|"
    r"document|valide|introuvable|erreur|pret|cloture|bonjour|envoyez|aucun|"
    r"recherche|filtre|filtrer|reinitialiser|pilotage|choisir|organisation|"
    r"role|contact|nouveau|civilite|prenom|nom|telephone|creer|lier|delier|"
    r"perimetre|destination|validite|debut|fin|siege|magasin|rue|porte|cedex|"
    r"france|tous|toutes|aucune|actif"
    r")\b",
    re.IGNORECASE,
)
ACCENT_RE = re.compile(r"[àâçéèêëîïôûùüÿœÀÂÇÉÈÊËÎÏÔÛÙÜŸŒ]")
TEXT_NODE_RE = re.compile(r">([^<]+)<")
INLINE_TRANS_RE = re.compile(r"{%\s*trans\b.*?%}")
INLINE_BLOCKTRANS_RE = re.compile(r"{%\s*blocktrans\b.*?%}.*?{%\s*endblocktrans\s*%}")
VISIBLE_ATTRIBUTE_RE = re.compile(
    r"""\b(?:title|aria-label|placeholder|alt)\s*=\s*['"]([^'"]+)['"]"""
)
EMAIL_RE = re.compile(r"(?i)^[^@\s]+@[^@\s]+\.[^@\s]+$")
URL_RE = re.compile(r"(?i)^https?://\S+$")
PHONE_RE = re.compile(r"^[+()0-9.\s-]+$")
ALLOWED_EXACT_LITERALS = {
    "ASF",
    "ASF WMS",
    "CSV",
    "Email",
    "Excel",
    "Logo",
    "PDF",
    "QR",
    "SKU",
}


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


def _normalize_candidate(text: str) -> str:
    return " ".join(text.split()).strip()


def _is_allowed_literal(text: str) -> bool:
    normalized = _normalize_candidate(text)
    if not normalized:
        return True
    if " // " in normalized:
        parts = [part.strip() for part in normalized.split(" // ")]
        if parts and all(_is_allowed_literal(part) for part in parts):
            return True
    if normalized in ALLOWED_EXACT_LITERALS:
        return True
    if EMAIL_RE.fullmatch(normalized):
        return True
    if URL_RE.fullmatch(normalized):
        return True
    if PHONE_RE.fullmatch(normalized):
        return True
    return False


def _strip_inline_i18n_fragments(line: str) -> str:
    line = INLINE_BLOCKTRANS_RE.sub("", line)
    return INLINE_TRANS_RE.sub("", line)


def _is_actionable_candidate(text: str) -> bool:
    normalized = _normalize_candidate(text)
    if _is_allowed_literal(normalized):
        return False
    return _looks_like_french(normalized)


def _iter_visible_candidates(line: str):
    for match in TEXT_NODE_RE.findall(line):
        candidate = _normalize_candidate(html.unescape(match))
        if candidate and "{{" not in candidate and "{%" not in candidate:
            yield candidate

    for match in VISIBLE_ATTRIBUTE_RE.findall(line):
        candidate = _normalize_candidate(html.unescape(match))
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
            auditable_line = _strip_inline_i18n_fragments(line)
            candidates = list(_iter_visible_candidates(auditable_line))
            if any(_is_actionable_candidate(candidate) for candidate in candidates):
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
