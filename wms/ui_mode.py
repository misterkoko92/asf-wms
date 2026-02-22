from typing import Optional

from django.contrib.auth.models import AnonymousUser
from .models import UiMode, UserUiPreference


DEFAULT_UI_MODE = UiMode.LEGACY


def normalize_ui_mode(raw_value: Optional[str]) -> str:
    value = (raw_value or "").strip().lower()
    if value == UiMode.NEXT:
        return UiMode.NEXT
    return UiMode.LEGACY


def get_ui_mode_for_user(user) -> str:
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return DEFAULT_UI_MODE
    preference = (
        UserUiPreference.objects.filter(user_id=user.id)
        .values_list("ui_mode", flat=True)
        .first()
    )
    return normalize_ui_mode(preference)


def set_ui_mode_for_user(user, mode: str) -> str:
    normalized = normalize_ui_mode(mode)
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return normalized
    UserUiPreference.objects.update_or_create(
        user_id=user.id,
        defaults={"ui_mode": normalized},
    )
    return normalized


def is_next_ui_mode(mode: str) -> bool:
    return normalize_ui_mode(mode) == UiMode.NEXT
