"""Ragenie smoke suite: the repo's first test layer.

Zero-dependency structural checks over the seven Python services:
everything compiles, compose references resolve, Docker bases are
pinned, requirements files are sane, and no hardcoded secrets lurk
in service code. Run: python3 -m pytest tests/ -q
"""

from __future__ import annotations

import py_compile
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SERVICES = sorted(p.name for p in (ROOT / "services").iterdir() if p.is_dir())

SECRET_RE = re.compile(
    r"""(?ix)
    (?:password|passwd|api[_-]?key|secret|token)\s*[:=]\s*["'][^"']{4,}["']
    """,
)
SECRET_ALLOWLIST = ("test", "example", "changeme", "xxx", "placeholder")


def _python_files() -> list[Path]:
    files = []
    for base in ("services", "shared"):
        files.extend(sorted((ROOT / base).rglob("*.py")))
    return files


def test_services_exist():
    assert len(SERVICES) == 7, SERVICES
    assert "conversation-service" in SERVICES


def test_every_python_file_compiles():
    files = _python_files()
    assert files, "no python files found"
    failures = []
    for path in files:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append(f"{path.relative_to(ROOT)}: {exc}")
    assert not failures, "\n".join(failures)


# Services whose build context is documented as intentionally untracked
# (README "Current backend quick start"). Everything else must resolve.
DOCUMENTED_MISSING_CONTEXTS = {"frontend"}


def test_compose_services_resolve():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose.get("services", {})
    app_services = [name for name in services if name in SERVICES]
    assert len(app_services) == len(SERVICES), (
        f"compose omits: {sorted(set(SERVICES) - set(app_services))}"
    )
    for name, service in services.items():
        build = service.get("build")
        if not build:
            continue
        context = build.get("context") if isinstance(build, dict) else build
        assert context, f"{name}: no build context"
        if name in DOCUMENTED_MISSING_CONTEXTS:
            assert not (ROOT / context).is_dir(), (
                f"{name}: context now tracked — drop the documented exception"
            )
        else:
            assert (ROOT / context).is_dir(), f"{name}: context {context} missing"


def test_docker_bases_pinned():
    for service in SERVICES:
        dockerfile = ROOT / "services" / service / "Dockerfile"
        assert dockerfile.is_file(), f"{service}: Dockerfile missing"
        bases = [
            line.split()[1]
            for line in dockerfile.read_text(encoding="utf-8").splitlines()
            if line.startswith("FROM ")
        ]
        assert bases, f"{service}: no FROM line"
        for base in bases:
            tag = base.rsplit(":", 1)
            assert len(tag) == 2 and tag[1] not in ("latest", ""), (
                f"{service}: unpinned base {base}"
            )


def test_requirements_sane():
    for service in SERVICES:
        req = ROOT / "services" / service / "requirements.txt"
        assert req.is_file(), f"{service}: requirements.txt missing"
        lines = [
            line.strip()
            for line in req.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith(("#", "-"))
        ]
        assert lines, f"{service}: requirements.txt has no pinned entries"


def test_no_hardcoded_secrets():
    hits = []
    for path in _python_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = SECRET_RE.search(line)
            if match and not any(
                token in match.group(0).lower() for token in SECRET_ALLOWLIST
            ):
                hits.append(f"{path.relative_to(ROOT)}:{lineno}")
    assert not hits, "possible hardcoded secrets:\n" + "\n".join(hits)


@pytest.mark.skipif(
    not (ROOT / "frontend").exists(), reason="no frontend checkout"
)
def test_frontend_lockfile_present():
    lockfiles = ["package-lock.json", "bun.lock", "pnpm-lock.yaml", "yarn.lock"]
    assert any((ROOT / "frontend" / name).is_file() for name in lockfiles), (
        "frontend has no lockfile"
    )
