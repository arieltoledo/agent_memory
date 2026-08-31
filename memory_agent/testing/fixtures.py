"""Fixture registry.

Discovers every YAML fixture under tests/golden and tests/adversarial and
exposes them as `FixtureBundle`s plus a flat `all_fixtures` mapping. This is
the single source the pytest executables and the report generator consume.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from .schema import FixtureBundle, FixtureSpec
from .loader import discover_fixtures, load_fixture

# Repository-relative locations consumed by this package.
_TESTS_DIR = Path(__file__).resolve().parents[2] / "tests"


def _golden_dir() -> Path:
    return _TESTS_DIR / "golden"


def _adversarial_dir() -> Path:
    return _TESTS_DIR / "adversarial"


def golden_fixtures() -> FixtureBundle:
    files = discover_fixtures(_golden_dir())
    return FixtureBundle(source="Golden Set v0.2.0", fixtures=_load_many(files))


def adversarial_fixtures() -> FixtureBundle:
    files = discover_fixtures(_adversarial_dir())
    return FixtureBundle(source="Adversarial Set v0.2.0", fixtures=_load_many(files))


def _load_many(files: list[Path]) -> dict[str, FixtureSpec]:
    out: dict[str, FixtureSpec] = {}
    for f in files:
        spec = load_fixture(f)
        if spec.id in out:
            raise ValueError(f"duplicate fixture id {spec.id!r} in {f}")
        out[spec.id] = spec
    return out


def all_fixtures() -> dict[str, FixtureSpec]:
    merged: dict[str, FixtureSpec] = {}
    merged.update(golden_fixtures().fixtures)
    merged.update(adversarial_fixtures().fixtures)
    return merged


def iter_fixtures() -> Iterator[FixtureSpec]:
    return iter(all_fixtures().values())
