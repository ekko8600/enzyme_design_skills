"""SQLite-backed document index."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from enzyme_design.schema import AnalysisResult, ParsedDocument, read_json, write_json


class LiteratureIndex:
    """Small local index for parsed documents and analysis status."""

    def __init__(self, index_path: Path, parsed_dir: Path):
        self.index_path = index_path
        self.parsed_dir = parsed_dir
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.parsed_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.index_path)

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    parser_backend TEXT NOT NULL,
                    parsed_path TEXT NOT NULL,
                    analysis_path TEXT,
                    wiki_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    source_document_id TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def add_document(self, document: ParsedDocument) -> Path:
        doc_dir = self.parsed_dir / document.document_id
        parsed_path = doc_dir / "document.json"
        write_json(parsed_path, document.to_dict())
        (doc_dir / "document.md").write_text(document.markdown, encoding="utf-8")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    document_id, title, source_path, source_type, parser_backend, parsed_path
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    title=excluded.title,
                    source_path=excluded.source_path,
                    source_type=excluded.source_type,
                    parser_backend=excluded.parser_backend,
                    parsed_path=excluded.parsed_path,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    document.document_id,
                    document.title,
                    document.source_path,
                    document.source_type,
                    document.parser_backend,
                    str(parsed_path),
                ),
            )
            conn.commit()
        return parsed_path

    def save_analysis(self, analysis: AnalysisResult) -> Path:
        analysis_path = self.parsed_dir / analysis.document_id / "analysis.json"
        write_json(analysis_path, analysis.to_dict())
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE documents
                SET analysis_path=?, updated_at=CURRENT_TIMESTAMP
                WHERE document_id=?
                """,
                (str(analysis_path), analysis.document_id),
            )
            conn.commit()
        self._upsert_memories_from_analysis(analysis)
        return analysis_path

    def upsert_memory(self, key: str, value: str, source_document_id: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memories (key, value, source_document_id)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    source_document_id=excluded.source_document_id,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (key, value, source_document_id),
            )
            conn.commit()

    def get_memory(self, key: str) -> str | None:
        row = self._one("SELECT value FROM memories WHERE key=?", (key,))
        return None if row is None else str(row[0])

    def list_memories(self) -> list[dict[str, str | None]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT key, value, source_document_id, updated_at FROM memories ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def _upsert_memories_from_analysis(self, analysis: AnalysisResult) -> None:
        if analysis.tldr:
            self.upsert_memory(f"paper:{analysis.document_id}:tldr", analysis.tldr, analysis.document_id)
        if analysis.concepts:
            self.upsert_memory(
                f"paper:{analysis.document_id}:concepts",
                ", ".join(analysis.concepts),
                analysis.document_id,
            )

    def set_wiki_path(self, document_id: str, wiki_path: Path) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE documents SET wiki_path=?, updated_at=CURRENT_TIMESTAMP WHERE document_id=?",
                (str(wiki_path), document_id),
            )
            conn.commit()

    def get_document(self, document_id: str) -> ParsedDocument:
        row = self._one("SELECT parsed_path FROM documents WHERE document_id=?", (document_id,))
        if row is None:
            raise KeyError(f"Unknown document id: {document_id}")
        return ParsedDocument.from_dict(read_json(Path(row[0])))

    def get_analysis(self, document_id: str) -> AnalysisResult | None:
        row = self._one("SELECT analysis_path FROM documents WHERE document_id=?", (document_id,))
        if row is None or row[0] is None:
            return None
        return AnalysisResult.from_dict(read_json(Path(row[0])))

    def list_documents(self) -> list[dict[str, str | None]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT document_id, title, source_path, source_type, parser_backend,
                       analysis_path, wiki_path, updated_at
                FROM documents
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def find_by_topic(self, topic: str) -> list[dict[str, str | None]]:
        topic_lower = f"%{topic.lower()}%"
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM documents WHERE lower(title) LIKE ? ORDER BY updated_at DESC",
                (topic_lower,),
            ).fetchall()
        return [dict(row) for row in rows]

    def iter_analyzed(self) -> Iterable[tuple[ParsedDocument, AnalysisResult]]:
        for row in self.list_documents():
            if row["analysis_path"]:
                yield self.get_document(str(row["document_id"])), AnalysisResult.from_dict(
                    read_json(Path(str(row["analysis_path"])))
                )

    def _one(self, sql: str, args: tuple[str, ...]) -> tuple | None:
        with self._connect() as conn:
            return conn.execute(sql, args).fetchone()
