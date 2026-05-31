"""Single-paper analysis service."""

from __future__ import annotations

from enzyme_design.llm.base import LLMProvider
from enzyme_design.schema import AnalysisResult, ParsedDocument


ANALYSIS_SYSTEM_PROMPT = """You are a rigorous research assistant building a personal literature wiki.
Return only valid JSON with keys: title, tldr, research_question, method,
contributions, evidence, limitations, concepts, related_work, claims, datasets,
metrics, key_figures, open_questions. Keep claims traceable to the provided
document text. If information is missing, say so.
"""


class PaperAnalyzer:
    """Analyze parsed literature documents into a wiki-friendly schema."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def analyze(self, document: ParsedDocument) -> AnalysisResult:
        snippet = document.markdown[:24000]
        payload = self.provider.structured_chat(
            [
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Title: {document.title}\nDocument ID: {document.document_id}\n\n{snippet}",
                },
            ],
            temperature=0.1,
        )
        return AnalysisResult(
            document_id=document.document_id,
            title=str(payload.get("title") or document.title),
            tldr=str(payload.get("tldr") or ""),
            research_question=str(payload.get("research_question") or ""),
            method=str(payload.get("method") or ""),
            contributions=_as_list(payload.get("contributions")),
            evidence=_as_list(payload.get("evidence")),
            limitations=_as_list(payload.get("limitations")),
            concepts=_as_list(payload.get("concepts")),
            related_work=_as_list(payload.get("related_work")),
            source_ids=[document.document_id],
            model=getattr(self.provider, "model", None),
            claims=_as_list(payload.get("claims")),
            datasets=_as_list(payload.get("datasets")),
            metrics=_as_list(payload.get("metrics")),
            key_figures=_as_list(payload.get("key_figures")),
            open_questions=_as_list(payload.get("open_questions")),
        )


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]
