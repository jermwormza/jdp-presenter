"""Version parsing and release-build bump helpers."""
from __future__ import annotations

import re


_VERSION_LINE = re.compile(r'(?m)^(version\s*=\s*")[^"]+("\s*)$')


def bump_version(version: str, part: str = "patch") -> str:
    pieces = version.split(".")
    if len(pieces) != 3 or not all(piece.isdigit() for piece in pieces):
        raise ValueError(f"Expected a semantic version such as 1.2.3, got {version!r}")
    major, minor, patch = (int(piece) for piece in pieces)
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unknown version part: {part}")


def replace_project_version(pyproject_text: str, version: str) -> str:
    updated, count = _VERSION_LINE.subn(rf'\g<1>{version}\g<2>', pyproject_text, count=1)
    if count != 1:
        raise ValueError("Could not find project version in pyproject.toml")
    return updated
