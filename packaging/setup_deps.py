#!/usr/bin/env python3
"""
MusicTranscriber first-run setup.

Creates a Python venv in the user data directory and pip-installs all
dependencies.  Run by launcher.py in a visible terminal window so the user
can watch progress during the one-time ~3-5 GB download.

Usage (called by launcher.py — do not run directly):
    <bundled-python> setup_deps.py <data_dir> <requirements_version>
"""

import sys
import subprocess
import platform
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: setup_deps.py <data_dir> <requirements_version>")
        sys.exit(1)

    data_dir = Path(sys.argv[1])
    requirements_version = sys.argv[2]

    # Resources dir (python/, backend/, web/, this script) is the parent of
    # this file inside the app bundle.
    resources = Path(__file__).parent.resolve()
    backend_dir = resources / "backend"
    venv_dir = data_dir / "venv"
    version_file = data_dir / ".requirements_version"

    _banner("MusicTranscriber — First-Time Setup")
    print(f"  Data directory : {data_dir}")
    print(f"  Backend source : {backend_dir}")
    print()
    print("  This installs ~3-5 GB of ML libraries.")
    print("  Keep this window open — it will close automatically when done.")
    print()

    # ── Step 1: create venv ───────────────────────────────────────────────
    _step(1, 3, "Creating Python environment")
    if venv_dir.exists():
        import shutil
        print(f"  Removing old venv at {venv_dir} ...", flush=True)
        shutil.rmtree(venv_dir)

    _run([sys.executable, "-m", "venv", str(venv_dir)])
    print(f"  Venv created at {venv_dir}", flush=True)

    venv_pip, venv_python = _venv_executables(venv_dir)

    # Always install pip + setuptools from official PyPI, ignoring any global pip.conf
    # that might point to a corporate registry which could serve stripped packages.
    # setuptools>=81 no longer bundles pkg_resources, which resampy (a torchcrepe
    # dependency) still imports directly — pin below that to keep it available.
    _PYPI = ["--index-url", "https://pypi.org/simple/"]
    _run([str(venv_pip), "install", "--quiet", "--upgrade"] + _PYPI + ["pip", "setuptools<81"])

    # ── Step 2: install Python dependencies ──────────────────────────────
    _step(2, 3, "Installing Python dependencies (this can take 10-30 minutes)")

    req_files = [
        backend_dir / "requirements.txt",
        backend_dir / "requirements-api.txt",
        resources / "requirements-launcher.txt",
    ]
    for req_file in req_files:
        if not req_file.exists():
            print(f"  WARNING: {req_file} not found — skipping.", flush=True)
            continue
        print(f"\n  ▶  pip install -r {req_file.name}", flush=True)
        result = subprocess.run(
            [str(venv_pip), "install"] + _PYPI + ["-r", str(req_file)],
        )
        if result.returncode != 0:
            _error(
                f"pip install failed for {req_file.name}.\n"
                "Check the output above for details, fix the issue, then\n"
                "relaunch MusicTranscriber to retry setup."
            )

    # ── Step 3: finalise ─────────────────────────────────────────────────
    _step(3, 3, "Finalising")
    data_dir.mkdir(parents=True, exist_ok=True)
    version_file.write_text(requirements_version)
    print(f"  Version marker written: {version_file}", flush=True)

    _banner("Setup complete — MusicTranscriber will launch now")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _venv_executables(venv_dir: Path):
    if platform.system() == "Windows":
        pip = venv_dir / "Scripts" / "pip.exe"
        python = venv_dir / "Scripts" / "python.exe"
    else:
        pip = venv_dir / "bin" / "pip"
        python = venv_dir / "bin" / "python3"
    return pip, python


def _run(cmd: list) -> None:
    result = subprocess.run(cmd)
    if result.returncode != 0:
        _error(f"Command failed: {' '.join(str(c) for c in cmd)}")


def _step(n: int, total: int, label: str) -> None:
    print(f"\n[{n}/{total}] {label}...", flush=True)


def _banner(text: str) -> None:
    line = "=" * max(60, len(text) + 4)
    print(f"\n{line}", flush=True)
    print(f"  {text}", flush=True)
    print(f"{line}\n", flush=True)


def _error(msg: str) -> None:
    print(f"\nERROR: {msg}\n", file=sys.stderr, flush=True)
    input("Press Enter to close this window...")
    sys.exit(1)


if __name__ == "__main__":
    main()
