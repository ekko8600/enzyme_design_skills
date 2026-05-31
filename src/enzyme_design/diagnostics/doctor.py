"""Health checks for enzyme-design skills."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import sqlite3
from dataclasses import dataclass
from typing import Any

from enzyme_design.config import Settings
from enzyme_design.retrieval.search_index import SearchIndex
from enzyme_design.storage.index import LiteratureIndex


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def doctor(settings: Settings) -> dict[str, Any]:
    """Return read-mostly project diagnostics for agent workflows."""
    settings.ensure_directories()
    index = LiteratureIndex(settings.index_path, settings.parsed_dir)
    checks = [
        _python_check(),
        _sqlite_fts_check(),
        *_directory_checks(settings),
        _deepseek_check(settings),
        _privacy_check(settings),
        _network_check(settings),
        _opencode_skill_check(settings),
        _command_check("mineru", settings.mineru_command),
        _command_check("paddleocr", settings.paddleocr_command),
        _document_check(index),
        _search_index_check(index, settings),
        _pytest_check(),
    ]
    summary = {
        "ok": sum(1 for item in checks if item.status == "OK"),
        "warn": sum(1 for item in checks if item.status == "WARN"),
        "fail": sum(1 for item in checks if item.status == "FAIL"),
    }
    return {"summary": summary, "checks": [item.to_dict() for item in checks]}


def render_doctor_report(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# enzyme-design Doctor",
        "",
        f"- OK: {summary.get('ok', 0)}",
        f"- WARN: {summary.get('warn', 0)}",
        f"- FAIL: {summary.get('fail', 0)}",
        "",
        "## Checks",
    ]
    for item in report.get("checks", []):
        lines.append(f"- [{item['status']}] {item['name']}: {item['detail']}")
    return "\n".join(lines)


def _python_check() -> DoctorCheck:
    version = platform.python_version()
    major, minor, *_ = (int(part) for part in version.split("."))
    status = "OK" if (major, minor) >= (3, 10) else "FAIL"
    return DoctorCheck("python", status, f"Python {version}")


def _sqlite_fts_check() -> DoctorCheck:
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE docs USING fts5(content)")
    except Exception as exc:  # noqa: BLE001 - diagnostic surface.
        return DoctorCheck("sqlite_fts5", "FAIL", str(exc))
    return DoctorCheck("sqlite_fts5", "OK", f"SQLite {sqlite3.sqlite_version} with FTS5")


def _directory_checks(settings: Settings) -> list[DoctorCheck]:
    paths = {
        "data_dir": settings.data_dir,
        "parsed_dir": settings.parsed_dir,
        "index_parent": settings.index_path.parent,
        "vault_dir": settings.vault_dir,
    }
    return [
        DoctorCheck(name, "OK" if path.exists() else "FAIL", str(path))
        for name, path in paths.items()
    ]


def _deepseek_check(settings: Settings) -> DoctorCheck:
    if settings.deepseek_api_key:
        return DoctorCheck(
            "deepseek",
            "OK",
            f"model={settings.deepseek_model}, base_url={settings.deepseek_base_url}",
        )
    return DoctorCheck(
        "deepseek",
        "WARN",
        "DEEPSEEK_API_KEY not configured; use dry-run or configure key for remote analysis.",
    )


def _privacy_check(settings: Settings) -> DoctorCheck:
    enabled = settings.allow_upload_private_notes_to_llm
    return DoctorCheck(
        "private_upload",
        "OK" if enabled else "WARN",
        "enabled by default" if enabled else "disabled by environment override",
    )


def _network_check(settings: Settings) -> DoctorCheck:
    return DoctorCheck(
        "network_search",
        "OK" if settings.allow_network_search else "WARN",
        "enabled by default" if settings.allow_network_search else "disabled by environment override",
    )


def _opencode_skill_check(settings: Settings) -> DoctorCheck:
    skill_path = settings.root_dir / ".opencode" / "skills" / "enzyme-design" / "SKILL.md"
    if skill_path.is_file():
        return DoctorCheck("opencode_skill", "OK", str(skill_path))
    return DoctorCheck(
        "opencode_skill",
        "WARN",
        f"{skill_path} not found; import the repository skill package or run scripts/sync_opencode_skill.py.",
    )


def _command_check(name: str, command: str) -> DoctorCheck:
    resolved = shutil.which(command)
    if resolved:
        return DoctorCheck(name, "OK", resolved)
    return DoctorCheck(name, "WARN", f"command '{command}' not found; relevant parser fallback may fail.")


def _document_check(index: LiteratureIndex) -> DoctorCheck:
    rows = index.list_documents()
    analyzed = sum(1 for row in rows if row.get("analysis_path"))
    return DoctorCheck("documents", "OK", f"{len(rows)} indexed, {analyzed} analyzed")


def _search_index_check(index: LiteratureIndex, settings: Settings) -> DoctorCheck:
    status = SearchIndex(index, settings.vault_dir).search_status()
    stale = int(status.get("stale_sources", 0))
    orphaned = int(status.get("orphaned_sources", 0))
    chunks = int(status.get("total_chunks", 0))
    level = "WARN" if stale or orphaned else "OK"
    return DoctorCheck("search_index", level, f"{chunks} chunks, {stale} stale, {orphaned} orphaned")


def _pytest_check() -> DoctorCheck:
    if importlib.util.find_spec("pytest") is None:
        return DoctorCheck("pytest", "WARN", "pytest not installed; use scripts/smoke_test.py.")
    return DoctorCheck(
        "pytest",
        "WARN",
        "pytest importable; if local capture segfault occurs, use python scripts/smoke_test.py.",
    )
