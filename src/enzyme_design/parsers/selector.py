"""Parser selection and fallback logic."""

from __future__ import annotations

from pathlib import Path

from enzyme_design.config import Settings
from enzyme_design.parsers.base import MarkdownParser, TextParser
from enzyme_design.parsers.mineru_api_parser import MinerUApiParser
from enzyme_design.parsers.mineru_parser import MinerUParser
from enzyme_design.parsers.paddleocr_api_parser import PaddleOCRApiParser
from enzyme_design.parsers.paddleocr_parser import PaddleOCRParser
from enzyme_design.parsers.pdf_text_parser import PdfTextParser
from enzyme_design.schema import ParsedDocument


class ParserSelector:
    def __init__(self, settings: Settings):
        self.settings = settings

    def parse(self, path: Path, backend: str = "auto") -> ParsedDocument:
        if not path.exists():
            raise FileNotFoundError(path)
        suffix = path.suffix.lower()
        requested = backend if backend != "auto" else self.settings.pdf_parser_backend
        if suffix in {".md", ".markdown"}:
            return MarkdownParser().parse(path)
        if suffix in {".txt"}:
            return TextParser().parse(path)
        if suffix == ".pdf":
            return self._parse_pdf(path, requested)
        raise ValueError(f"Unsupported input type: {path.suffix}")

    def _parse_pdf(self, path: Path, backend: str) -> ParsedDocument:
        backends = {
            "text": [PdfTextParser()],
            "pdf-text": [PdfTextParser()],
            "mineru": [MinerUParser(self.settings)],
            "mineru-api": [MinerUApiParser(self.settings)],
            "paddleocr": [PaddleOCRParser(self.settings)],
            "paddleocr-api": [PaddleOCRApiParser(self.settings)],
            "auto": [
                PdfTextParser(),
                MinerUApiParser(self.settings),
                PaddleOCRApiParser(self.settings),
                MinerUParser(self.settings),
                PaddleOCRParser(self.settings),
            ],
        }
        errors: list[str] = []
        for parser in backends.get(backend, backends["auto"]):
            try:
                return parser.parse(path)
            except Exception as exc:  # noqa: BLE001 - preserve fallback chain for agent workflows.
                errors.append(f"{parser.backend_name}: {exc}")
        raise RuntimeError("All PDF parsers failed: " + " | ".join(errors))
