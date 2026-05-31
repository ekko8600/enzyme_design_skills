"""Shared data structures for parsed documents and analysis output."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedDocument:
    """Normalized output from all document parser adapters."""

    document_id: str
    source_path: str
    source_type: str
    title: str
    markdown: str
    parser_backend: str
    metadata: dict[str, Any] = field(default_factory=dict)
    sections: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    figures: list[dict[str, Any]] = field(default_factory=list)
    equations: list[dict[str, Any]] = field(default_factory=list)
    raw_backend_output: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ParsedDocument":
        return cls(**payload)


@dataclass
class AnalysisResult:
    """Structured literature analysis suitable for wiki generation."""

    document_id: str
    title: str
    tldr: str
    research_question: str
    method: str
    contributions: list[str]
    evidence: list[str]
    limitations: list[str]
    concepts: list[str]
    related_work: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    model: str | None = None
    claims: list[str] = field(default_factory=list)
    datasets: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    key_figures: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AnalysisResult":
        for key in ("related_work", "claims", "datasets", "metrics", "key_figures", "open_questions"):
            payload.setdefault(key, [])
        return cls(**payload)


def stable_document_id(source: str, content: str | bytes | None = None) -> str:
    """Create a stable short id from source and optional content."""
    digest = hashlib.sha256()
    digest.update(source.encode("utf-8"))
    if isinstance(content, str):
        digest.update(content.encode("utf-8", errors="ignore"))
    elif isinstance(content, bytes):
        digest.update(content)
    return digest.hexdigest()[:16]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
