"""Tests for the example test runner."""

from pathlib import Path

import pytest

from scripts.test_examples import ExampleTest, ExampleTester
from scripts.test_examples import TestCategory as ExampleCategory
from scripts.test_examples import TestStatus as ExampleStatus


def test_dry_run_skips_before_checking_prerequisites(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Dry-run mode must not probe external services or local prerequisites."""
    tester = ExampleTester(dry_run=True)
    test = ExampleTest(
        name="Offline dry run",
        path=tmp_path / "missing.py",
        category=ExampleCategory.OPERATORS,
        requires_ollama=True,
        requires_opensearch=True,
        requires_env=["MISSING_API_KEY"],
    )

    def fail_if_called(*, test: ExampleTest) -> tuple[bool, str | None]:
        pytest.fail(f"check_prerequisites() unexpectedly called for {test.name}")

    monkeypatch.setattr(tester, "check_prerequisites", fail_if_called)

    result = tester.run_test(test=test)

    assert result.status is ExampleStatus.SKIPPED
    assert result.skip_reason == "Dry run mode"


def test_normal_run_checks_prerequisites(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Non-dry runs must retain prerequisite checks."""
    tester = ExampleTester()
    test = ExampleTest(
        name="Normal run",
        path=tmp_path / "missing.py",
        category=ExampleCategory.OPERATORS,
    )
    checked_tests: list[ExampleTest] = []

    def check_prerequisites(*, test: ExampleTest) -> tuple[bool, str | None]:
        checked_tests.append(test)
        return False, "Prerequisite unavailable"

    monkeypatch.setattr(tester, "check_prerequisites", check_prerequisites)

    result = tester.run_test(test=test)

    assert checked_tests == [test]
    assert result.status is ExampleStatus.SKIPPED
    assert result.skip_reason == "Prerequisite unavailable"
