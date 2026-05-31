"""MinerU PDF parser adapter.

This wrapper supports command-line MinerU installations without making MinerU a
hard dependency of the package. If the command is unavailable, callers can fall
back to PaddleOCR or the lightweight PDF text parser.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from enzyme_design.config import Settings
from enzyme_design.parsers.base import DocumentParser
from enzyme_design.schema import ParsedDocument, stable_document_id


class MinerUParser(DocumentParser):
    """Adapter around a local MinerU CLI that produces Markdown/JSON outputs."""

    backend_name = "mineru"

    def __init__(self, settings: Settings):
        self.settings = settings

    def parse(self, path: Path) -> ParsedDocument:
        command = shutil.which(self.settings.mineru_command)
        if command is None:
            raise RuntimeError(
                f"MinerU command '{self.settings.mineru_command}' was not found. "
                "Install MinerU or use --parser paddleocr/text."
            )
        output_dir = self.settings.parsed_dir / stable_document_id(str(path)) / "mineru_raw"
        output_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [command, "-p", str(path), "-o", str(output_dir)],
            check=True,
            text=True,
            capture_output=True,
        )
        markdown_files = sorted(output_dir.rglob("*.md"))
        json_files = sorted(output_dir.rglob("*.json"))
        markdown = markdown_files[0].read_text(encoding="utf-8") if markdown_files else ""
        raw = {}
        if json_files:
            try:
                raw = json.loads(json_files[0].read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                raw = {"raw_json_path": str(json_files[0])}
        return ParsedDocument(
            document_id=stable_document_id(str(path), markdown or path.read_bytes()),
            source_path=str(path),
            source_type="pdf",
            title=path.stem,
            markdown=markdown or f"# {path.stem}\n\nMinerU produced no Markdown output.",
            parser_backend=self.backend_name,
            metadata={"filename": path.name, "mineru_output_dir": str(output_dir)},
            raw_backend_output=raw,
        )
