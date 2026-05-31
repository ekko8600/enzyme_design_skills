"""Answer questions using local retrieved evidence and an LLM provider."""

from __future__ import annotations

from dataclasses import dataclass

from enzyme_design.llm.base import LLMProvider
from enzyme_design.llm.mock import MockProvider
from enzyme_design.retrieval.search_index import SearchHit, SearchIndex


ANSWER_SYSTEM_PROMPT = """You answer questions over a private personal literature wiki.
Use only the provided evidence snippets. Do not invent facts, papers, values,
methods, mutations, or conclusions. If the evidence is insufficient, say so.
Return Markdown with exactly these sections:
## Answer
## Evidence
## Confidence
## Gaps / Not Found
Every substantive claim must cite evidence ids like [E1]. Treat strong evidence
as direct support, supporting evidence as context, and weak evidence as
insufficient unless paired with stronger evidence.
"""


@dataclass(frozen=True)
class EvidenceItem:
    """A normalized evidence row passed to answer synthesis."""

    evidence_id: str
    title: str
    document_id: str
    source_type: str
    source_path: str
    section_path: str
    start_line: int
    end_line: int
    excerpt: str
    rank_score: float
    match_reason: str
    strength: str


@dataclass(frozen=True)
class EvidenceMatrix:
    """Grouped local evidence for one user question."""

    question: str
    items: list[EvidenceItem]

    @property
    def strong(self) -> list[EvidenceItem]:
        return [item for item in self.items if item.strength == "strong"]

    @property
    def supporting(self) -> list[EvidenceItem]:
        return [item for item in self.items if item.strength == "supporting"]

    @property
    def weak(self) -> list[EvidenceItem]:
        return [item for item in self.items if item.strength == "weak"]


class AnswerService:
    """Retrieve local chunks, then synthesize an evidence-grounded answer."""

    def __init__(self, search_index: SearchIndex, provider: LLMProvider):
        self.search_index = search_index
        self.provider = provider

    def ask(self, question: str, *, top_k: int = 8, source: str = "all") -> str:
        hits = self.search_index.search(question, top_k=top_k, source=source)
        matrix = build_evidence_matrix(question, hits)
        if isinstance(self.provider, MockProvider):
            return _dry_run_answer(matrix)
        if not matrix.items:
            return _empty_answer(question)
        context = _format_context(matrix)
        return self.provider.chat(
            [
                {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Question:\n{question}\n\nEvidence snippets:\n{context}",
                },
            ],
            temperature=0.1,
        )


def build_evidence_matrix(question: str, hits: list[SearchHit]) -> EvidenceMatrix:
    items = [
        EvidenceItem(
            evidence_id=f"E{idx}",
            title=hit.title,
            document_id=hit.document_id,
            source_type=hit.source_type,
            source_path=hit.source_path,
            section_path=hit.section_path,
            start_line=hit.start_line,
            end_line=hit.end_line,
            excerpt=hit.excerpt,
            rank_score=hit.rank_score,
            match_reason=hit.match_reason,
            strength=_strength(hit, idx),
        )
        for idx, hit in enumerate(hits, start=1)
    ]
    return EvidenceMatrix(question=question, items=items)


def _dry_run_answer(matrix: EvidenceMatrix) -> str:
    lines = [
        "## Answer",
        "",
        "Dry-run mode did not call a remote LLM. Review the Evidence Matrix below to answer the question.",
        "",
        "## Evidence",
    ]
    if matrix.items:
        lines.extend(["", "| ID | Strength | Score | Source | Section | Location | Match | Excerpt |", "| --- | --- | ---: | --- | --- | --- | --- | --- |"])
        for item in matrix.items:
            lines.extend(
                [
                    "| "
                    + " | ".join(
                        [
                            item.evidence_id,
                            item.strength,
                            f"{item.rank_score:.2f}",
                            f"`{item.source_type}`",
                            _escape_table(item.section_path),
                            f"`{item.source_path}:{item.start_line}`",
                            item.match_reason,
                            _escape_table(item.excerpt),
                        ]
                    )
                    + " |"
                ]
            )
    else:
        lines.append("- No local evidence matched the question.")
    lines.extend(
        [
            "",
            "## Confidence",
            "",
            "Not assessed in dry-run mode.",
            "",
            "## Gaps / Not Found",
            "",
            f"Question: {matrix.question}",
        ]
    )
    return "\n".join(lines)


def _empty_answer(question: str) -> str:
    return "\n".join(
        [
            "## Answer",
            "",
            "No answer can be grounded because the local search index returned no evidence.",
            "",
            "## Evidence",
            "",
            "- No matching local chunks.",
            "",
            "## Confidence",
            "",
            "Low.",
            "",
            "## Gaps / Not Found",
            "",
            f"No local evidence was found for: {question}",
        ]
    )


def _format_context(matrix: EvidenceMatrix) -> str:
    parts: list[str] = []
    for label, items in [
        ("Strong Evidence", matrix.strong),
        ("Supporting Evidence", matrix.supporting),
        ("Weak / Possibly Insufficient Evidence", matrix.weak),
    ]:
        if not items:
            continue
        parts.append(
            "\n".join([f"### {label}", *[_format_item_for_context(item) for item in items]])
        )
    return "\n\n".join(parts)


def _format_item_for_context(item: EvidenceItem) -> str:
    return "\n".join(
        [
            f"[{item.evidence_id}]",
            f"Strength: {item.strength}",
            f"Rank Score: {item.rank_score:.2f}",
            f"Match Reason: {item.match_reason}",
            f"Title: {item.title}",
            f"Document ID: {item.document_id}",
            f"Source Type: {item.source_type}",
            f"Source Path: {item.source_path}:{item.start_line}",
            f"Section: {item.section_path}",
            "Excerpt:",
            item.excerpt,
        ]
    )


def _strength(hit: SearchHit, idx: int) -> str:
    if hit.rank_score >= 12 or (idx <= 3 and hit.match_reason in {"phrase_fts", "title_section_like"}):
        return "strong"
    if hit.rank_score >= 7 or idx <= 6:
        return "supporting"
    return "weak"


def _escape_table(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")
