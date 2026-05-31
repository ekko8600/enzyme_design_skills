"""SQLite FTS-backed local search index."""

from __future__ import annotations

import json
import re
import sqlite3
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from enzyme_design.schema import AnalysisResult, ParsedDocument
from enzyme_design.storage.index import LiteratureIndex


SOURCE_CHOICES = {"parsed", "analysis", "wiki", "logs", "all"}
MAX_CHUNK_CHARS = 4000
QUESTION_STOPWORDS = {
    "what",
    "which",
    "where",
    "when",
    "why",
    "how",
    "does",
    "did",
    "do",
    "the",
    "and",
    "or",
    "with",
    "from",
    "this",
    "that",
    "paper",
    "papers",
    "evidence",
    "mention",
    "mentions",
    "说明",
    "什么",
    "哪些",
    "哪个",
    "如何",
    "是否",
    "论文",
    "证据",
}
SOURCE_WEIGHTS = {"parsed": 2.0, "analysis": 1.5, "logs": 1.0, "wiki": 0.8}


@dataclass(frozen=True)
class SearchHit:
    """One local retrieval result with source trace metadata."""

    chunk_id: int
    document_id: str
    title: str
    source_type: str
    source_path: str
    section_path: str
    chunk_index: int
    content: str
    score: float
    start_line: int = 1
    end_line: int = 1
    rank_score: float = 0.0
    match_reason: str = ""

    @property
    def excerpt(self) -> str:
        compact = " ".join(self.content.split())
        return compact[:500] + ("..." if len(compact) > 500 else "")


@dataclass(frozen=True)
class _Chunk:
    document_id: str
    title: str
    source_type: str
    source_path: str
    section_path: str
    chunk_index: int
    content: str
    start_line: int
    end_line: int
    heading_level: int
    content_hash: str


@dataclass(frozen=True)
class _SourceRecord:
    source_type: str
    source_path: str
    content: str
    chunks: list[_Chunk]

    @property
    def content_hash(self) -> str:
        return _hash_text(self.content)

    @property
    def size(self) -> int:
        return len(self.content.encode("utf-8", errors="ignore"))

    @property
    def mtime(self) -> float:
        path = Path(self.source_path)
        if path.exists():
            return path.stat().st_mtime
        return 0.0


class SearchIndex:
    """Build and query a local FTS index from parsed files and the vault."""

    def __init__(self, index: LiteratureIndex, vault_dir: Path):
        self.index = index
        self.vault_dir = vault_dir
        self._initialize()

    def rebuild(self, source: str = "all", full: bool = False) -> int:
        source = _normalize_source(source)
        records = list(self._iter_source_records(source))
        with self.index._connect() as conn:  # Uses the same SQLite file as the document index.
            self._create_tables(conn)
            if source == "all" and (full or not self._has_source_state(conn)):
                conn.execute("DELETE FROM search_chunks")
                conn.execute("DELETE FROM search_chunk_meta")
                conn.execute("DELETE FROM search_source_state")
            elif full:
                self._delete_source_type(conn, source)
            current_keys = {(record.source_type, record.source_path) for record in records}
            for state_type, state_path in self._state_keys(conn, source):
                if (state_type, state_path) not in current_keys:
                    self._delete_source_record(conn, state_type, state_path)
            indexed_count = 0
            for record in records:
                if not full and self._source_is_fresh(conn, record):
                    continue
                self._delete_source_record(conn, record.source_type, record.source_path)
                for chunk in record.chunks:
                    cursor = conn.execute(
                        """
                        INSERT INTO search_chunks (
                            document_id, title, source_type, source_path, section_path, chunk_index, content
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk.document_id,
                            chunk.title,
                            chunk.source_type,
                            chunk.source_path,
                            chunk.section_path,
                            chunk.chunk_index,
                            chunk.content,
                        ),
                    )
                    chunk_id = int(cursor.lastrowid)
                    conn.execute(
                        """
                        INSERT INTO search_chunk_meta (
                            chunk_id, document_id, title, source_type, source_path, section_path,
                            chunk_index, start_line, end_line, heading_level, content_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk_id,
                            chunk.document_id,
                            chunk.title,
                            chunk.source_type,
                            chunk.source_path,
                            chunk.section_path,
                            chunk.chunk_index,
                            chunk.start_line,
                            chunk.end_line,
                            chunk.heading_level,
                            chunk.content_hash,
                        ),
                    )
                    indexed_count += 1
                conn.execute(
                    """
                    INSERT INTO search_source_state (
                        source_type, source_path, mtime, size, content_hash, indexed_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_type, source_path) DO UPDATE SET
                        mtime=excluded.mtime,
                        size=excluded.size,
                        content_hash=excluded.content_hash,
                        indexed_at=excluded.indexed_at
                    """,
                    (
                        record.source_type,
                        record.source_path,
                        record.mtime,
                        record.size,
                        record.content_hash,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
            conn.commit()
        return indexed_count

    def search_status(self, source: str = "all") -> dict[str, object]:
        source = _normalize_source(source)
        records = list(self._iter_source_records(source))
        current = {(record.source_type, record.source_path): record for record in records}
        with self.index._connect() as conn:
            self._create_tables(conn)
            state_rows = self._state_rows(conn, source)
            state = {(row["source_type"], row["source_path"]): row for row in state_rows}
            source_counts = {
                source_type: conn.execute(
                    "SELECT COUNT(*) FROM search_chunk_meta WHERE source_type=?",
                    (source_type,),
                ).fetchone()[0]
                for source_type in sorted(SOURCE_CHOICES - {"all"})
            }
            total_chunks = conn.execute("SELECT COUNT(*) FROM search_chunk_meta").fetchone()[0]
        stale: list[str] = []
        fresh = 0
        for key, record in current.items():
            row = state.get(key)
            if row and str(row["content_hash"]) == record.content_hash:
                fresh += 1
            else:
                stale.append(record.source_path)
        orphaned = [path for key in state for path in [key[1]] if key not in current]
        return {
            "total_chunks": int(total_chunks),
            "fresh_sources": fresh,
            "stale_sources": len(stale),
            "orphaned_sources": len(orphaned),
            "source_chunks": {key: int(value) for key, value in source_counts.items()},
            "stale_paths": stale[:20],
            "orphaned_paths": orphaned[:20],
        }

    def search(self, query: str, top_k: int = 8, source: str = "all") -> list[SearchHit]:
        source = _normalize_source(source)
        query = query.strip()
        if not query:
            return []
        self._initialize()
        variants = _query_variants(query)
        candidates: list[SearchHit] = []
        candidates.extend(self._search_fts(variants["phrase"], top_k * 2, source, "phrase_fts"))
        if variants["keywords"] != variants["phrase"]:
            candidates.extend(self._search_fts(variants["keywords"], top_k * 2, source, "keyword_fts"))
        candidates.extend(self._search_title_section_like(query, top_k * 2, source))
        candidates.extend(self._search_like(query, top_k * 2, source, "content_like"))
        ranked = [_with_rank_score(hit, query) for hit in candidates]
        ranked.sort(key=lambda hit: hit.rank_score, reverse=True)
        return _dedupe_hits(ranked, top_k)

    def count_chunks(self, source: str = "all") -> int:
        source = _normalize_source(source)
        with self.index._connect() as conn:
            self._create_tables(conn)
            if source == "all":
                row = conn.execute("SELECT COUNT(*) FROM search_chunk_meta").fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) FROM search_chunk_meta WHERE source_type=?",
                    (source,),
                ).fetchone()
        return int(row[0]) if row else 0

    def _initialize(self) -> None:
        with self.index._connect() as conn:
            self._create_tables(conn)
            conn.commit()

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS search_chunks USING fts5(
                document_id UNINDEXED,
                title,
                source_type UNINDEXED,
                source_path UNINDEXED,
                section_path,
                chunk_index UNINDEXED,
                content
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_chunk_meta (
                chunk_id INTEGER PRIMARY KEY,
                document_id TEXT NOT NULL,
                title TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_path TEXT NOT NULL,
                section_path TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                start_line INTEGER NOT NULL DEFAULT 1,
                end_line INTEGER NOT NULL DEFAULT 1,
                heading_level INTEGER NOT NULL DEFAULT 0,
                content_hash TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_source_state (
                source_type TEXT NOT NULL,
                source_path TEXT NOT NULL,
                mtime REAL NOT NULL,
                size INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                indexed_at TEXT NOT NULL,
                PRIMARY KEY (source_type, source_path)
            )
            """
        )
        self._ensure_meta_columns(conn)

    def _ensure_meta_columns(self, conn: sqlite3.Connection) -> None:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(search_chunk_meta)").fetchall()}
        for name, ddl in {
            "start_line": "ALTER TABLE search_chunk_meta ADD COLUMN start_line INTEGER NOT NULL DEFAULT 1",
            "end_line": "ALTER TABLE search_chunk_meta ADD COLUMN end_line INTEGER NOT NULL DEFAULT 1",
            "heading_level": "ALTER TABLE search_chunk_meta ADD COLUMN heading_level INTEGER NOT NULL DEFAULT 0",
            "content_hash": "ALTER TABLE search_chunk_meta ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''",
        }.items():
            if name not in existing:
                conn.execute(ddl)

    def _search_fts(self, query: str, top_k: int, source: str, reason: str) -> list[SearchHit]:
        match_query = _fts_query(query)
        source_filter = "" if source == "all" else "AND m.source_type = ?"
        params: list[object] = [match_query]
        if source != "all":
            params.append(source)
        params.append(max(top_k * 4, top_k))
        sql = f"""
            SELECT
                s.rowid AS chunk_id,
                s.document_id,
                s.title,
                s.source_type,
                s.source_path,
                s.section_path,
                s.chunk_index,
                s.content,
                bm25(search_chunks) AS score,
                m.start_line,
                m.end_line,
                m.heading_level,
                m.content_hash
            FROM search_chunks AS s
            JOIN search_chunk_meta AS m ON m.chunk_id = s.rowid
            WHERE search_chunks MATCH ? {source_filter}
            ORDER BY score ASC
            LIMIT ?
        """
        try:
            with self.index._connect() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(sql, tuple(params)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [_hit_from_row(row, reason) for row in rows]

    def _search_like(self, query: str, top_k: int, source: str, reason: str) -> list[SearchHit]:
        terms = _query_terms(query)
        if not terms:
            terms = [query]
        clauses = []
        params: list[object] = []
        for term in terms[:6]:
            clauses.append("(lower(s.title) LIKE ? OR lower(s.section_path) LIKE ? OR lower(s.content) LIKE ?)")
            needle = f"%{term.lower()}%"
            params.extend([needle, needle, needle])
        source_filter = "" if source == "all" else "AND m.source_type = ?"
        if source != "all":
            params.append(source)
        params.append(max(top_k * 4, top_k))
        sql = f"""
            SELECT
                s.rowid AS chunk_id,
                s.document_id,
                s.title,
                s.source_type,
                s.source_path,
                s.section_path,
                s.chunk_index,
                s.content,
                1000.0 AS score,
                m.start_line,
                m.end_line,
                m.heading_level,
                m.content_hash
            FROM search_chunks AS s
            JOIN search_chunk_meta AS m ON m.chunk_id = s.rowid
            WHERE ({' OR '.join(clauses)}) {source_filter}
            LIMIT ?
        """
        with self.index._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [_hit_from_row(row, reason) for row in rows]

    def _search_title_section_like(self, query: str, top_k: int, source: str) -> list[SearchHit]:
        terms = _query_terms(query) or [query]
        clauses = []
        params: list[object] = []
        for term in terms[:6]:
            clauses.append("(lower(s.title) LIKE ? OR lower(s.section_path) LIKE ?)")
            needle = f"%{term.lower()}%"
            params.extend([needle, needle])
        source_filter = "" if source == "all" else "AND m.source_type = ?"
        if source != "all":
            params.append(source)
        params.append(max(top_k * 2, top_k))
        sql = f"""
            SELECT
                s.rowid AS chunk_id,
                s.document_id,
                s.title,
                s.source_type,
                s.source_path,
                s.section_path,
                s.chunk_index,
                s.content,
                500.0 AS score,
                m.start_line,
                m.end_line,
                m.heading_level,
                m.content_hash
            FROM search_chunks AS s
            JOIN search_chunk_meta AS m ON m.chunk_id = s.rowid
            WHERE ({' OR '.join(clauses)}) {source_filter}
            LIMIT ?
        """
        with self.index._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [_hit_from_row(row, "title_section_like") for row in rows]

    def _iter_source_records(self, source: str) -> Iterable[_SourceRecord]:
        if source in {"parsed", "analysis", "all"}:
            for row in self.index.list_documents():
                document_id = str(row["document_id"])
                if source in {"parsed", "all"}:
                    try:
                        document = self.index.get_document(document_id)
                    except (KeyError, FileNotFoundError, json.JSONDecodeError):
                        document = None
                    if document is not None:
                        markdown = _document_search_markdown(document)
                        chunks = list(_chunks_from_document(document, markdown))
                        yield _SourceRecord(
                            source_type="parsed",
                            source_path=document.source_path,
                            content=markdown,
                            chunks=chunks,
                        )
                if source in {"analysis", "all"}:
                    analysis = self.index.get_analysis(document_id)
                    if analysis is not None:
                        source_path = str(row["analysis_path"] or f"data/parsed/{analysis.document_id}/analysis.json")
                        markdown = _analysis_markdown(analysis)
                        chunks = list(_chunks_from_analysis(
                            analysis,
                            source_path=source_path,
                        ))
                        yield _SourceRecord(
                            source_type="analysis",
                            source_path=source_path,
                            content=markdown,
                            chunks=chunks,
                        )
        if source in {"wiki", "logs", "all"}:
            yield from self._iter_vault_source_records(source)

    def _iter_vault_source_records(self, source: str) -> Iterable[_SourceRecord]:
        if not self.vault_dir.exists():
            return
        roots: list[tuple[str, Path]] = []
        if source in {"wiki", "all"}:
            roots.extend(
                [
                    ("wiki", self.vault_dir / "papers"),
                    ("wiki", self.vault_dir / "topics"),
                    ("wiki", self.vault_dir / "concepts"),
                ]
            )
        if source in {"logs", "all"}:
            roots.append(("logs", self.vault_dir / "research_logs"))
        for source_type, root in roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*.md")):
                text = _read_text(path)
                if not text:
                    continue
                title = _title_from_markdown(text) or path.stem
                doc_id = _document_id_from_path(path, self.vault_dir)
                chunks = list(_chunks_from_markdown(
                    document_id=doc_id,
                    title=title,
                    markdown=text,
                    source_type=source_type,
                    source_path=str(path),
                ))
                yield _SourceRecord(
                    source_type=source_type,
                    source_path=str(path),
                    content=text,
                    chunks=chunks,
                )

    def _delete_source_type(self, conn: sqlite3.Connection, source_type: str) -> None:
        conn.execute(
            "DELETE FROM search_chunks WHERE rowid IN (SELECT chunk_id FROM search_chunk_meta WHERE source_type=?)",
            (source_type,),
        )
        conn.execute("DELETE FROM search_chunk_meta WHERE source_type=?", (source_type,))
        conn.execute("DELETE FROM search_source_state WHERE source_type=?", (source_type,))

    def _delete_source_record(self, conn: sqlite3.Connection, source_type: str, source_path: str) -> None:
        conn.execute(
            """
            DELETE FROM search_chunks
            WHERE rowid IN (
                SELECT chunk_id FROM search_chunk_meta WHERE source_type=? AND source_path=?
            )
            """,
            (source_type, source_path),
        )
        conn.execute(
            "DELETE FROM search_chunk_meta WHERE source_type=? AND source_path=?",
            (source_type, source_path),
        )
        conn.execute(
            "DELETE FROM search_source_state WHERE source_type=? AND source_path=?",
            (source_type, source_path),
        )

    def _has_source_state(self, conn: sqlite3.Connection) -> bool:
        row = conn.execute("SELECT COUNT(*) FROM search_source_state").fetchone()
        return bool(row and row[0])

    def _state_keys(self, conn: sqlite3.Connection, source: str) -> list[tuple[str, str]]:
        if source == "all":
            rows = conn.execute("SELECT source_type, source_path FROM search_source_state").fetchall()
        else:
            rows = conn.execute(
                "SELECT source_type, source_path FROM search_source_state WHERE source_type=?",
                (source,),
            ).fetchall()
        return [(str(row[0]), str(row[1])) for row in rows]

    def _state_rows(self, conn: sqlite3.Connection, source: str) -> list[sqlite3.Row]:
        conn.row_factory = sqlite3.Row
        if source == "all":
            return conn.execute("SELECT * FROM search_source_state").fetchall()
        return conn.execute("SELECT * FROM search_source_state WHERE source_type=?", (source,)).fetchall()

    def _source_is_fresh(self, conn: sqlite3.Connection, record: _SourceRecord) -> bool:
        row = conn.execute(
            """
            SELECT content_hash FROM search_source_state
            WHERE source_type=? AND source_path=?
            """,
            (record.source_type, record.source_path),
        ).fetchone()
        return bool(row and str(row[0]) == record.content_hash)


def _chunks_from_document(document: ParsedDocument, markdown: str) -> Iterable[_Chunk]:
    if document.sections:
        chunks = list(_chunks_from_structured_sections(document, markdown))
        if chunks:
            yield from chunks
            return
    yield from _chunks_from_markdown(
        document_id=document.document_id,
        title=document.title,
        markdown=markdown,
        source_type="parsed",
        source_path=document.source_path,
    )


def _chunks_from_structured_sections(document: ParsedDocument, markdown: str) -> Iterable[_Chunk]:
    chunk_index = 0
    for idx, section in enumerate(document.sections):
        title = str(
            section.get("title")
            or section.get("heading")
            or section.get("section_title")
            or f"Section {idx + 1}"
        )
        content = str(section.get("markdown") or section.get("text") or section.get("content") or "").strip()
        if not content:
            continue
        level = _int_or_default(section.get("level") or section.get("heading_level"), 0)
        start_line = _int_or_default(section.get("start_line") or section.get("line_start"), 1)
        for part, part_start, part_end in _split_long_text(content, MAX_CHUNK_CHARS, start_line):
            stripped = part.strip()
            if not stripped:
                continue
            yield _Chunk(
                document_id=document.document_id,
                title=document.title,
                source_type="parsed",
                source_path=document.source_path,
                section_path=f"{document.title} > {title}",
                chunk_index=chunk_index,
                content=stripped,
                start_line=part_start,
                end_line=_int_or_default(section.get("end_line") or section.get("line_end"), part_end),
                heading_level=level,
                content_hash=_hash_text(stripped),
            )
            chunk_index += 1


def _document_search_markdown(document: ParsedDocument) -> str:
    source = Path(document.source_path)
    if document.source_type in {"markdown", "text"} and source.exists():
        return _read_text(source)
    return document.markdown


def _chunks_from_analysis(analysis: AnalysisResult, source_path: str) -> Iterable[_Chunk]:
    yield from _chunks_from_markdown(
        document_id=analysis.document_id,
        title=analysis.title,
        markdown=_analysis_markdown(analysis),
        source_type="analysis",
        source_path=source_path,
    )


def _analysis_markdown(analysis: AnalysisResult) -> str:
    lines = [
        f"# {analysis.title}",
        "",
        "## TL;DR",
        analysis.tldr,
        "",
        "## Research Question",
        analysis.research_question,
        "",
        "## Method",
        analysis.method,
        "",
        "## Contributions",
        *_bullets(analysis.contributions),
        "",
        "## Evidence",
        *_bullets(analysis.evidence),
        "",
        "## Limitations",
        *_bullets(analysis.limitations),
        "",
        "## Concepts",
        *_bullets(analysis.concepts),
        "",
        "## Related Work",
        *_bullets(analysis.related_work),
        "",
        "## Claims",
        *_bullets(analysis.claims),
        "",
        "## Datasets",
        *_bullets(analysis.datasets),
        "",
        "## Metrics",
        *_bullets(analysis.metrics),
        "",
        "## Key Figures",
        *_bullets(analysis.key_figures),
        "",
        "## Open Questions",
        *_bullets(analysis.open_questions),
    ]
    return "\n".join(lines)


def _chunks_from_markdown(
    *,
    document_id: str,
    title: str,
    markdown: str,
    source_type: str,
    source_path: str,
) -> Iterable[_Chunk]:
    sections = _split_markdown_sections(markdown)
    chunk_index = 0
    for section in sections:
        for part, start_line, end_line in _split_long_text(section.content, MAX_CHUNK_CHARS, section.start_line):
            stripped = part.strip()
            if not stripped:
                continue
            yield _Chunk(
                document_id=document_id,
                title=title,
                source_type=source_type,
                source_path=source_path,
                section_path=section.section_path or title,
                chunk_index=chunk_index,
                content=stripped,
                start_line=start_line,
                end_line=end_line,
                heading_level=section.heading_level,
                content_hash=_hash_text(stripped),
            )
            chunk_index += 1


@dataclass(frozen=True)
class _MarkdownSection:
    section_path: str
    content: str
    start_line: int
    end_line: int
    heading_level: int


def _split_markdown_sections(markdown: str) -> list[_MarkdownSection]:
    sections: list[tuple[str, list[str], int, int, int]] = []
    heading_stack: list[tuple[int, str]] = []
    current_title = "Document"
    current_lines: list[str] = []
    current_start = 1
    current_level = 0

    def flush(end_line: int) -> None:
        nonlocal current_lines, current_start
        text = "\n".join(current_lines).strip()
        if text:
            sections.append((current_title, current_lines, current_start, end_line, current_level))
        current_lines = []

    lines = markdown.splitlines()
    for lineno, line in enumerate(lines, start=1):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            flush(lineno - 1)
            level = len(match.group(1))
            heading = match.group(2).strip()
            heading_stack[:] = [(lvl, title) for lvl, title in heading_stack if lvl < level]
            heading_stack.append((level, heading))
            current_title = " > ".join(title for _, title in heading_stack)
            current_level = level
            current_start = lineno
            current_lines.append(line)
        else:
            if not current_lines:
                current_start = lineno
            current_lines.append(line)
    flush(len(lines))
    if not sections and markdown.strip():
        return [_MarkdownSection("Document", markdown.strip(), 1, len(lines) or 1, 0)]
    return [
        _MarkdownSection(title, "\n".join(section_lines), start, end, level)
        for title, section_lines, start, end, level in sections
    ]


def _split_long_text(text: str, max_chars: int, start_line: int) -> list[tuple[str, int, int]]:
    if len(text) <= max_chars:
        return [(text, start_line, start_line + max(text.count("\n"), 0))]
    paragraphs = re.split(r"(\n\s*\n)", text)
    chunks: list[tuple[str, int, int]] = []
    current: list[str] = []
    current_len = 0
    current_start = start_line
    cursor_line = start_line
    for paragraph in paragraphs:
        if not paragraph:
            continue
        paragraph_start = cursor_line
        cursor_line += paragraph.count("\n")
        if paragraph.strip():
            cursor_line += 1 if "\n" not in paragraph else 0
        if not paragraph.strip():
            continue
        paragraph = paragraph.strip()
        if current and current_len + len(paragraph) + 2 > max_chars:
            text_chunk = "\n\n".join(current)
            chunks.append((text_chunk, current_start, current_start + text_chunk.count("\n")))
            current = []
            current_len = 0
            current_start = paragraph_start
        if len(paragraph) > max_chars:
            for i in range(0, len(paragraph), max_chars):
                part = paragraph[i : i + max_chars]
                chunks.append((part, paragraph_start, paragraph_start + part.count("\n")))
        else:
            if not current:
                current_start = paragraph_start
            current.append(paragraph)
            current_len += len(paragraph) + 2
    if current:
        text_chunk = "\n\n".join(current)
        chunks.append((text_chunk, current_start, current_start + text_chunk.count("\n")))
    return chunks


def _dedupe_hits(hits: list[SearchHit], top_k: int) -> list[SearchHit]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[SearchHit] = []
    for hit in hits:
        key = (hit.document_id, hit.source_type, hit.section_path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
        if len(deduped) >= top_k:
            break
    return deduped


def _hit_from_row(row: sqlite3.Row, reason: str) -> SearchHit:
    return SearchHit(
        chunk_id=int(row["chunk_id"]),
        document_id=str(row["document_id"]),
        title=str(row["title"]),
        source_type=str(row["source_type"]),
        source_path=str(row["source_path"]),
        section_path=str(row["section_path"]),
        chunk_index=int(row["chunk_index"]),
        content=str(row["content"]),
        score=float(row["score"]),
        start_line=int(row["start_line"]),
        end_line=int(row["end_line"]),
        rank_score=0.0,
        match_reason=reason,
    )


def _fts_query(query: str) -> str:
    terms = _query_terms(query)
    if not terms:
        return f'"{query.replace(chr(34), chr(34) + chr(34))}"'
    return " OR ".join(f'"{term.replace(chr(34), chr(34) + chr(34))}"' for term in terms[:10])


def _query_variants(query: str) -> dict[str, str]:
    terms = _query_terms(query)
    keywords = " ".join(terms[:12])
    return {
        "phrase": query.strip(),
        "keywords": keywords or query.strip(),
    }


def _query_terms(query: str) -> list[str]:
    terms = re.findall(r"[\w\u4e00-\u9fff]+", query.lower(), flags=re.UNICODE)
    return [term for term in terms if len(term) > 1 and term not in QUESTION_STOPWORDS]


def _with_rank_score(hit: SearchHit, query: str) -> SearchHit:
    terms = _query_terms(query)
    haystacks = {
        "title": hit.title.lower(),
        "section": hit.section_path.lower(),
        "content": hit.content.lower(),
    }
    title_hits = sum(1 for term in terms if term in haystacks["title"])
    section_hits = sum(1 for term in terms if term in haystacks["section"])
    content_hits = sum(1 for term in terms if term in haystacks["content"])
    coverage = content_hits / max(len(terms), 1)
    bm25_bonus = max(0.0, 10.0 - min(abs(hit.score), 10.0)) if hit.score < 100 else 0.0
    reason_bonus = {
        "phrase_fts": 3.0,
        "keyword_fts": 2.0,
        "title_section_like": 4.0,
        "content_like": 1.0,
    }.get(hit.match_reason, 0.0)
    rank_score = (
        bm25_bonus
        + reason_bonus
        + title_hits * 4.0
        + section_hits * 3.0
        + content_hits * 1.2
        + coverage * 5.0
        + SOURCE_WEIGHTS.get(hit.source_type, 0.0)
    )
    return SearchHit(
        chunk_id=hit.chunk_id,
        document_id=hit.document_id,
        title=hit.title,
        source_type=hit.source_type,
        source_path=hit.source_path,
        section_path=hit.section_path,
        chunk_index=hit.chunk_index,
        content=hit.content,
        score=hit.score,
        start_line=hit.start_line,
        end_line=hit.end_line,
        rank_score=rank_score,
        match_reason=hit.match_reason,
    )


def _normalize_source(source: str) -> str:
    if source not in SOURCE_CHOICES:
        raise ValueError(f"source must be one of {', '.join(sorted(SOURCE_CHOICES))}")
    return source


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _title_from_markdown(markdown: str) -> str | None:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def _document_id_from_path(path: Path, vault_dir: Path) -> str:
    try:
        return path.relative_to(vault_dir).with_suffix("").as_posix()
    except ValueError:
        return path.with_suffix("").as_posix()


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- Not available."]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _int_or_default(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
