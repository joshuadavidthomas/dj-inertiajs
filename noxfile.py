from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import nox

nox.options.default_venv_backend = "uv|virtualenv"
nox.options.reuse_existing_virtualenvs = True

PY310 = "3.10"
PY311 = "3.11"
PY312 = "3.12"
PY313 = "3.13"
PY314 = "3.14"
PY_VERSIONS = [PY310, PY311, PY312, PY313, PY314]
PY_DEFAULT = PY_VERSIONS[0]
PY_LATEST = PY_VERSIONS[-1]

DJ52 = "5.2"
DJ60 = "6.0"
DJ61 = "6.1"
DJMAIN = "main"
DJ_VERSIONS = [DJ52, DJ60, DJ61, DJMAIN]
DJ_DEFAULT = DJ_VERSIONS[0]

# The oldest Python each Django version supports, where it is newer than ours.
DJ_MIN_PY = {DJ60: PY312, DJ61: PY312, DJMAIN: PY312}


def version(ver: str) -> tuple[int, ...]:
    """Convert a string version to a tuple of ints, e.g. "3.10" -> (3, 10)"""
    return tuple(map(int, ver.split(".")))


def should_skip(python: str, django: str) -> bool:
    """Return True if this Django version does not support this Python."""
    return version(python) < version(DJ_MIN_PY.get(django, PY_DEFAULT))


def sync(session: nox.Session, python: str, *args: str) -> None:
    session.run_install(
        "uv",
        "sync",
        "--frozen",
        "--all-extras",
        "--python",
        python,
        *args,
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )


def posargs(session: nox.Session) -> list[str]:
    return [part for arg in session.posargs for part in arg.split(" ") if part]


@nox.session
def test(session: nox.Session) -> None:
    session.notify(f"tests(python='{PY_DEFAULT}', django='{DJ_DEFAULT}')")


@nox.session
@nox.parametrize(
    "python,django",
    [
        (python, django)
        for python in PY_VERSIONS
        for django in DJ_VERSIONS
        if not should_skip(python, django)
    ],
)
def tests(session: nox.Session, django: str) -> None:
    sync(session, session.python, "--inexact", "--no-install-package", "django")  # type: ignore[arg-type]
    if django == DJMAIN:
        session.install(
            "django @ https://github.com/django/django/archive/refs/heads/main.zip"
        )
    else:
        session.install(f"django~={django}.0")
    session.run("python", "-m", "pytest", *posargs(session))


@nox.session
def coverage(session: nox.Session) -> None:
    sync(session, PY_DEFAULT)
    try:
        session.run(
            "python", "-m", "pytest", "--cov", "--cov-report=", *posargs(session)
        )
    finally:
        # 0 -> OK, 2 -> the coverage threshold was not met
        success_codes = [0, 2]
        report = ["python", "-m", "coverage", "report"]
        session.run(*report, success_codes=success_codes)
        if summary := os.getenv("GITHUB_STEP_SUMMARY"):
            report += ["--skip-covered", "--skip-empty", "--format=markdown"]
            with Path(summary).open("a") as output:
                output.write("### Coverage\n\n")
                output.flush()
                session.run(*report, stdout=output, success_codes=success_codes)
        else:
            session.run(
                "python",
                "-m",
                "coverage",
                "html",
                "--skip-covered",
                "--skip-empty",
                success_codes=success_codes,
            )


@nox.session
def types(session: nox.Session) -> None:
    sync(session, PY_LATEST)
    session.run("python", "-m", "mypy", ".", *posargs(session))


@nox.session
def lint(session: nox.Session) -> None:
    session.run(
        "uv",
        "run",
        "--with",
        "pre-commit-uv",
        "--python",
        PY_LATEST,
        "pre-commit",
        "run",
        "--all-files",
        external=True,
    )


@nox.session
def gha_matrix(session: nox.Session) -> None:
    sessions = session.run(
        sys.executable, "-m", "nox", "-l", "--json", silent=True, external=True
    )
    matrix = {
        "include": [
            {
                "python-version": entry["python"],
                "django-version": entry["call_spec"]["django"],
            }
            for entry in json.loads(sessions)  # type: ignore[arg-type]
            if entry["name"] == "tests"
        ]
    }
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as fh:
        print(f"matrix={json.dumps(matrix)}", file=fh)
