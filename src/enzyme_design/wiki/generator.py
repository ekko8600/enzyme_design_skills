"""Markdown wiki generator."""

from __future__ import annotations

from pathlib import Path

from enzyme_design.schema import AnalysisResult, ParsedDocument
from enzyme_design.storage.index import LiteratureIndex


class WikiBuilder:
    """Generate Obsidian-compatible Markdown pages from analyzed documents."""

    def __init__(self, vault_dir: Path, index: LiteratureIndex):
        self.vault_dir = vault_dir
        self.index = index

    def build_all(self) -> list[Path]:
        paths: list[Path] = []
        topics: dict[str, list[AnalysisResult]] = {}
        for document, analysis in self.index.iter_analyzed():
            paper_path = self.write_paper_page(document, analysis)
            self.index.set_wiki_path(document.document_id, paper_path)
            paths.append(paper_path)
            for concept in analysis.concepts:
                topics.setdefault(concept, []).append(analysis)
        for topic, analyses in topics.items():
            paths.append(self.write_topic_page(topic, analyses))
        paths.append(self.write_open_questions_page())
        paths.extend(self._latest_deep_synthesis_pages())
        paths.append(self.write_index_page(paths))
        return paths

    def write_paper_page(self, document: ParsedDocument, analysis: AnalysisResult) -> Path:
        path = self.vault_dir / "papers" / f"{document.document_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# {analysis.title}",
            "",
            f"- Document ID: `{document.document_id}`",
            f"- Source: `{document.source_path}`",
            f"- Parser: `{document.parser_backend}`",
            f"- Model: `{analysis.model or 'unknown/local'}`",
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
            *_bullets([f"[[{concept}]]" for concept in analysis.concepts]),
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
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def write_topic_page(self, topic: str, analyses: list[AnalysisResult]) -> Path:
        slug = _slug(topic)
        path = self.vault_dir / "topics" / f"{slug}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# {topic}",
            "",
            "## Representative Papers",
        ]
        for analysis in analyses:
            lines.append(f"- [[{analysis.document_id}]] — {analysis.title}")
        lines.extend(["", "## Open Questions", "- Add manually or generate with `enzyme-design synthesize`."])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def write_open_questions_page(self) -> Path:
        path = self.vault_dir / "topics" / "open-questions.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Open Questions", ""]
        found = False
        for _, analysis in self.index.iter_analyzed():
            for question in analysis.open_questions:
                found = True
                lines.append(f"- {question} — [[{analysis.document_id}]]")
        if not found:
            lines.append("- Not available.")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def write_index_page(self, paths: list[Path]) -> Path:
        path = self.vault_dir / "index.md"
        lines = ["# enzyme-design", "", "## Generated Pages"]
        for generated in sorted(paths):
            rel = generated.relative_to(self.vault_dir)
            lines.append(f"- [[{rel.with_suffix('').as_posix()}]]")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def _latest_deep_synthesis_pages(self) -> list[Path]:
        logs_dir = self.vault_dir / "research_logs"
        if not logs_dir.exists():
            return []
        return sorted(logs_dir.glob("*/deep_synthesis.md"))


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- Not available."]


def _slug(value: str) -> str:
    return "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())[:80]
