"""PaddleOCR / PP-StructureV3 parser adapter."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from enzyme_design.config import Settings
from enzyme_design.parsers.base import DocumentParser
from enzyme_design.schema import ParsedDocument, stable_document_id


class PaddleOCRParser(DocumentParser):
    """OCR-heavy fallback parser for scanned or image-based PDFs."""

    backend_name = "paddleocr"

    def __init__(self, settings: Settings):
        self.settings = settings

    def parse(self, path: Path) -> ParsedDocument:
        command = shutil.which(self.settings.paddleocr_command)
        if command is None:
            raise RuntimeError(
                f"PaddleOCR command '{self.settings.paddleocr_command}' was not found. "
                "Install PaddleOCR or use a different parser backend."
            )
        output_dir = self.settings.parsed_dir / stable_document_id(str(path)) / "paddleocr_raw"
        output_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [command, "pp_structurev3", "--input", str(path), "--output", str(output_dir)],
            check=True,
            text=True,
            capture_output=True,
        )
        markdown_files = sorted(output_dir.rglob("*.md"))
        markdown = markdown_files[0].read_text(encoding="utf-8") if markdown_files else ""
        return ParsedDocument(
            document_id=stable_document_id(str(path), markdown or path.read_bytes()),
            source_path=str(path),
            source_type="pdf",
            title=path.stem,
            markdown=markdown or f"# {path.stem}\n\nPaddleOCR produced no Markdown output.",
            parser_backend=self.backend_name,
            metadata={"filename": path.name, "paddleocr_output_dir": str(output_dir)},
        )
