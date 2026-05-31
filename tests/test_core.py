import json
from pathlib import Path

from enzyme_design.analysis.paper import PaperAnalyzer
from enzyme_design.config import Settings
from enzyme_design.llm.mock import MockProvider
from enzyme_design.parsers.selector import ParserSelector
from enzyme_design.research.search import SearchResult
from enzyme_design.schema import AnalysisResult
from enzyme_design.storage.index import LiteratureIndex
from enzyme_design.wiki.generator import WikiBuilder


def test_markdown_ingest_analyze_and_wiki(tmp_path: Path):
    note = tmp_path / "paper.md"
    note.write_text("# Example Paper\n\nThis paper studies literature wiki agents.", encoding="utf-8")
    settings = Settings.from_env(tmp_path)
    settings.ensure_directories()
    index = LiteratureIndex(settings.index_path, settings.parsed_dir)

    document = ParserSelector(settings).parse(note)
    index.add_document(document)
    analysis = PaperAnalyzer(MockProvider()).analyze(document)
    index.save_analysis(analysis)
    paths = WikiBuilder(settings.vault_dir, index).build_all()

    assert document.title == "Example Paper"
    assert any(path.name == "index.md" for path in paths)
    assert (settings.vault_dir / "papers" / f"{document.document_id}.md").exists()
    memories = index.list_memories()
    assert any(memory["key"] == f"paper:{document.document_id}:tldr" for memory in memories)


def test_analysis_result_old_json_defaults_optional_fields():
    payload = {
        "document_id": "doc1",
        "title": "Old Analysis",
        "tldr": "summary",
        "research_question": "rq",
        "method": "method",
        "contributions": [],
        "evidence": [],
        "limitations": [],
        "concepts": [],
        "related_work": [],
    }

    analysis = AnalysisResult.from_dict(payload)

    assert analysis.claims == []
    assert analysis.datasets == []
    assert analysis.metrics == []
    assert analysis.key_figures == []
    assert analysis.open_questions == []


def test_wiki_renders_extended_analysis_fields(tmp_path: Path):
    from enzyme_design.schema import ParsedDocument

    settings = Settings.from_env(tmp_path)
    settings.ensure_directories()
    index = LiteratureIndex(settings.index_path, settings.parsed_dir)
    document = ParsedDocument(
        document_id="doc-extended",
        source_path=str(tmp_path / "paper.md"),
        source_type="markdown",
        title="Extended Paper",
        markdown="# Extended Paper",
        parser_backend="test",
    )
    index.add_document(document)
    index.save_analysis(
        AnalysisResult(
            document_id=document.document_id,
            title=document.title,
            tldr="summary",
            research_question="rq",
            method="method",
            contributions=[],
            evidence=[],
            limitations=[],
            concepts=[],
            related_work=[],
            claims=["Claim A"],
            datasets=["Dataset A"],
            metrics=["Metric A"],
            key_figures=["Figure 1"],
            open_questions=["What remains unknown?"],
        )
    )

    paths = WikiBuilder(settings.vault_dir, index).build_all()
    paper_text = (settings.vault_dir / "papers" / "doc-extended.md").read_text(encoding="utf-8")
    open_questions = (settings.vault_dir / "topics" / "open-questions.md").read_text(encoding="utf-8")

    assert any(path.name == "open-questions.md" for path in paths)
    assert "## Claims" in paper_text
    assert "Claim A" in paper_text
    assert "What remains unknown?" in open_questions


def test_network_and_private_upload_defaults_enabled(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LITERATURE_WIKI_ALLOW_NETWORK", raising=False)
    monkeypatch.delenv("LITERATURE_WIKI_ALLOW_PRIVATE_UPLOAD", raising=False)

    settings = Settings.from_env(tmp_path)

    assert settings.allow_network_search is True
    assert settings.allow_upload_private_notes_to_llm is True


def test_doctor_reports_fts_and_missing_deepseek_warn(tmp_path: Path):
    from enzyme_design.diagnostics.doctor import doctor

    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        parsed_dir=tmp_path / "data" / "parsed",
        index_path=tmp_path / "data" / "index" / "enzyme_design.sqlite3",
        vault_dir=tmp_path / "vault",
        deepseek_api_key=None,
    )
    report = doctor(settings)
    checks = {item["name"]: item for item in report["checks"]}

    assert checks["sqlite_fts5"]["status"] == "OK"
    assert checks["deepseek"]["status"] == "WARN"
    assert "summary" in report


def test_workflow_file_ingests_analyzes_and_builds(tmp_path: Path):
    from enzyme_design.skill_api import EnzymeDesignSkillAPI

    note = tmp_path / "workflow.md"
    note.write_text("# Workflow Paper\n\nThis paper discusses workflow skills.", encoding="utf-8")
    api = EnzymeDesignSkillAPI(Settings.from_env(tmp_path))

    result = api.workflow_file(note, analyze=True, dry_run=True, build_wiki=True)

    assert result["document_id"]
    assert result["analysis_path"]
    assert result["wiki_paths"]


def test_workflow_question_uses_local_ask(tmp_path: Path):
    from enzyme_design.skill_api import EnzymeDesignSkillAPI

    note = tmp_path / "qa.md"
    note.write_text("# QA Workflow\n\n## Evidence\n\nworkflow question evidence appears here.", encoding="utf-8")
    api = EnzymeDesignSkillAPI(Settings.from_env(tmp_path))
    api.ingest(note)

    answer = api.workflow_question("workflow question evidence", dry_run=True)

    assert "Evidence Matrix" in answer
    assert "workflow question evidence" in answer


def test_discovered_paper_markdown_written(tmp_path: Path):
    from enzyme_design.research.fulltext import FullTextFetchResult
    from enzyme_design.research.research_log import write_result_markdown

    settings = Settings.from_env(tmp_path)
    settings.ensure_directories()
    result = SearchResult(
        title="Enzyme Design with Foundation Models",
        url="https://doi.org/10.1000/example",
        summary="An example abstract.",
        source="crossref",
        doi="10.1000/example",
        published="2026-01-01",
        authors=["Jane Doe", "John Smith"],
        pdf_url="https://example.com/paper.pdf",
    )
    fetch_status = FullTextFetchResult(markdown="# Parsed Full Text\n\ncontent", status="retrieved", source=result.pdf_url)
    path = write_result_markdown(settings.vault_dir, result, fulltext_markdown=fetch_status.markdown, fetch_status=fetch_status)
    text = path.read_text(encoding="utf-8")
    assert "## Metadata" in text
    assert "10.1000/example" in text
    assert "Full Text Status: retrieved" in text
    assert "## Full Text" in text


def test_artifact_archive_run(tmp_path: Path):
    from enzyme_design.research.artifacts import archive_run, write_artifact_json, write_artifact_markdown

    run_dir = tmp_path / "run"
    archive_dir = tmp_path / "archive"
    manifest = write_artifact_json(run_dir / "manifest.json", {"run_id": "demo"})
    synthesis = write_artifact_markdown(run_dir / "deep_synthesis.md", ["# Deep Synthesis"])
    archive_manifest = archive_run(archive_dir, [manifest, synthesis], {"run_id": "demo"})

    assert archive_manifest.exists()
    assert (archive_dir / "manifest.json").exists()
    assert (archive_dir / "deep_synthesis.md").exists()


def test_wiki_index_includes_deep_synthesis(tmp_path: Path):
    settings = Settings.from_env(tmp_path)
    settings.ensure_directories()
    index = LiteratureIndex(settings.index_path, settings.parsed_dir)
    synthesis = settings.vault_dir / "research_logs" / "run-1" / "deep_synthesis.md"
    synthesis.parent.mkdir(parents=True)
    synthesis.write_text("# Deep Synthesis\n", encoding="utf-8")

    paths = WikiBuilder(settings.vault_dir, index).build_all()
    index_text = (settings.vault_dir / "index.md").read_text(encoding="utf-8")

    assert synthesis in paths
    assert "[[research_logs/run-1/deep_synthesis]]" in index_text


def test_fetch_fulltext_required_records_missing_status(tmp_path: Path):
    from enzyme_design.research.fulltext import fetch_fulltext

    settings = Settings.from_env(tmp_path)
    result = SearchResult(title="No Full Text", url="", source="test", requires_fulltext=True)
    fetch = fetch_fulltext(settings, result, require_fulltext=True)

    assert fetch.status == "missing_required"
    assert "Retrieved: No" in fetch.markdown


def test_depth_profile_defaults_and_overrides():
    from enzyme_design.research.depth import resolve_depth_profile

    quick = resolve_depth_profile("quick")
    overridden = resolve_depth_profile("quick", limit=10)
    deep = resolve_depth_profile("deep", max_rounds=1)

    assert quick.effective_limit == 3
    assert quick.effective_max_rounds == 3
    assert quick.fulltext_cap == 2
    assert overridden.effective_limit == 10
    assert overridden.unique_result_cap == 20
    assert deep.effective_max_rounds == 1
    assert deep.effective_reflection_cycles == 3


def test_research_plan_includes_ai_priors_and_user_codesign():
    from enzyme_design.research.planner import build_research_plan

    plan = build_research_plan("proteinase K thermostability", goal="stability", enzyme="Proteinase K")
    ids = [question.question_id for question in plan.questions]

    assert "q4_ai_design_priors" in ids
    assert "q5_drylab_contract" in ids
    assert "q6_user_strategy_discussion" in ids
    contract = next(question for question in plan.questions if question.question_id == "q5_drylab_contract")
    assert contract.needs_user_confirmation is True
    assert "干实验设计契约" in contract.confirmation_prompt


def test_opencode_skill_wrapper_matches_canonical():
    root = Path(__file__).resolve().parents[1]
    wrapper = root / ".opencode" / "skills" / "enzyme-design"

    assert (wrapper / "SKILL.md").read_text(encoding="utf-8") == (root / "SKILL.md").read_text(encoding="utf-8")
    for reference in (root / "references").glob("*.md"):
        assert (wrapper / "references" / reference.name).read_text(encoding="utf-8") == reference.read_text(encoding="utf-8")


def test_explore_writes_run_manifest_archive_and_failures(tmp_path: Path):
    from enzyme_design.research.agent import ResearchAgent

    settings = Settings.from_env(tmp_path)
    settings.ensure_directories()
    agent = ResearchAgent(settings)
    agent._build_reasoner = lambda: MockProvider()  # type: ignore[method-assign]
    agent._require_user_confirmations = lambda plan, confirmations_path: None  # type: ignore[method-assign]
    agent._search_once = lambda keyword, limit: [  # type: ignore[method-assign]
        SearchResult(
            title="Example Enzyme Engineering",
            url="",
            summary="A mutation improves activity.",
            source="test",
            doi="10.1000/example",
            published="2026",
        )
    ]

    log_path = agent.explore(
        "example enzyme engineering",
        allow_network=True,
        limit=1,
        max_rounds=1,
        reflection_cycles=1,
    )
    manifest_path = log_path.parent / "manifest.json"
    failures_path = log_path.parent / "failures.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert log_path.name == "research_log.md"
    assert manifest_path.exists()
    assert failures_path.exists()
    assert Path(str(manifest["artifacts"]["deep_synthesis"])).exists()
    assert Path(str(manifest["artifacts"]["archive_manifest"])).exists()
    pipeline_step = next(step for step in manifest["steps"] if step["name"] == "post_explore_pipeline")
    final_step = next(step for step in manifest["steps"] if step["name"] == "finalize_wiki_and_search")
    assert pipeline_step["status"] == "completed"
    assert pipeline_step["ingested_document_ids"]
    assert pipeline_step["analyzed_document_ids"]
    assert pipeline_step["analysis_summaries"]
    assert final_step["status"] == "completed"
    assert int(manifest["artifacts"]["search_chunks"]) > 0
    assert any(Path(path).exists() for path in manifest["artifacts"]["discovered_papers"])


def test_quick_depth_caps_fulltext_and_records_skips(tmp_path: Path):
    from enzyme_design.research.agent import ResearchAgent

    settings = Settings.from_env(tmp_path)
    settings.ensure_directories()
    agent = ResearchAgent(settings)
    agent._build_reasoner = lambda: MockProvider()  # type: ignore[method-assign]
    agent._require_user_confirmations = lambda plan, confirmations_path: None  # type: ignore[method-assign]
    agent._search_once = lambda keyword, limit: [  # type: ignore[method-assign]
        SearchResult(
            title=f"Mutation kinetics structure substrate paper {idx}",
            url="",
            summary="mutation kinetics structure substrate",
            source="test",
            doi=f"10.1000/example-{idx}",
            published="2026",
            pdf_url=f"https://example.com/{idx}.pdf",
            requires_fulltext=True,
        )
        for idx in range(4)
    ]

    log_path = agent.explore(
        "example enzyme engineering",
        allow_network=True,
        depth="quick",
        max_rounds=1,
        reflection_cycles=1,
        run_full_pipeline=False,
    )
    manifest = json.loads((log_path.parent / "manifest.json").read_text(encoding="utf-8"))
    fetch_step = next(step for step in manifest["steps"] if step["name"] == "fetch_fulltext")
    statuses = [record["status"] for record in fetch_step["records"]]

    assert manifest["depth_profile"]["effective_limit"] == 3
    assert manifest["depth_profile"]["fulltext_cap"] == 2
    assert statuses.count("skipped_by_depth_budget") >= 1


def test_explore_fetches_relevant_web_text_without_pdf(tmp_path: Path):
    from types import SimpleNamespace

    from enzyme_design.research.agent import ResearchAgent

    settings = Settings.from_env(tmp_path)
    agent = ResearchAgent(settings)
    result = SearchResult(
        title="Mutation kinetics for example enzyme",
        url="https://example.com/paper",
        summary="This study reports mutagenesis, kcat, Km, and substrate specificity.",
        source="test",
    )
    plan = SimpleNamespace(topic="example enzyme", design_goal="activity", user_constraints={})

    assert agent._should_fetch_fulltext(result, plan, {result.url: 1}) is True


def test_remote_analyze_refuses_when_private_upload_disabled(tmp_path: Path):
    from enzyme_design.skill_api import EnzymeDesignSkillAPI

    note = tmp_path / "paper.md"
    note.write_text("# Private Paper\n\nsecret", encoding="utf-8")
    settings = Settings.from_env(tmp_path)
    settings.allow_upload_private_notes_to_llm = False
    api = EnzymeDesignSkillAPI(settings)
    document_id = api.ingest(note)

    try:
        api.analyze(document_id, dry_run=False)
    except PermissionError as exc:
        assert "ENZYME_DESIGN_ALLOW_PRIVATE_UPLOAD" in str(exc)
    else:
        raise AssertionError("remote analyze should refuse when private upload is disabled")


def test_search_index_retrieves_markdown_sections(tmp_path: Path):
    from enzyme_design.retrieval.search_index import SearchIndex

    note = tmp_path / "paper.md"
    note.write_text(
        "# Enzyme Paper\n\n## Assay Results\n\nProteinase K retained collagen activity after calcium treatment.",
        encoding="utf-8",
    )
    settings = Settings.from_env(tmp_path)
    settings.ensure_directories()
    index = LiteratureIndex(settings.index_path, settings.parsed_dir)
    document = ParserSelector(settings).parse(note)
    index.add_document(document)

    search_index = SearchIndex(index, settings.vault_dir)
    count = search_index.rebuild()
    hits = search_index.search("collagen activity calcium", top_k=3)

    assert count >= 1
    assert hits
    assert hits[0].document_id == document.document_id
    assert "Assay Results" in hits[0].section_path
    assert "collagen activity" in hits[0].content
    assert hits[0].start_line >= 1
    assert hits[0].rank_score > 0
    assert hits[0].match_reason


def test_search_reranks_section_title_hits(tmp_path: Path):
    from enzyme_design.retrieval.search_index import SearchIndex

    note = tmp_path / "paper.md"
    note.write_text(
        "# Ranking Paper\n\n## Weak Context\n\nzinc appears once.\n\n## Zinc Binding Assay\n\nThis section has the assay details.",
        encoding="utf-8",
    )
    settings = Settings.from_env(tmp_path)
    settings.ensure_directories()
    index = LiteratureIndex(settings.index_path, settings.parsed_dir)
    document = ParserSelector(settings).parse(note)
    index.add_document(document)

    search_index = SearchIndex(index, settings.vault_dir)
    search_index.rebuild()
    hits = search_index.search("zinc binding assay", top_k=2)

    assert hits
    assert "Zinc Binding Assay" in hits[0].section_path
    assert hits[0].rank_score >= hits[-1].rank_score


def test_search_chinese_like_fallback(tmp_path: Path):
    from enzyme_design.retrieval.search_index import SearchIndex

    note = tmp_path / "paper.md"
    note.write_text("# 中文论文\n\n## 结果\n\n这个章节讨论蛋白稳定性和钙离子处理。", encoding="utf-8")
    settings = Settings.from_env(tmp_path)
    settings.ensure_directories()
    index = LiteratureIndex(settings.index_path, settings.parsed_dir)
    document = ParserSelector(settings).parse(note)
    index.add_document(document)

    search_index = SearchIndex(index, settings.vault_dir)
    search_index.rebuild()
    hits = search_index.search("蛋白稳定性 钙离子", top_k=2)

    assert hits
    assert "中文论文 > 结果" in hits[0].section_path


def test_search_index_retrieves_analysis_json(tmp_path: Path):
    from enzyme_design.retrieval.search_index import SearchIndex

    settings = Settings.from_env(tmp_path)
    settings.ensure_directories()
    index = LiteratureIndex(settings.index_path, settings.parsed_dir)
    note = tmp_path / "paper.md"
    note.write_text("# Analysis Paper\n\nbody", encoding="utf-8")
    document = ParserSelector(settings).parse(note)
    index.add_document(document)
    index.save_analysis(
        AnalysisResult(
            document_id=document.document_id,
            title=document.title,
            tldr="This paper explains protease thermostability markers.",
            research_question="How does thermostability change?",
            method="Local analysis.",
            contributions=["Defines thermostability markers."],
            evidence=["Marker residues are discussed."],
            limitations=[],
            concepts=["thermostability marker"],
        )
    )

    search_index = SearchIndex(index, settings.vault_dir)
    search_index.rebuild(source="analysis")
    hits = search_index.search("thermostability markers", top_k=3, source="analysis")

    assert hits
    assert hits[0].source_type == "analysis"
    assert "thermostability" in hits[0].content


def test_search_index_retrieves_research_logs(tmp_path: Path):
    from enzyme_design.retrieval.search_index import SearchIndex

    settings = Settings.from_env(tmp_path)
    settings.ensure_directories()
    index = LiteratureIndex(settings.index_path, settings.parsed_dir)
    log = settings.vault_dir / "research_logs" / "2026-05-22-example.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("# Research Log\n\n## Findings\n\nDirected evolution improved PETase activity.", encoding="utf-8")

    search_index = SearchIndex(index, settings.vault_dir)
    search_index.rebuild(source="logs")
    hits = search_index.search("PETase activity", top_k=3, source="logs")

    assert hits
    assert hits[0].source_type == "logs"
    assert str(log) == hits[0].source_path


def test_ask_dry_run_uses_local_evidence(tmp_path: Path):
    from enzyme_design.skill_api import EnzymeDesignSkillAPI

    settings = Settings.from_env(tmp_path)
    api = EnzymeDesignSkillAPI(settings)
    note = tmp_path / "paper.md"
    note.write_text("# QA Paper\n\n## Result\n\nA local-only answer can cite this zinc binding evidence.", encoding="utf-8")
    api.ingest(note)

    answer = api.ask("What evidence mentions zinc binding?", dry_run=True, rebuild_index=True)

    assert "## Answer" in answer
    assert "Evidence Matrix" in answer
    assert "zinc binding evidence" in answer
    assert "| ID | Strength | Score | Source | Section | Location | Match | Excerpt |" in answer


def test_remote_ask_refuses_when_private_upload_disabled(tmp_path: Path):
    from enzyme_design.skill_api import EnzymeDesignSkillAPI

    settings = Settings.from_env(tmp_path)
    settings.allow_upload_private_notes_to_llm = False
    api = EnzymeDesignSkillAPI(settings)
    note = tmp_path / "paper.md"
    note.write_text("# Private QA Paper\n\nprivate evidence", encoding="utf-8")
    api.ingest(note)

    try:
        api.ask("What is private?", dry_run=False, rebuild_index=True)
    except PermissionError as exc:
        assert "ENZYME_DESIGN_ALLOW_PRIVATE_UPLOAD" in str(exc)
    else:
        raise AssertionError("remote ask should refuse when private upload is disabled")


def test_incremental_index_updates_modified_markdown_source(tmp_path: Path):
    from enzyme_design.skill_api import EnzymeDesignSkillAPI

    settings = Settings.from_env(tmp_path)
    api = EnzymeDesignSkillAPI(settings)
    note = tmp_path / "paper.md"
    note.write_text("# Incremental Paper\n\n## Old\n\nold phosphatase evidence", encoding="utf-8")
    api.ingest(note)

    assert api.search_status()["stale_sources"] == 0
    note.write_text("# Incremental Paper\n\n## New\n\nfresh kinase activity evidence", encoding="utf-8")
    assert api.search_status()["stale_sources"] == 1
    indexed = api.rebuild_search_index()
    hits = api.search("kinase activity", top_k=2)

    assert indexed >= 1
    assert api.search_status()["stale_sources"] == 0
    assert hits
    assert "New" in hits[0].section_path


def test_full_rebuild_resets_search_index(tmp_path: Path):
    from enzyme_design.skill_api import EnzymeDesignSkillAPI

    settings = Settings.from_env(tmp_path)
    api = EnzymeDesignSkillAPI(settings)
    note = tmp_path / "paper.md"
    note.write_text("# Full Paper\n\n## Result\n\nfull rebuild marker", encoding="utf-8")
    api.ingest(note)

    count = api.rebuild_search_index(full=True)
    status = api.search_status()

    assert count >= 1
    assert status["total_chunks"] >= 1
    assert status["orphaned_sources"] == 0


def test_structured_sections_are_indexed_before_markdown(tmp_path: Path):
    from enzyme_design.retrieval.search_index import SearchIndex
    from enzyme_design.schema import ParsedDocument, stable_document_id

    settings = Settings.from_env(tmp_path)
    settings.ensure_directories()
    index = LiteratureIndex(settings.index_path, settings.parsed_dir)
    document = ParsedDocument(
        document_id=stable_document_id("structured", "structured kinase fact"),
        source_path=str(tmp_path / "structured.md"),
        source_type="markdown",
        title="Structured Paper",
        markdown="# Structured Paper\n\nmarkdown fallback text",
        parser_backend="test",
        sections=[
            {
                "title": "Structured Results",
                "text": "structured kinase fact",
                "start_line": 12,
                "end_line": 14,
                "level": 2,
            }
        ],
    )
    index.add_document(document)

    search_index = SearchIndex(index, settings.vault_dir)
    search_index.rebuild(full=True)
    hits = search_index.search("structured kinase", top_k=2)

    assert hits
    assert "Structured Results" in hits[0].section_path
    assert hits[0].start_line == 12


def test_rank_results_prefers_pdf_and_relevance():
    from enzyme_design.research.search import rank_results

    results = [
        SearchResult(title="Protein engineering review", url="u1", summary="", source="crossref", score=1),
        SearchResult(title="Protein enzyme design", url="u2", summary="full", source="arxiv", score=0, pdf_url="pdf"),
    ]
    ranked = rank_results(results, "protein enzyme")
    assert ranked[0].url == "u2"


def test_expand_openalex_inverted_abstract():
    from enzyme_design.research.search import _expand_inverted_abstract

    abstract = _expand_inverted_abstract({"enzyme": [0], "design": [1], "works": [2]})
    assert abstract == "enzyme design works"


def test_parse_pubmed_xml_basic():
    from enzyme_design.research.search import _parse_pubmed_xml

    xml = """
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>123456</PMID>
          <Article>
            <ArticleTitle>Protein Engineering Study</ArticleTitle>
            <Abstract><AbstractText>Abstract content.</AbstractText></Abstract>
            <AuthorList><Author><ForeName>Jane</ForeName><LastName>Doe</LastName></Author></AuthorList>
            <Journal><JournalIssue><PubDate><Year>2025</Year></PubDate></JournalIssue></Journal>
          </Article>
        </MedlineCitation>
        <PubmedData><ArticleIdList><ArticleId IdType="doi">10.1000/test</ArticleId></ArticleIdList></PubmedData>
      </PubmedArticle>
    </PubmedArticleSet>
    """
    results = _parse_pubmed_xml(xml)
    assert len(results) == 1
    assert results[0].source == "pubmed"
    assert results[0].doi == "10.1000/test"
