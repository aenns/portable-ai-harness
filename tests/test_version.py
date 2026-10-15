"""Core metadata behavior stays independent of terminal and model integrations."""

from dataclasses import FrozenInstanceError
from importlib import metadata

import pytest

from portable_ai_harness.core import version


def test_reads_the_requested_distribution_and_runtime(monkeypatch):
    requested = []

    def installed(name):
        requested.append(name)
        return "2.3.4"

    monkeypatch.setattr(version.metadata, "version", installed)
    monkeypatch.setattr(version, "python_version", lambda: "3.12.15")
    result = version.get_version_info()
    assert requested == ["portable-ai-harness"]
    assert result == version.VersionInfo("portable-ai-harness", "2.3.4", "3.12.15")


def test_missing_metadata_is_an_actionable_failure(monkeypatch):
    def missing(name):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(version.metadata, "version", missing)
    with pytest.raises(RuntimeError, match="Install the package with uv sync"):
        version.get_version_info()


def test_report_cannot_be_mutated():
    result = version.get_version_info()
    with pytest.raises(FrozenInstanceError):
        result.cli_version = "invented"
