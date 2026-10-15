"""Install a locally built wheel into a disposable venv and test outside the checkout.

Run after uv build. Uses uv only to create/install; the installed CLI runs directly.
Dependency installation can contact the configured package index. No project secrets needed.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


def run(*argv: str, cwd: Path) -> str:
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=True)
    return result.stdout


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    wheel = root / "dist" / f"portable_ai_harness-{version}-py3-none-any.whl"
    if not wheel.is_file():
        raise SystemExit(f"Build the expected wheel first: {wheel.name}")
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv must be installed and available on PATH")
    with tempfile.TemporaryDirectory(prefix="pah-install-") as temporary:
        directory = Path(temporary)
        environment = directory / "venv"
        executable_dir = "Scripts" if sys.platform == "win32" else "bin"
        python_name = "python.exe" if sys.platform == "win32" else "python"
        cli_name = "pah.exe" if sys.platform == "win32" else "pah"
        python = environment / executable_dir / python_name
        cli = environment / executable_dir / cli_name
        run(uv, "venv", "--python", sys.executable, str(environment), cwd=directory)
        run(uv, "pip", "install", "--python", str(python), str(wheel), cwd=directory)
        help_text = run(str(cli), "--help", cwd=directory)
        if "version" not in help_text:
            raise RuntimeError("Installed CLI help does not list version")
        expected = f"Portable AI Harness {version}"
        if run(str(cli), "--version", cwd=directory).strip() != expected:
            raise RuntimeError("Installed CLI version does not match package metadata")
        report = json.loads(run(str(cli), "version", "--json", cwd=directory))
        if report["cli_version"] != version or report["report_schema"] != 1:
            raise RuntimeError("Installed JSON report is invalid")
        if (
            run(str(python), "-m", "portable_ai_harness", "--version", cwd=directory).strip()
            != expected
        ):
            raise RuntimeError("Installed module entry point failed")
        invalid = subprocess.run([str(cli), "unknown"], cwd=directory, capture_output=True)
        if invalid.returncode != 2:
            raise RuntimeError("Installed CLI did not reject an unknown command")
    print("PASS: wheel installed and CLI exercised outside checkout; temporary venv removed.")


if __name__ == "__main__":
    main()
