#!/usr/bin/env python3
"""Cross-platform task runner for CenterAlign.

Usage:
    python tasks.py setup
    python tasks.py run-finance
    python tasks.py ui
    python tasks.py demo
    python tasks.py demo-all
    python tasks.py test
    python tasks.py reset
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

VENV_DIR = Path(".venv")
if sys.platform == "win32":
    PYTHON = str(VENV_DIR / "Scripts" / "python.exe")
else:
    PYTHON = str(VENV_DIR / "bin" / "python")


def run(cmd: list[str]) -> None:
    print(f"==> {' '.join(cmd)}")
    subprocess.check_call(cmd)


def task_setup() -> None:
    """Setup virtualenv, install dependencies, browser and initial seed."""
    if not VENV_DIR.exists():
        run(["uv", "venv", "--python", "3.12", ".venv"])

    run(["uv", "pip", "install", "-e", ".[dev]"])
    run([PYTHON, "-m", "playwright", "install", "chromium"])

    env_file = Path(".env")
    if not env_file.exists() and Path(".env.example").exists():
        shutil.copy(".env.example", ".env")
        print("Created .env from .env.example")

    seed_script = Path("finance_app/seed.py")
    if seed_script.exists():
        run([PYTHON, str(seed_script), "--reset"])
    print("Setup completed successfully.")


def task_run_finance() -> None:
    """Run mock Finance App on port 8000."""
    run([PYTHON, "-m", "uvicorn", "finance_app.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"])


def task_ui() -> None:
    """Run UI Dashboard on port 8001."""
    run([PYTHON, "-m", "uvicorn", "ui.server:app", "--host", "0.0.0.0", "--port", "8001", "--reload"])


def task_demo() -> None:
    """Run Scenario 1 (happy path)."""
    run([PYTHON, "scenarios/s1_happy_path.py"])


def task_demo_all() -> None:
    """Run Scenario 2 (full mixed 12 claims)."""
    run([PYTHON, "scenarios/s2_full_mixed.py"])


def task_test() -> None:
    """Run test suite."""
    run([PYTHON, "-m", "pytest", "tests/", "-v"])


def task_reset() -> None:
    """Reset SQLite databases and test artifacts."""
    seed_script = Path("finance_app/seed.py")
    if seed_script.exists():
        run([PYTHON, str(seed_script), "--reset"])

    reports_dir = Path("reports")
    if reports_dir.exists():
        for f in reports_dir.glob("*.db*"):
            f.unlink(missing_ok=True)
        for f in reports_dir.glob("*.json"):
            f.unlink(missing_ok=True)
        screenshots = reports_dir / "screenshots"
        if screenshots.exists():
            for f in screenshots.glob("*"):
                f.unlink(missing_ok=True)
    print("Reset completed.")


COMMANDS = {
    "setup": task_setup,
    "run-finance": task_run_finance,
    "ui": task_ui,
    "demo": task_demo,
    "demo-all": task_demo_all,
    "test": task_test,
    "reset": task_reset,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Available tasks:")
        for name in COMMANDS:
            print(f"  python tasks.py {name}")
        sys.exit(1)

    cmd = sys.argv[1]
    COMMANDS[cmd]()


if __name__ == "__main__":
    main()
