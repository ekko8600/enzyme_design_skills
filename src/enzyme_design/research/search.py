"""Network search adapters for topic exploration."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


@dataclass
class SearchResult:
    title: str
    url: str
    summary: str = ""
    source: str = "web"
    doi: str = ""
    published: str = ""
    authors: list[str] | None = None
    score: float = 0.0
    pdf_url: str = ""
    requires_fulltext: bool = False


def search_crossref(query: str, limit: int = 5) -> list[SearchResult]:
    """Search Crossref works API for scholarly metadata."""
    url = f"https://api.crossref.org/works?query={quote_plus(query)}&rows={limit}"
    payload = _request_json(url, source="crossref")
    results: list[SearchResult] = []
    for item in payload.get("message", {}).get("items", []):
        title = (item.get("title") or ["Untitled"])[0]
        doi = item.get("DOI")
        link = f"https://doi.org/{doi}" if doi else item.get("URL", "")
        abstract = _clean_abstract(item.get("abstract", ""))
        pdf = _find_pdf_link(item)
        results.append(
            SearchResult(
                title=title,
                url=link,
                summary=abstract,
                source="crossref",
                doi=doi or "",
                published=_extract_published(item),
                authors=_extract_authors(item),
                score=float(item.get("is-referenced-by-count", 0)),
                pdf_url=pdf,
                requires_fulltext=bool(pdf),
            )
        )
    return results


def search_semantic_scholar(query: str, limit: int = 5, api_key: str | None = None) -> list[SearchResult]:
    fields = "title,abstract,url,year,authors,citationCount,externalIds,openAccessPdf"
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={quote_plus(query)}&limit={limit}&fields={fields}"
    headers = {"x-api-key": api_key} if api_key else None
    payload = _request_json(url, source="semantic-scholar", headers=headers)
    results: list[SearchResult] = []
    for item in payload.get("data", []):
        doi = (item.get("externalIds") or {}).get("DOI", "")
        pdf_url = ((item.get("openAccessPdf") or {}).get("url")) or ""
        results.append(
            SearchResult(
                title=item.get("title", "Untitled"),
                url=item.get("url") or (f"https://doi.org/{doi}" if doi else ""),
                summary=item.get("abstract") or "",
                source="semantic-scholar",
                doi=doi,
                published=str(item.get("year") or ""),
                authors=[a.get("name", "") for a in item.get("authors", []) if a.get("name")],
                score=float(item.get("citationCount") or 0),
                pdf_url=pdf_url,
                requires_fulltext=bool(pdf_url),
            )
        )
    return results


def search_arxiv(query: str, limit: int = 5) -> list[SearchResult]:
    url = (
        "http://export.arxiv.org/api/query?search_query=all:"
        f"{quote_plus(query)}&start=0&max_results={limit}&sortBy=relevance&sortOrder=descending"
    )
    xml_text = _request_text(url, source="arxiv")
    entries = xml_text.split("<entry>")[1:]
    results: list[SearchResult] = []
    for entry in entries:
        title = _extract_xml_tag(entry, "title")
        summary = _extract_xml_tag(entry, "summary")
        page_url = _extract_xml_tag(entry, "id")
        published = _extract_xml_tag(entry, "published")[:10]
        authors = re.findall(r"<name>(.*?)</name>", entry, flags=re.DOTALL)
        arxiv_id = page_url.rsplit("/", 1)[-1] if page_url else ""
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else ""
        results.append(
            SearchResult(
                title=" ".join(title.split()) or "Untitled",
                url=page_url,
                summary=" ".join(summary.split()),
                source="arxiv",
                published=published,
                authors=[" ".join(a.split()) for a in authors],
                score=0.0,
                pdf_url=pdf_url,
                requires_fulltext=bool(pdf_url),
            )
        )
    return results


def search_pubmed(query: str, limit: int = 5) -> list[SearchResult]:
    esearch_url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&retmode=json&retmax={limit}&sort=relevance&term={quote_plus(query)}"
    )
    payload = _request_json(esearch_url, source="pubmed")
    ids = payload.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    efetch_url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        f"?db=pubmed&retmode=xml&id={','.join(ids)}"
    )
    xml_text = _request_text(efetch_url, source="pubmed")
    return _parse_pubmed_xml(xml_text)


def search_openalex(query: str, limit: int = 5) -> list[SearchResult]:
    url = f"https://api.openalex.org/works?search={quote_plus(query)}&per-page={limit}"
    payload = _request_json(url, source="openalex")
    results: list[SearchResult] = []
    for item in payload.get("results", []):
        doi = str(item.get("doi") or "").replace("https://doi.org/", "")
        primary_loc = item.get("primary_location") or {}
        pdf_url = ((primary_loc.get("pdf_url") or "") if isinstance(primary_loc, dict) else "")
        venue_url = (primary_loc.get("landing_page_url") or "") if isinstance(primary_loc, dict) else ""
        open_access = bool(item.get("open_access", {}).get("is_oa"))
        results.append(
            SearchResult(
                title=item.get("title", "Untitled"),
                url=venue_url or (f"https://doi.org/{doi}" if doi else ""),
                summary=item.get("abstract_inverted_index") and _expand_inverted_abstract(item["abstract_inverted_index"]) or "",
                source="openalex",
                doi=doi,
                published=str(item.get("publication_year") or ""),
                authors=[a.get("author", {}).get("display_name", "") for a in item.get("authorships", []) if a.get("author", {}).get("display_name")],
                score=float(item.get("cited_by_count") or 0),
                pdf_url=pdf_url,
                requires_fulltext=bool(pdf_url and open_access),
            )
        )
    return results


def rank_results(results: list[SearchResult], topic: str) -> list[SearchResult]:
    topic_terms = {term.lower() for term in topic.split() if term.strip()}
    scored: list[tuple[float, SearchResult]] = []
    for item in results:
        text = f"{item.title} {item.summary}".lower()
        relevance = sum(1 for t in topic_terms if t in text)
        has_pdf = 2 if item.pdf_url else 0
        fulltext_bonus = 1 if item.requires_fulltext else 0
        total = relevance * 3 + has_pdf + fulltext_bonus + min(item.score / 200, 5)
        scored.append((total, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


def _request_json(url: str, *, source: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    body = _request_text(url, source=source, headers=headers)
    return json.loads(body) if body else {}


def _request_text(url: str, *, source: str, headers: dict[str, str] | None = None) -> str:
    attempts = 4
    base_sleep = 1.5
    for attempt in range(attempts):
        request_headers = {"User-Agent": "enzyme-design/0.1", **(headers or {})}
        req = Request(url, headers=request_headers)
        try:
            with urlopen(req, timeout=30) as response:  # noqa: S310
                return response.read().decode("utf-8", errors="ignore")
        except HTTPError as exc:
            code = exc.code
            if code in {429, 500, 502, 503, 504} and attempt < attempts - 1:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                delay = float(retry_after) if (retry_after and retry_after.isdigit()) else base_sleep * (2**attempt)
                time.sleep(delay)
                continue
            if source == "semantic-scholar" and code == 429:
                return ""
            return ""
        except URLError:
            if attempt < attempts - 1:
                time.sleep(base_sleep * (2**attempt))
                continue
            return ""
    return ""

# ... rest unchanged helpers

def _extract_authors(item: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for author in item.get("author", []):
        given = author.get("given", "").strip()
        family = author.get("family", "").strip()
        full = " ".join(part for part in [given, family] if part)
        if full:
            names.append(full)
    return names


def _extract_published(item: dict[str, Any]) -> str:
    parts = (item.get("published-print", {}).get("date-parts") or item.get("published-online", {}).get("date-parts") or [])
    if not parts:
        return ""
    values = parts[0]
    return "-".join(str(v) for v in values)


def _clean_abstract(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    for tag in ["<jats:p>", "</jats:p>", "<jats:title>", "</jats:title>"]:
        cleaned = cleaned.replace(tag, " ")
    return " ".join(unescape(cleaned).split())


def _find_pdf_link(item: dict[str, Any]) -> str:
    for link in item.get("link", []):
        content_type = str(link.get("content-type", "")).lower()
        if "pdf" in content_type:
            return str(link.get("URL", ""))
    return ""


def _extract_xml_tag(entry: str, tag: str) -> str:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", entry, flags=re.DOTALL)
    if not match:
        return ""
    return unescape(match.group(1).strip())


def _parse_pubmed_xml(xml_text: str) -> list[SearchResult]:
    articles = xml_text.split("<PubmedArticle>")[1:]
    results: list[SearchResult] = []
    for article in articles:
        pmid = _extract_xml_tag(article, "PMID")
        title = _extract_xml_tag(article, "ArticleTitle") or "Untitled"
        abstract_parts = re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", article, flags=re.DOTALL)
        abstract = " ".join(" ".join(p.split()) for p in abstract_parts)
        pub_year = _extract_xml_tag(article, "Year")
        doi_match = re.search(r'<ArticleId IdType="doi">(.*?)</ArticleId>', article, flags=re.DOTALL)
        doi = doi_match.group(1).strip() if doi_match else ""
        authors = re.findall(r"<ForeName>(.*?)</ForeName>\s*<LastName>(.*?)</LastName>", article, flags=re.DOTALL)
        author_names = [f"{' '.join(fn.split())} {' '.join(ln.split())}" for fn, ln in authors]
        results.append(SearchResult(title=" ".join(title.split()), url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else (f"https://doi.org/{doi}" if doi else ""), summary=abstract, source="pubmed", doi=doi, published=pub_year, authors=author_names, score=0.0, pdf_url=""))
    return results


def _expand_inverted_abstract(index: dict[str, list[int]]) -> str:
    if not index:
        return ""
    length = max((max(positions) for positions in index.values() if positions), default=-1) + 1
    words = [""] * length
    for token, positions in index.items():
        for pos in positions:
            if 0 <= pos < length:
                words[pos] = token
    return " ".join(word for word in words if word).strip()
