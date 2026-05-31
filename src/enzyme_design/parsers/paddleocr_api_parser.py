"""PaddleOCR HTTP API parser adapter.

Sends scanned/image-based PDFs to a remote PaddleOCR API service and
receives parsed Markdown back. Replaces the local CLI-based approach
when PADDLEOCR_API_URL is configured.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from enzyme_design.config import Settings
from enzyme_design.parsers.base import DocumentParser
from enzyme_design.schema import ParsedDocument, stable_document_id


class PaddleOCRApiParser(DocumentParser):
    backend_name = "paddleocr-api"

    def __init__(self, settings: Settings):
        if not settings.paddleocr_api_url:
            raise RuntimeError(
                "PADDLEOCR_API_URL is required for PaddleOCR API parsing. "
                "Set the environment variable or use --parser paddleocr for local CLI."
            )
        self.api_url = settings.paddleocr_api_url.rstrip("/")
        self.api_key = settings.paddleocr_api_key

    def parse(self, path: Path) -> ParsedDocument:
        files = {"file": (path.name, path.read_bytes(), "application/pdf")}
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            import requests  # noqa: PLC0415 - optional dependency
        except ImportError:
            raise RuntimeError(
                "requests is required for HTTP API parsers. "
                "Install with: pip install enzyme-design[http]"
            ) from None

        response = requests.post(
            f"{self.api_url}/parse",
            files=files,
            headers=headers,
            params={"structure": "v3"},
            timeout=300,
        )
        response.raise_for_status()
        data = response.json()

        title = _extract_title(data) or path.stem
        markdown = _extract_markdown(data)

        return ParsedDocument(
            document_id=stable_document_id(str(path), markdown or path.read_bytes()),
            source_path=str(path),
            source_type="pdf",
            title=title,
            markdown=markdown or f"# {path.stem}\n\nPaddleOCR API returned no Markdown content.",
            parser_backend=self.backend_name,
            metadata={
                "filename": path.name,
                "api_url": self.api_url,
            },
            raw_backend_output=data,
        )


def _extract_title(data: dict[str, Any]) -> str | None:
    for key in ("title", "document_title", "filename", "name"):
        if key in data:
            return str(data[key])
    content = data.get("content")
    if isinstance(content, list) and content:
        for item in content:
            if isinstance(item, dict) and item.get("type") == "title":
                return str(item.get("text", ""))
    return None


def _extract_markdown(data: dict[str, Any]) -> str:
    for key in ("markdown", "md", "text", "content"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val
    result = data.get("result")
    if isinstance(result, dict):
        for key in ("markdown", "md", "text"):
            val = result.get(key)
            if isinstance(val, str) and val.strip():
                return val
        pages = result.get("pages")
        if isinstance(pages, list):
            parts = []
            for i, page in enumerate(pages, 1):
                if isinstance(page, dict):
                    text = page.get("text") or page.get("markdown") or ""
                    if text.strip():
                        parts.append(f"## Page {i}\n\n{text.strip()}")
            if parts:
                return "\n\n".join(parts)
    return ""
