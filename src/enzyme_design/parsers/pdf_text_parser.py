"""Lightweight PDF text parser used before OCR-heavy fallbacks."""

from __future__ import annotations

from pathlib import Path
from importlib import import_module, util

from enzyme_design.parsers.base import DocumentParser
from enzyme_design.schema import ParsedDocument, stable_document_id


class PdfTextParser(DocumentParser):
    """Extract text from PDFs with pypdf when available."""

    backend_name = "pdf-text"

    def parse(self, path: Path) -> ParsedDocument:
        if util.find_spec("pypdf") is None:
            raise RuntimeError("Install pypdf or choose --parser mineru/paddleocr.")
        PdfReader = import_module("pypdf").PdfReader
        reader = PdfReader(str(path))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"## Page {index}\n\n{text.strip()}")
        markdown = f"# {path.stem}\n\n" + "\n\n".join(pages)
        if not pages:
            raise RuntimeError("PDF has no extractable text layer.")
        return ParsedDocument(
            document_id=stable_document_id(str(path), markdown),
            source_path=str(path),
            source_type="pdf",
            title=path.stem,
            markdown=markdown,
            parser_backend=self.backend_name,
            metadata={"filename": path.name, "pages": len(reader.pages)},
        )
