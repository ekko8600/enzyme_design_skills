"""High-level safe workflows for the enzyme-design skill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from enzyme_design.analysis.paper import PaperAnalyzer
from enzyme_design.config import Settings
from enzyme_design.llm.deepseek import DeepSeekProvider
from enzyme_design.llm.mock import MockProvider
from enzyme_design.parsers.selector import ParserSelector
from enzyme_design.qa.answer import AnswerService
from enzyme_design.research.agent import ResearchAgent
from enzyme_design.retrieval.search_index import SearchIndex
from enzyme_design.storage.index import LiteratureIndex
from enzyme_design.wiki.generator import WikiBuilder


class WorkflowRunner:
    """Small orchestration layer for common agent-safe paths."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.ensure_directories()
        self.index = LiteratureIndex(settings.index_path, settings.parsed_dir)

    def file(
        self,
        path: Path,
        *,
        parser: str = "auto",
        analyze: bool = False,
        dry_run: bool = False,
        build_wiki: bool = False,
    ) -> dict[str, Any]:
        document = ParserSelector(self.settings).parse(path, parser)
        parsed_path = self.index.add_document(document)
        search_index = SearchIndex(self.index, self.settings.vault_dir)
        search_index.rebuild(source="parsed")
        result: dict[str, Any] = {
            "document_id": document.document_id,
            "title": document.title,
            "parsed_path": str(parsed_path),
            "analysis_path": "",
            "wiki_paths": [],
        }
        if analyze:
            if not dry_run and not self.settings.allow_upload_private_notes_to_llm:
                raise PermissionError(
                    "Remote analysis of local documents is disabled by ENZYME_DESIGN_ALLOW_PRIVATE_UPLOAD=false."
                )
            provider = MockProvider() if dry_run else DeepSeekProvider(self.settings)
            analysis = PaperAnalyzer(provider).analyze(document)
            analysis_path = self.index.save_analysis(analysis)
            search_index.rebuild(source="analysis")
            result["analysis_path"] = str(analysis_path)
        if build_wiki:
            wiki_paths = WikiBuilder(self.settings.vault_dir, self.index).build_all()
            search_index.rebuild(source="wiki")
            result["wiki_paths"] = [str(path) for path in wiki_paths]
        return result

    def question(self, question: str, *, dry_run: bool = True, top_k: int = 8) -> str:
        search_index = SearchIndex(self.index, self.settings.vault_dir)
        if search_index.count_chunks() == 0:
            search_index.rebuild()
        if not dry_run and not self.settings.allow_upload_private_notes_to_llm:
            raise PermissionError(
                "Remote question answering over local knowledge requires "
                "ENZYME_DESIGN_ALLOW_PRIVATE_UPLOAD=true; it is currently disabled."
            )
        provider = MockProvider() if dry_run else DeepSeekProvider(self.settings)
        answer = AnswerService(search_index, provider).ask(question, top_k=top_k)
        if "No local evidence matched" in answer or "No matching local chunks" in answer:
            return answer + "\n\n## Next Step\n\nLocal evidence was insufficient. Use `enzyme-design explore --topic \"<topic>\" --depth deep --allow-network` or the topic workflow to collect new source-traceable literature; network search is enabled by default unless disabled in settings."
        return answer

    def topic(self, topic: str, *, allow_network: bool = False, depth: str = "standard") -> Path:
        return ResearchAgent(self.settings).explore(topic, allow_network=allow_network, depth=depth)
