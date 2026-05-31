"""Parser interfaces and lightweight local parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from enzyme_design.schema import ParsedDocument, stable_document_id


class DocumentParser(ABC):
    """Base class for all parser adapters."""

    backend_name = "base"

    @abstractmethod
    def parse(self, path: Path) -> ParsedDocument:
        """Parse a document into the normalized schema."""


class MarkdownParser(DocumentParser):
    """Parse existing Markdown notes without external dependencies."""

    backend_name = "markdown"

    def parse(self, path: Path) -> ParsedDocument:
        markdown = path.read_text(encoding="utf-8")
        title = _title_from_markdown(markdown) or path.stem
        return ParsedDocument(
            document_id=stable_document_id(str(path), markdown),
            source_path=str(path),
            source_type="markdown",
            title=title,
            markdown=markdown,
            parser_backend=self.backend_name,
            metadata={"filename": path.name},
        )


class TextParser(DocumentParser):
    """Parse plain text files as Markdown-compatible content."""

    backend_name = "text"

    def parse(self, path: Path) -> ParsedDocument:
        text = path.read_text(encoding="utf-8")
        return ParsedDocument(
            document_id=stable_document_id(str(path), text),
            source_path=str(path),
            source_type="text",
            title=path.stem,
            markdown=text,
            parser_backend=self.backend_name,
            metadata={"filename": path.name},
        )


def _title_from_markdown(markdown: str) -> str | None:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None
