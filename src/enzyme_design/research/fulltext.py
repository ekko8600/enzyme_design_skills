"""Helpers to fetch and store full-text content for discovered papers."""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from enzyme_design.config import Settings
from enzyme_design.parsers.pdf_text_parser import PdfTextParser
from enzyme_design.research.search import SearchResult


@dataclass
class FullTextFetchResult:
    """Traceable result for a full-text retrieval attempt."""

    markdown: str = ""
    status: str = "not_attempted"
    source: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "source": self.source,
            "error": self.error,
        }


def fetch_fulltext(settings: Settings, result: SearchResult, require_fulltext: bool = False) -> FullTextFetchResult:
    """Fetch full text with status metadata instead of silent best-effort behavior."""
    errors: list[str] = []
    if result.pdf_url:
        try:
            markdown = _markdown_from_pdf_url(result.pdf_url)
        except Exception as exc:  # noqa: BLE001 - keep exploration moving but record the failure.
            markdown = ""
            errors.append(f"pdf: {exc}")
        if markdown:
            return FullTextFetchResult(markdown=markdown, status="retrieved", source=result.pdf_url)

    if result.url:
        try:
            web_text = _text_from_webpage(result.url)
        except Exception as exc:  # noqa: BLE001 - keep exploration moving but record the failure.
            web_text = ""
            errors.append(f"web: {exc}")
        if web_text:
            return FullTextFetchResult(
                markdown=f"# {result.title}\n\n## Full Text (web extract)\n\n{web_text}",
                status="retrieved",
                source=result.url,
            )

    if require_fulltext:
        return FullTextFetchResult(
            markdown="## Full Text Fetch Status\n\n- Required: Yes (OA candidate)\n- Retrieved: No\n- Action: retry later or provide institutional access.",
            status="missing_required",
            source=result.pdf_url or result.url,
            error=" | ".join(errors),
        )
    if errors:
        return FullTextFetchResult(status="failed", source=result.pdf_url or result.url, error=" | ".join(errors))
    return FullTextFetchResult(status="not_available", source=result.pdf_url or result.url)


def fetch_fulltext_markdown(settings: Settings, result: SearchResult, require_fulltext: bool = False) -> str:
    return fetch_fulltext(settings, result, require_fulltext=require_fulltext).markdown


def _markdown_from_pdf_url(url: str) -> str:
    request = Request(url, headers={"User-Agent": "enzyme-design/0.1"})
    with urlopen(request, timeout=60) as response:  # noqa: S310
        blob = response.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        handle.write(blob)
        temp_path = Path(handle.name)
    try:
        parsed = PdfTextParser().parse(temp_path)
        return parsed.markdown
    except Exception:
        return ""
    finally:
        temp_path.unlink(missing_ok=True)


def _text_from_webpage(url: str) -> str:
    request = Request(url, headers={"User-Agent": "enzyme-design/0.1"})
    with urlopen(request, timeout=30) as response:  # noqa: S310
        html = response.read().decode("utf-8", errors="ignore")
    content = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"<style.*?</style>", " ", content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"<[^>]+>", " ", content)
    content = re.sub(r"\s+", " ", content).strip()
    return content[:40000]
