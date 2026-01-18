import re


_WORD_SPLIT_RE = re.compile(r"([-/'’])")
CATEGORY_ACRONYMS = {"EPI", "PCA"}


def normalize_upper(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return ""
    return text.upper()


def normalize_title(value, *, keep_upper=None):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return ""
    keep_upper = {item.upper() for item in (keep_upper or set())}
    tokens = re.split(r"(\s+)", text)
    formatted = []
    for token in tokens:
        if not token or token.isspace():
            formatted.append(token)
            continue
        parts = _WORD_SPLIT_RE.split(token)
        new_parts = []
        for part in parts:
            if part in {"-", "/", "'", "’"}:
                new_parts.append(part)
                continue
            if not part:
                new_parts.append(part)
                continue
            if part.upper() in keep_upper:
                new_parts.append(part.upper())
                continue
            if not part[0].isalpha():
                new_parts.append(part)
                continue
            lower = part.lower()
            new_parts.append(lower[0].upper() + lower[1:])
        formatted.append("".join(new_parts))
    return "".join(formatted)


def normalize_category_name(value, *, is_root=False):
    if is_root:
        return normalize_upper(value)
    return normalize_title(value, keep_upper=CATEGORY_ACRONYMS)
