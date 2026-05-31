"""Sync the canonical enzyme-design skill into the OpenCode skill directory."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".opencode" / "skills" / "enzyme-design"
REFERENCE_NAMES = [
    "ai-methods.md",
    "co-design.md",
    "computational-planning.md",
    "evidence-research.md",
    "literature-coverage-checklist.md",
    "literature-runtime.md",
    "literature-synthesis-schema.md",
    "output-contracts.md",
]


def main() -> int:
    references_dir = TARGET / "references"
    references_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "SKILL.md", TARGET / "SKILL.md")
    for name in REFERENCE_NAMES:
        shutil.copy2(ROOT / "references" / name, references_dir / name)
    print(f"synced OpenCode skill: {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
