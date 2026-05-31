"""MinerU HTTP API parser adapter.

Sends PDF files to a remote MinerU API service and receives parsed
Markdown/JSON back. Replaces the local CLI-based approach when
MINERU_API_URL is configured.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from enzyme_design.config import Settings
from enzyme_design.parsers.base import DocumentParser
from enzyme_design.schema import ParsedDocument, stable_document_id


class MinerUApiParser(DocumentParser):
    backend_name = "mineru-api"

    def __init__(self, settings: Settings):
        if not settings.mineru_api_url:
            raise RuntimeError(
                "MINERU_API_URL is required for MinerU API parsing. "
                "Set the environment variable or use --parser mineru for local CLI."
            )
        self.api_url = settings.mineru_api_url.rstrip("/")
        self.api_key = settings.mineru_api_key

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
            markdown=markdown or f"# {path.stem}\n\nMinerU API returned no Markdown content.",
            parser_backend=self.backend_name,
            metadata={
                "filename": path.name,
                "api_url": self.api_url,
            },
            raw_backend_output=data,
        )


def _extract_title(data: dict[str, Any]) -> str | None:
    for key in ("title", "document_title", "name"):
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
    content = data.get("content")
    if isinstance(content, str) and content.strip():
        return content
    return ""
