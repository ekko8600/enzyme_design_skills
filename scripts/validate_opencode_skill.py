"""Validate the self-contained OpenCode enzyme-design skill mirror."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".opencode" / "skills" / "enzyme-design"


def main() -> int:
    canonical_skill = ROOT / "SKILL.md"
    wrapper_skill = TARGET / "SKILL.md"
    if not wrapper_skill.is_file():
        raise SystemExit(f"missing OpenCode skill: {wrapper_skill}")
    if wrapper_skill.read_text(encoding="utf-8") != canonical_skill.read_text(encoding="utf-8"):
        raise SystemExit("OpenCode SKILL.md is stale; run python scripts/sync_opencode_skill.py")

    canonical_references = sorted((ROOT / "references").glob("*.md"))
    wrapper_references = sorted((TARGET / "references").glob("*.md"))
    if [path.name for path in wrapper_references] != [path.name for path in canonical_references]:
        raise SystemExit("OpenCode reference set is stale; run python scripts/sync_opencode_skill.py")
    for canonical in canonical_references:
        wrapper = TARGET / "references" / canonical.name
        if wrapper.read_text(encoding="utf-8") != canonical.read_text(encoding="utf-8"):
            raise SystemExit(f"OpenCode reference is stale: {canonical.name}")

    print(f"OpenCode skill valid: {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
