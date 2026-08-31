"""YAML fixture loading with deterministic validation.

Every fixture is validated against the strict schema. The `expected` block is
parsed and returned as-is; callers MUST NOT mutate it.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .schema import FixtureBundle, FixtureSpec


class FixtureError(Exception):
    pass


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise FixtureError(f"{path}: fixture YAML must map to an object")
    return data


def load_fixture(path: str | Path) -> FixtureSpec:
    """Load and validate a single fixture file."""
    p = Path(path)
    data = _read_yaml(p)
    if "id" not in data:
        raise FixtureError(f"{p}: fixture missing 'id'")
    return FixtureSpec.model_validate(data)


def load_bundle(source: str, file_paths: list[str | Path]) -> FixtureBundle:
    """Load several fixtures that belong to one source document."""
    fixtures: dict[str, FixtureSpec] = {}
    for fp in file_paths:
        spec = load_fixture(fp)
        if spec.id in fixtures:
            raise FixtureError(f"duplicate fixture id {spec.id!r} in bundle <{source}>")
        fixtures[spec.id] = spec
    return FixtureBundle(source=source, fixtures=fixtures)


def discover_fixtures(directory: str | Path) -> list[Path]:
    """Return all *.yaml / *.yml fixture files under a directory (recursive)."""
    root = Path(directory)
    if not root.exists():
        return []
    return sorted(
        [p for p in root.rglob("*.yaml") if p.is_file()]
        + [p for p in root.rglob("*.yml") if p.is_file()],
        key=lambda p: str(p),
    )
