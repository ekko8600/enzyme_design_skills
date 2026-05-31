"""Command-line entry point for enzyme-design skills."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from enzyme_design.analysis.paper import PaperAnalyzer
from enzyme_design.config import Settings
from enzyme_design.diagnostics.doctor import doctor, render_doctor_report
from enzyme_design.llm.deepseek import DeepSeekProvider
from enzyme_design.llm.mock import MockProvider
from enzyme_design.parsers.selector import ParserSelector
from enzyme_design.qa.answer import AnswerService
from enzyme_design.research.agent import ResearchAgent
from enzyme_design.retrieval.search_index import SOURCE_CHOICES, SearchIndex
from enzyme_design.storage.index import LiteratureIndex
from enzyme_design.wiki.generator import WikiBuilder
from enzyme_design.workflow.runner import WorkflowRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="enzyme-design")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Parse a local PDF/Markdown/text document.")
    ingest.add_argument("path", type=Path)
    ingest.add_argument(
        "--parser",
        choices=["auto", "text", "pdf-text", "mineru", "mineru-api", "paddleocr", "paddleocr-api"],
        default="auto",
    )

    analyze = sub.add_parser("analyze", help="Analyze one parsed document.")
    analyze.add_argument("document_id")
    analyze.add_argument("--dry-run", action="store_true", help="Use a local mock provider instead of DeepSeek.")

    explore = sub.add_parser("explore", help="Search scholarly metadata for a topic and write a research log.")
    explore.add_argument("--topic", required=True)
    explore.add_argument("--allow-network", action="store_true", help="Compatibility override; network search is enabled by settings unless disabled.")
    explore.add_argument("--limit", type=int, default=None)
    explore.add_argument("--max-rounds", type=int, default=None)
    explore.add_argument("--reflection-cycles", type=int, default=None, help="Plan->Act->Reflect cycles per question.")
    explore.add_argument("--depth", choices=["quick", "standard", "deep"], default="standard")
    explore.add_argument("--no-full-pipeline", action="store_true", help="Skip the default post-explore ingest/analyze/wiki/search refresh pipeline.")
    explore.add_argument("--synthesis-only", action="store_true", help="Skip full-text fetching and post-explore pipeline; write synthesis artifacts only.")
    explore.add_argument("--goal", default="activity")
    explore.add_argument("--enzyme", default="")
    explore.add_argument("--target-substrate", default="")
    explore.add_argument("--host", default="")
    explore.add_argument("--confirmations-file", default="")

    synthesize = sub.add_parser("synthesize", help="List local documents matching a topic.")
    synthesize.add_argument("--topic", required=True)

    index_search = sub.add_parser("index-search", help="Rebuild the local full-text search index.")
    index_search.add_argument("--source", choices=sorted(SOURCE_CHOICES), default="all")
    index_search.add_argument("--full", action="store_true", help="Force a full rebuild instead of incremental refresh.")

    search_status = sub.add_parser("search-status", help="Show local search index freshness and chunk counts.")
    search_status.add_argument("--source", choices=sorted(SOURCE_CHOICES), default="all")

    ask = sub.add_parser("ask", help="Answer a question using local literature evidence.")
    ask.add_argument("--question", required=True)
    ask.add_argument("--top-k", type=int, default=8)
    ask.add_argument("--dry-run", action="store_true", help="Show retrieved evidence without calling a remote LLM.")
    ask.add_argument("--rebuild-index", action="store_true", help="Rebuild the search index before answering.")
    ask.add_argument("--source", choices=sorted(SOURCE_CHOICES), default="all")

    workflow = sub.add_parser("workflow", help="Run a safe high-level literature workflow.")
    workflow.add_argument("--file", type=Path)
    workflow.add_argument("--question")
    workflow.add_argument("--topic")
    workflow.add_argument("--parser", choices=["auto", "text", "pdf-text", "mineru", "mineru-api", "paddleocr", "paddleocr-api"], default="auto")
    workflow.add_argument("--analyze", action="store_true")
    workflow.add_argument("--build-wiki", action="store_true")
    workflow.add_argument("--dry-run", action="store_true")
    workflow.add_argument("--top-k", type=int, default=8)
    workflow.add_argument("--allow-network", action="store_true", help="Compatibility override; network search is enabled by settings unless disabled.")
    workflow.add_argument("--depth", choices=["quick", "standard", "deep"], default="standard")

    sub.add_parser("build-wiki", help="Generate Markdown wiki pages from analyses.")
    sub.add_parser("status", help="Show local index status.")
    sub.add_parser("doctor", help="Run environment and workflow diagnostics.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    settings.ensure_directories()
    index = LiteratureIndex(settings.index_path, settings.parsed_dir)

    if args.command == "ingest":
        document = ParserSelector(settings).parse(args.path, args.parser)
        path = index.add_document(document)
        SearchIndex(index, settings.vault_dir).rebuild(source="parsed")
        print(f"Ingested {document.document_id}: {document.title}")
        print(path)
        return 0

    if args.command == "analyze":
        if not args.dry_run and not settings.allow_upload_private_notes_to_llm:
            raise PermissionError(
                "Remote analysis of local documents is disabled by ENZYME_DESIGN_ALLOW_PRIVATE_UPLOAD=false. "
                "Use --dry-run for local analysis."
            )
        provider = MockProvider() if args.dry_run else DeepSeekProvider(settings)
        document = index.get_document(args.document_id)
        analysis = PaperAnalyzer(provider).analyze(document)
        path = index.save_analysis(analysis)
        SearchIndex(index, settings.vault_dir).rebuild(source="analysis")
        print(f"Analyzed {analysis.document_id}: {analysis.title}")
        print(path)
        return 0

    if args.command == "explore":
        path = ResearchAgent(settings).explore(
            args.topic,
            allow_network=args.allow_network,
            limit=args.limit,
            max_rounds=args.max_rounds,
            goal=args.goal,
            enzyme=args.enzyme,
            target_substrate=args.target_substrate,
            host=args.host,
            confirmations_path=args.confirmations_file,
            reflection_cycles=args.reflection_cycles,
            run_full_pipeline=not args.no_full_pipeline,
            depth=args.depth,
            synthesis_only=args.synthesis_only,
        )
        print(path)
        manifest = next((path.parent.glob("manifest.json")), None)
        if manifest:
            print(manifest)
        return 0

    if args.command == "synthesize":
        rows = index.find_by_topic(args.topic)
        for row in rows:
            print(f"{row['document_id']}\t{row['title']}\t{row['analysis_path'] or 'pending'}")
        return 0

    if args.command == "index-search":
        count = SearchIndex(index, settings.vault_dir).rebuild(source=args.source, full=args.full)
        print(f"indexed chunks: {count}")
        return 0

    if args.command == "search-status":
        status = SearchIndex(index, settings.vault_dir).search_status(source=args.source)
        print(f"total_chunks: {status['total_chunks']}")
        print(f"fresh_sources: {status['fresh_sources']}")
        print(f"stale_sources: {status['stale_sources']}")
        print(f"orphaned_sources: {status['orphaned_sources']}")
        print("source_chunks:")
        for source_type, count in dict(status["source_chunks"]).items():
            print(f"  {source_type}: {count}")
        stale_paths = list(status["stale_paths"])
        if stale_paths:
            print("stale_paths:")
            for path in stale_paths:
                print(f"  {path}")
        orphaned_paths = list(status["orphaned_paths"])
        if orphaned_paths:
            print("orphaned_paths:")
            for path in orphaned_paths:
                print(f"  {path}")
        return 0

    if args.command == "ask":
        search_index = SearchIndex(index, settings.vault_dir)
        if args.rebuild_index or search_index.count_chunks(source=args.source) == 0:
            count = search_index.rebuild(source=args.source)
            print(f"indexed chunks: {count}")
        if not args.dry_run and not settings.allow_upload_private_notes_to_llm:
            raise PermissionError(
                "Remote question answering over local knowledge requires "
                "ENZYME_DESIGN_ALLOW_PRIVATE_UPLOAD=true; it is currently disabled. Use --dry-run to inspect local evidence."
            )
        provider = MockProvider() if args.dry_run else DeepSeekProvider(settings)
        answer = AnswerService(search_index, provider).ask(
            args.question,
            top_k=args.top_k,
            source=args.source,
        )
        print(answer)
        return 0

    if args.command == "workflow":
        selected = [bool(args.file), bool(args.question), bool(args.topic)]
        if sum(selected) != 1:
            raise ValueError("workflow requires exactly one of --file, --question, or --topic.")
        runner = WorkflowRunner(settings)
        if args.file:
            result = runner.file(
                args.file,
                parser=args.parser,
                analyze=args.analyze,
                dry_run=args.dry_run,
                build_wiki=args.build_wiki,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.question:
            print(runner.question(args.question, dry_run=args.dry_run, top_k=args.top_k))
            return 0
        if args.topic:
            print(runner.topic(args.topic, allow_network=args.allow_network, depth=args.depth))
            return 0

    if args.command == "build-wiki":
        paths = WikiBuilder(settings.vault_dir, index).build_all()
        SearchIndex(index, settings.vault_dir).rebuild(source="wiki")
        for path in paths:
            print(path)
        return 0

    if args.command == "status":
        rows = index.list_documents()
        print(f"documents: {len(rows)}")
        for row in rows:
            status = "analyzed" if row["analysis_path"] else "pending"
            print(f"{row['document_id']}\t{status}\t{row['title']}")
        return 0

    if args.command == "doctor":
        print(render_doctor_report(doctor(settings)))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
