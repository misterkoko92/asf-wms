from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from wms.models import UiMode, UserUiPreference
from wms.ui_mode import (
    DEFAULT_UI_MODE,
    get_ui_mode_for_user,
    normalize_ui_mode,
    set_ui_mode_for_user,
)


class UiModeHelpersTests(TestCase):
    def test_normalize_ui_mode_defaults_to_legacy(self):
        self.assertEqual(normalize_ui_mode(None), UiMode.LEGACY)
        self.assertEqual(normalize_ui_mode("anything"), UiMode.LEGACY)
        self.assertEqual(normalize_ui_mode("NEXT"), UiMode.NEXT)

    def test_get_ui_mode_for_anonymous_user_returns_default(self):
        self.assertEqual(get_ui_mode_for_user(AnonymousUser()), DEFAULT_UI_MODE)

    def test_set_ui_mode_for_authenticated_user_persists_preference(self):
        user = get_user_model().objects.create_user(
            username="ui-mode-user",
            password="pass1234",
        )

        saved_mode = set_ui_mode_for_user(user, UiMode.NEXT)

        self.assertEqual(saved_mode, UiMode.NEXT)
        preference = UserUiPreference.objects.get(user=user)
        self.assertEqual(preference.ui_mode, UiMode.NEXT)
        self.assertEqual(get_ui_mode_for_user(user), UiMode.NEXT)
