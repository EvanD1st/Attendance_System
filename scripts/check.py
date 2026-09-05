"""Run the same component checks locally as CI, stopping at the first failure."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command, directory=ROOT):
    executable = shutil.which(command[0])
    if not executable:
        raise SystemExit(f"Required executable is not on PATH: {command[0]}")
    print(f"\n[{directory.name}] {' '.join(command)}", flush=True)
    subprocess.run([executable, *command[1:]], cwd=directory, check=True)


def backend():
    run([sys.executable, "-m", "ruff", "check", "backend", "scripts"])
    run([sys.executable, "-m", "ruff", "format", "--check", "backend", "scripts"])
    for arguments in (
        ["check"],
        ["makemigrations", "--check", "--dry-run"],
        ["test", "core", "attendance_app", "--settings=config.test_settings"],
        ["spectacular", "--validate", "--fail-on-warn", "--file", os.devnull],
    ):
        run([sys.executable, "backend/manage.py", *arguments])


def web():
    for task in ("format:check", "lint", "test", "build"):
        run(["npm", "run", task], ROOT / "web")


def mobile():
    for command in (
        ["dart", "format", "--output=none", "--set-exit-if-changed", "lib", "test"],
        ["flutter", "analyze"],
        ["flutter", "test"],
    ):
        run(command, ROOT / "mobile")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "component", choices=["all", "backend", "web", "mobile"], default="all", nargs="?"
    )
    args = parser.parse_args()
    checks = {"backend": backend, "web": web, "mobile": mobile}
    for name, check in checks.items():
        if args.component in ("all", name):
            check()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode) from error
