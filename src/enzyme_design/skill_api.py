"""Skill-first orchestration API (CLI-free entrypoints)."""

from __future__ import annotations

from pathlib import Path

from enzyme_design.analysis.paper import PaperAnalyzer
from enzyme_design.config import Settings
from enzyme_design.diagnostics.doctor import doctor
from enzyme_design.llm.deepseek import DeepSeekProvider
from enzyme_design.llm.mock import MockProvider
from enzyme_design.parsers.selector import ParserSelector
from enzyme_design.qa.answer import AnswerService
from enzyme_design.research.agent import ResearchAgent
from enzyme_design.retrieval.search_index import SearchHit, SearchIndex
from enzyme_design.storage.index import LiteratureIndex
from enzyme_design.wiki.generator import WikiBuilder
from enzyme_design.workflow.runner import WorkflowRunner


class EnzymeDesignSkillAPI:
    """Programmatic APIs for the bundled enzyme-design literature runtime."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        self.settings.ensure_directories()
        self.index = LiteratureIndex(self.settings.index_path, self.settings.parsed_dir)

    def ingest(self, path: Path, parser: str = "auto") -> str:
        document = ParserSelector(self.settings).parse(path, parser)
        self.index.add_document(document)
        SearchIndex(self.index, self.settings.vault_dir).rebuild(source="parsed")
        return document.document_id

    def analyze(self, document_id: str, dry_run: bool = False) -> Path:
        if not dry_run and not self.settings.allow_upload_private_notes_to_llm:
            raise PermissionError(
                "Remote analysis of local documents is disabled by ENZYME_DESIGN_ALLOW_PRIVATE_UPLOAD=false."
            )
        provider = MockProvider() if dry_run else DeepSeekProvider(self.settings)
        document = self.index.get_document(document_id)
        analysis = PaperAnalyzer(provider).analyze(document)
        path = self.index.save_analysis(analysis)
        SearchIndex(self.index, self.settings.vault_dir).rebuild(source="analysis")
        return path

    def explore(
        self,
        topic: str,
        allow_network: bool = False,
        limit: int | None = None,
        max_rounds: int | None = None,
        goal: str = "activity",
        enzyme: str = "",
        target_substrate: str = "",
        host: str = "",
        confirmations_path: str = "",
        reflection_cycles: int | None = None,
        depth: str = "standard",
        run_full_pipeline: bool = True,
        synthesis_only: bool = False,
    ) -> Path:
        return ResearchAgent(self.settings).explore(
            topic,
            allow_network=allow_network,
            limit=limit,
            max_rounds=max_rounds,
            goal=goal,
            enzyme=enzyme,
            target_substrate=target_substrate,
            host=host,
            confirmations_path=confirmations_path,
            reflection_cycles=reflection_cycles,
            depth=depth,
            run_full_pipeline=run_full_pipeline,
            synthesis_only=synthesis_only,
        )

    def build_wiki(self) -> list[Path]:
        paths = WikiBuilder(self.settings.vault_dir, self.index).build_all()
        SearchIndex(self.index, self.settings.vault_dir).rebuild(source="wiki")
        return paths

    def doctor(self) -> dict[str, object]:
        return doctor(self.settings)

    def rebuild_search_index(self, source: str = "all", full: bool = False) -> int:
        return SearchIndex(self.index, self.settings.vault_dir).rebuild(source=source, full=full)

    def search_status(self, source: str = "all") -> dict[str, object]:
        return SearchIndex(self.index, self.settings.vault_dir).search_status(source=source)

    def search(self, question: str, top_k: int = 8, source: str = "all") -> list[SearchHit]:
        return SearchIndex(self.index, self.settings.vault_dir).search(question, top_k=top_k, source=source)

    def ask(
        self,
        question: str,
        dry_run: bool = False,
        top_k: int = 8,
        rebuild_index: bool = False,
        source: str = "all",
    ) -> str:
        search_index = SearchIndex(self.index, self.settings.vault_dir)
        if rebuild_index or search_index.count_chunks(source=source) == 0:
            search_index.rebuild(source=source)
        if not dry_run and not self.settings.allow_upload_private_notes_to_llm:
            raise PermissionError(
                "Remote question answering over local knowledge requires "
                "ENZYME_DESIGN_ALLOW_PRIVATE_UPLOAD=true; it is currently disabled."
            )
        provider = MockProvider() if dry_run else DeepSeekProvider(self.settings)
        return AnswerService(search_index, provider).ask(question, top_k=top_k, source=source)

    def workflow_file(
        self,
        path: Path,
        parser: str = "auto",
        analyze: bool = False,
        dry_run: bool = False,
        build_wiki: bool = False,
    ) -> dict[str, object]:
        return WorkflowRunner(self.settings).file(
            path,
            parser=parser,
            analyze=analyze,
            dry_run=dry_run,
            build_wiki=build_wiki,
        )

    def workflow_question(self, question: str, dry_run: bool = True, top_k: int = 8) -> str:
        return WorkflowRunner(self.settings).question(question, dry_run=dry_run, top_k=top_k)

    def workflow_topic(self, topic: str, allow_network: bool = False, depth: str = "standard") -> Path:
        return WorkflowRunner(self.settings).topic(topic, allow_network=allow_network, depth=depth)
