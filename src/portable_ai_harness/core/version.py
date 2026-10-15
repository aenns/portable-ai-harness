"""Read actual installed distribution metadata without project discovery or network access."""

from dataclasses import dataclass
from importlib import metadata
from platform import python_version

DISTRIBUTION = "portable-ai-harness"


@dataclass(frozen=True)
class VersionInfo:
    """Installed identity; configuration/pack identities are added when implemented."""

    distribution: str
    cli_version: str
    python_version: str


def get_version_info() -> VersionInfo:
    """Return installed facts; never disguise missing metadata as a real version."""
    try:
        installed_version = metadata.version(DISTRIBUTION)
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            "Portable AI Harness package metadata is missing. Install the package with uv sync."
        ) from exc
    return VersionInfo(DISTRIBUTION, installed_version, python_version())
