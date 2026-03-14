from unittest.runner import TextTestResult

from django.conf import settings
from django.test.runner import (
    DebugSQLTextTestResult,
    DiscoverRunner,
    ParallelTestSuite,
    PDBDebugResult,
    RemoteTestResult,
    RemoteTestRunner,
)
from django.utils import translation


class _LanguageResetMixin:
    def _reset_language(self):
        translation.deactivate_all()
        translation.activate(settings.LANGUAGE_CODE)

    def startTestRun(self):
        self._reset_language()
        super().startTestRun()

    def startTest(self, test):
        self._reset_language()
        super().startTest(test)

    def stopTest(self, test):
        try:
            super().stopTest(test)
        finally:
            self._reset_language()


class LanguageResetTextTestResult(_LanguageResetMixin, TextTestResult):
    pass


class LanguageResetDebugSQLTextTestResult(
    _LanguageResetMixin,
    DebugSQLTextTestResult,
):
    pass


class LanguageResetPDBDebugResult(_LanguageResetMixin, PDBDebugResult):
    pass


class LanguageResetRemoteTestResult(_LanguageResetMixin, RemoteTestResult):
    pass


class LanguageResetRemoteTestRunner(RemoteTestRunner):
    resultclass = LanguageResetRemoteTestResult


class LanguageResetParallelTestSuite(ParallelTestSuite):
    runner_class = LanguageResetRemoteTestRunner


class LanguageResetDiscoverRunner(DiscoverRunner):
    parallel_test_suite = LanguageResetParallelTestSuite

    def get_resultclass(self):
        if self.debug_sql:
            return LanguageResetDebugSQLTextTestResult
        if self.pdb:
            return LanguageResetPDBDebugResult
        return LanguageResetTextTestResult
