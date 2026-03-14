from io import StringIO
from unittest import FunctionTestCase
from unittest.runner import _WritelnDecorator

from django.test import SimpleTestCase
from django.utils import translation

from asf_wms.test_runner import (
    LanguageResetRemoteTestResult,
    LanguageResetTextTestResult,
)


class LanguageResetTextTestResultTests(SimpleTestCase):
    def test_start_test_resets_active_language_to_default(self):
        result = LanguageResetTextTestResult(_WritelnDecorator(StringIO()), False, 0)
        test = FunctionTestCase(lambda: None)

        translation.activate("en")

        result.startTest(test)

        self.assertEqual(translation.get_language(), "fr")


class LanguageResetRemoteTestResultTests(SimpleTestCase):
    def test_stop_test_restores_default_language(self):
        result = LanguageResetRemoteTestResult()
        test = FunctionTestCase(lambda: None)

        result.startTest(test)
        translation.activate("en")

        result.stopTest(test)

        self.assertEqual(translation.get_language(), "fr")
