"""Deterministic local provider used for dry runs and tests."""

from __future__ import annotations

from typing import Any

from enzyme_design.llm.base import LLMProvider


class MockProvider(LLMProvider):
    """Return predictable structured analysis without network calls."""

    def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.2) -> str:
        return "Local mock response."

    def structured_chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        user_text = messages[-1]["content"] if messages else ""
        title = "Untitled Document"
        for line in user_text.splitlines():
            if line.startswith("Title:"):
                title = line.partition(":")[2].strip() or title
        return {
            "title": title,
            "tldr": "Local dry-run summary generated without an external LLM.",
            "research_question": "What question does this document address?",
            "method": "Method details require full model analysis.",
            "contributions": ["Prepared a structured analysis placeholder."],
            "evidence": ["Derived from the parsed document text."],
            "limitations": ["Dry-run mode does not perform deep semantic analysis."],
            "concepts": ["enzyme-design"],
            "related_work": [],
            "claims": ["Dry-run placeholder claim; use remote analysis for evidence-grounded claims."],
            "datasets": [],
            "metrics": [],
            "key_figures": [],
            "open_questions": ["What additional evidence should be reviewed with a full model analysis?"],
        }
