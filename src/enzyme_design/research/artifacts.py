"""Explore-run artifact helpers."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def slugify(value: str, limit: int = 80) -> str:
    return "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())[:limit]


def make_run_id(topic: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = slugify(topic) or "explore"
    return f"{stamp}-{slug}"


def write_artifact_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_artifact_markdown(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def archive_run(archive_dir: Path, paths: list[Path], manifest: dict[str, Any]) -> Path:
    """Copy key run artifacts into a stable archive directory."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        target = archive_dir / path.name
        if target.exists() and path.resolve() != target.resolve():
            target = archive_dir / f"{path.parent.name}-{path.name}"
        if path.resolve() != target.resolve():
            shutil.copy2(path, target)
        copied.append(str(target))
    manifest = {**manifest, "archived_paths": copied}
    return write_artifact_json(archive_dir / "manifest.json", manifest)
