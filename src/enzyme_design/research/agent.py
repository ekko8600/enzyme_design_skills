"""Topic exploration orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from enzyme_design.analysis.paper import PaperAnalyzer
from enzyme_design.config import Settings
from enzyme_design.llm.base import LLMProvider
from enzyme_design.llm.deepseek import DeepSeekProvider
from enzyme_design.llm.mock import MockProvider
from enzyme_design.parsers.selector import ParserSelector
from enzyme_design.research.artifacts import archive_run, make_run_id, write_artifact_json, write_artifact_markdown
from enzyme_design.research.depth import DepthProfile, resolve_depth_profile
from enzyme_design.research.fulltext import FullTextFetchResult, fetch_fulltext
from enzyme_design.research.planner import ResearchQuestion, build_research_plan
from enzyme_design.research.research_log import write_research_log, write_result_markdown
from enzyme_design.research.search import SearchResult, rank_results, search_arxiv, search_crossref, search_openalex, search_pubmed, search_semantic_scholar
from enzyme_design.retrieval.search_index import SearchIndex
from enzyme_design.storage.index import LiteratureIndex
from enzyme_design.wiki.generator import WikiBuilder


class ResearchAgent:
    """Run logged, source-traceable network exploration for a topic."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def explore(self, topic: str, *, allow_network: bool = False, limit: int | None = None, max_rounds: int | None = None, goal: str = "activity", enzyme: str = "", target_substrate: str = "", host: str = "", run_full_pipeline: bool = True, confirmations_path: str = "", reflection_cycles: int | None = None, depth: str = "standard", synthesis_only: bool = False):
        if not (allow_network or self.settings.allow_network_search):
            raise PermissionError("Network exploration is disabled by ENZYME_DESIGN_ALLOW_NETWORK=false.")
        profile = resolve_depth_profile(depth, limit=limit, max_rounds=max_rounds, reflection_cycles=reflection_cycles)
        run_id = make_run_id(topic)
        run_dir = self.settings.vault_dir / "research_logs" / run_id
        archive_dir = self.settings.vault_dir / "archive" / run_id
        plan = build_research_plan(topic, goal=goal, enzyme=enzyme, target_substrate=target_substrate, host=host)
        self._require_user_confirmations(plan, confirmations_path)
        reasoner = self._build_reasoner()

        manifest: dict[str, object] = {
            "run_id": run_id,
            "topic": topic,
            "goal": goal,
            "enzyme": enzyme,
            "target_substrate": target_substrate,
            "host": host,
            "depth": depth,
            "depth_profile": profile.to_dict(),
            "steps": [],
            "artifacts": {},
            "failures": [],
        }
        results: list[SearchResult] = []
        rounds: list[dict[str, str]] = []
        question_answers: dict[str, str] = {}
        for round_id, question in enumerate(plan.questions[:profile.effective_max_rounds], start=1):
            if question.needs_user_confirmation:
                question_answers[question.question_id] = "- 已由用户在确认文件中给出选项，见 Confirmations 小节。"
                continue
            query = f"{plan.topic} {question.section} {plan.design_goal}"
            query = self._plan_query(question, query)
            ranked = rank_results(self._dedupe(self._search_once(query, limit=profile.effective_limit)), query)[: profile.effective_limit]
            no_growth_count = 0
            for _ in range(max(profile.effective_reflection_cycles - 1, 0)):
                if self._has_enough_direct_evidence(ranked):
                    break
                reflect_query = self._reflect_next_query(question, query, ranked)
                if not reflect_query or reflect_query == query:
                    break
                previous_count = len(self._dedupe(ranked))
                query = reflect_query
                ranked = rank_results(self._dedupe(ranked + self._search_once(query, limit=profile.effective_limit)), query)[: profile.effective_limit]
                new_count = len(self._dedupe(ranked))
                if new_count <= previous_count:
                    no_growth_count += 1
                else:
                    no_growth_count = 0
                if no_growth_count >= (2 if profile.depth == "deep" else 1):
                    break
            results.extend(ranked)
            answer = self._synthesize_answer_with_llm(reasoner, question, ranked)
            if answer.startswith("- LLM synthesis failed"):
                failures = manifest["failures"]
                if isinstance(failures, list):
                    failures.append({"stage": "question_synthesis", "question_id": question.question_id, "error": answer})
            question_answers[question.question_id] = answer
            rounds.append({"round_id": str(round_id), "question_id": question.question_id, "query": query, "result_count": str(len(ranked)), "gap": self._infer_gap(ranked)})

        unique_results = rank_results(self._dedupe(results), topic)[: profile.unique_result_cap]
        manifest["steps"].append({"name": "search", "status": "completed", "result_count": len(unique_results), "rounds": rounds})
        discovered_paths = []
        fetch_records = []
        if synthesis_only:
            manifest["steps"].append({"name": "fetch_fulltext", "status": "skipped", "reason": "synthesis_only"})
        else:
            fulltext_budget = 0
            duplicate_counts = self._duplicate_counts(results)
            for result in unique_results:
                should_fetch = fulltext_budget < profile.fulltext_cap and self._should_fetch_fulltext(result, plan, duplicate_counts)
                if should_fetch:
                    fetch_result = fetch_fulltext(self.settings, result, require_fulltext=result.requires_fulltext)
                    fulltext_budget += 1
                else:
                    fetch_result = FullTextFetchResult(
                        status="skipped_by_depth_budget",
                        source=result.pdf_url or result.url,
                        error="" if fulltext_budget >= profile.fulltext_cap else "low full-text value under current depth profile",
                    )
                fetch_records.append(self._fetch_record(result, fetch_result))
                discovered_paths.append(
                    write_result_markdown(
                        self.settings.vault_dir,
                        result,
                        fulltext_markdown=fetch_result.markdown,
                        fetch_status=fetch_result,
                    )
                )
            manifest["steps"].append({"name": "fetch_fulltext", "status": "completed", "records": fetch_records})
        manifest["artifacts"] = {**dict(manifest["artifacts"]), "discovered_papers": [str(path) for path in discovered_paths]}
        pipeline_report: dict[str, object] = {}
        if synthesis_only:
            manifest["steps"].append({"name": "post_explore_pipeline", "status": "skipped", "reason": "synthesis_only"})
        elif run_full_pipeline:
            pipeline_report = self._run_post_explore_pipeline(discovered_paths)
            manifest["steps"].append({"name": "post_explore_pipeline", **pipeline_report})
            manifest["failures"] = list(manifest["failures"]) + list(pipeline_report.get("failures", []))
        else:
            manifest["steps"].append({"name": "post_explore_pipeline", "status": "skipped", "reason": "disabled"})
        deep_synthesis_path, synthesis_failure = self._write_deep_synthesis(run_dir, reasoner, plan, unique_results, question_answers, rounds, fetch_records, pipeline_report, profile)
        if synthesis_failure:
            failures = manifest["failures"]
            if isinstance(failures, list):
                failures.append({"stage": "deep_synthesis", "error": synthesis_failure})
        manifest["artifacts"] = {**dict(manifest["artifacts"]), "deep_synthesis": str(deep_synthesis_path)}
        failures_path = write_artifact_json(run_dir / "failures.json", {"failures": list(manifest["failures"])})
        manifest["artifacts"] = {**dict(manifest["artifacts"]), "failures": str(failures_path)}
        log_path = write_research_log(self.settings.vault_dir, plan, unique_results, question_answers, rounds, path=run_dir / "research_log.md")
        manifest["artifacts"] = {**dict(manifest["artifacts"]), "research_log": str(log_path)}
        manifest_path = write_artifact_json(run_dir / "manifest.json", manifest)
        manifest["artifacts"] = {**dict(manifest["artifacts"]), "manifest": str(manifest_path)}
        if not synthesis_only:
            final_surface_report = self._finalize_knowledge_surfaces()
            manifest["steps"].append({"name": "finalize_wiki_and_search", **final_surface_report})
            manifest["artifacts"] = {
                **dict(manifest["artifacts"]),
                "final_wiki_paths": final_surface_report.get("wiki_paths", []),
                "search_chunks": final_surface_report.get("search_chunks", 0),
            }
            manifest["failures"] = list(manifest["failures"]) + list(final_surface_report.get("failures", []))
            write_artifact_json(manifest_path, manifest)
        archive_paths = [manifest_path, failures_path, deep_synthesis_path, log_path, *discovered_paths]
        archive_paths.extend(Path(str(path)) for path in pipeline_report.get("wiki_paths", []) if isinstance(path, str))
        archive_paths.extend(Path(str(path)) for path in manifest["artifacts"].get("final_wiki_paths", []) if isinstance(path, str))
        archive_manifest = archive_run(archive_dir, archive_paths, manifest)
        manifest["artifacts"] = {**dict(manifest["artifacts"]), "archive_manifest": str(archive_manifest)}
        write_artifact_json(manifest_path, manifest)
        return log_path

    def _build_reasoner(self) -> LLMProvider:
        if self.settings.deepseek_api_key:
            return DeepSeekProvider(self.settings)
        return MockProvider()

    def _synthesize_answer_with_llm(self, provider: LLMProvider, question: ResearchQuestion, results: list[SearchResult]) -> str:
        if not results:
            return "- 目前未检索到支持该问题的直接证据。"
        evidence = "\n\n".join(
            f"[{idx+1}] title={r.title}\nsource={r.source}\nyear={r.published or 'N/A'}\ndoi={r.doi or 'N/A'}\nsummary={r.summary[:1200]}"
            for idx, r in enumerate(results[:8])
        )
        messages = [
            {
                "role": "system",
                "content": "你是酶工程文献研究助手。必须仅基于给定证据回答；不确定就明确写\"不确定\"并提出需要用户补充的选项。输出中文Markdown，包含：1)直接结论 2)推理依据 3)不确定点与用户澄清问题(选择题)。",
            },
            {"role": "user", "content": f"问题：{question.prompt}\n\n证据片段：\n{evidence}"},
        ]
        try:
            return provider.chat(messages, temperature=0.1)
        except Exception as exc:  # noqa: BLE001 - keep the run alive and make the failure visible.
            return f"- LLM synthesis failed for this question: {exc}"

    def _require_user_confirmations(self, plan, confirmations_path: str) -> None:
        required = [q for q in plan.questions if q.needs_user_confirmation]
        if not required:
            return
        if not confirmations_path:
            template = self.settings.vault_dir / "research_logs" / "required_confirmations.json"
            template.parent.mkdir(parents=True, exist_ok=True)
            template.write_text(json.dumps({q.question_id: {"prompt": q.confirmation_prompt, "options": q.confirmation_options, "selected": ""} for q in required}, ensure_ascii=False, indent=2), encoding="utf-8")
            raise ValueError(f"Missing confirmations. Fill {template} and rerun with --confirmations-file {template}.")
        payload = json.loads(Path(confirmations_path).read_text(encoding="utf-8"))
        for q in required:
            selected = str(payload.get(q.question_id, {}).get("selected", "")).strip()
            if selected not in q.confirmation_options:
                raise ValueError(f"Invalid confirmation for {q.question_id}. Must be one of: {q.confirmation_options}")

    def _search_once(self, keyword: str, *, limit: int) -> list[SearchResult]:
        tasks = [
            ("crossref", lambda: search_crossref(keyword, limit=limit)),
            ("semantic_scholar", lambda: search_semantic_scholar(keyword, limit=limit, api_key=self.settings.semantic_scholar_api_key)),
            ("arxiv", lambda: search_arxiv(keyword, limit=limit)),
            ("pubmed", lambda: search_pubmed(keyword, limit=limit)),
            ("openalex", lambda: search_openalex(keyword, limit=limit)),
        ]
        merged: list[SearchResult] = []
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = {executor.submit(func): name for name, func in tasks}
            for future in as_completed(futures):
                try:
                    merged.extend(future.result())
                except Exception:
                    continue
        return merged

    def _plan_query(self, question: ResearchQuestion, fallback_query: str) -> str:
        section_terms = {
            "功能与边界": "function substrate scope side reaction",
            "机制与结构": "mechanism structure dynamics active site",
            "突变证据": "mutation mutagenesis variant engineering",
            "AI设计先验": "protein language model ProteinMPNN inverse folding Rosetta molecular dynamics generative design",
            "干实验设计契约": "designable residues fixed motif mutation budget scaffold constraint",
            "用户共创议题": "design tradeoff uncertainty multi-objective optimization Pareto",
        }
        hint = section_terms.get(question.section, "")
        return " ".join(part for part in [fallback_query, hint] if part)

    def _reflect_next_query(self, question: ResearchQuestion, previous_query: str, results: list[SearchResult]) -> str:
        gap = self._infer_gap(results).lower()
        if "doi" in gap:
            return f"{previous_query} DOI experimental evidence"
        if "突变" in gap:
            return f"{previous_query} mutagenesis variant"
        if "结构" in gap or "动力学" in gap:
            return f"{previous_query} PDB crystal structure active site kcat Km kinetic characterization"
        return previous_query

    def _infer_gap(self, results: list[SearchResult]) -> str:
        if not results:
            return "no results"
        if not any(r.doi for r in results):
            return "缺少 DOI 级证据，建议追加数据库交叉验证。"
        if not any("mutation" in (r.title + r.summary).lower() for r in results):
            return "缺少直接突变证据，建议下一轮聚焦 mutagenesis。"
        if not any(term in (r.title + r.summary).lower() for r in results for term in ["structure", "pdb", "crystal", "active site"]):
            return "缺少结构证据，建议下一轮聚焦 PDB/active site。"
        if not any(term in (r.title + r.summary).lower() for r in results for term in ["kcat", "km", "kinetic", "catalytic efficiency"]):
            return "缺少动力学证据，建议下一轮聚焦 kcat/Km。"
        return "部分满足，需补充结构/动力学实验证据。"

    def _has_enough_direct_evidence(self, results: list[SearchResult]) -> bool:
        direct_sources = {"pubmed", "openalex", "crossref", "semantic-scholar", "semantic_scholar"}
        direct = [item for item in results if (item.doi or item.source in direct_sources) and item.summary]
        return len(direct) >= 2

    def _dedupe(self, results: list[SearchResult]) -> list[SearchResult]:
        seen: set[str] = set()
        unique: list[SearchResult] = []
        for item in results:
            key = item.doi or item.url or item.title.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _run_post_explore_pipeline(self, discovered_paths: list[Path]) -> dict[str, object]:
        index = LiteratureIndex(self.settings.index_path, self.settings.parsed_dir)
        parser = ParserSelector(self.settings)
        provider = self._build_reasoner()
        analyzer = PaperAnalyzer(provider)
        ingested: list[str] = []
        analyzed: list[str] = []
        analysis_summaries: list[dict[str, object]] = []
        failures: list[dict[str, str]] = []
        for path in discovered_paths:
            try:
                document = parser.parse(path, "text")
                index.add_document(document)
                analysis = analyzer.analyze(document)
                index.save_analysis(analysis)
                ingested.append(document.document_id)
                analyzed.append(document.document_id)
                analysis_summaries.append(self._analysis_summary(analysis))
            except Exception as exc:  # noqa: BLE001 - report the failed paper but keep the run alive.
                failures.append({"path": str(path), "stage": "ingest_analyze", "error": str(exc)})
        wiki_paths = [str(path) for path in WikiBuilder(self.settings.vault_dir, index).build_all()]
        search_chunks = SearchIndex(index, self.settings.vault_dir).rebuild(source="all")
        status = "completed" if not failures else "completed_with_failures"
        return {
            "status": status,
            "ingested_document_ids": ingested,
            "analyzed_document_ids": analyzed,
            "analysis_summaries": analysis_summaries,
            "wiki_paths": wiki_paths,
            "search_chunks": search_chunks,
            "failures": failures,
        }

    def _finalize_knowledge_surfaces(self) -> dict[str, object]:
        index = LiteratureIndex(self.settings.index_path, self.settings.parsed_dir)
        failures: list[dict[str, str]] = []
        try:
            wiki_paths = [str(path) for path in WikiBuilder(self.settings.vault_dir, index).build_all()]
        except Exception as exc:  # noqa: BLE001 - keep manifest traceable.
            wiki_paths = []
            failures.append({"stage": "final_wiki_build", "error": str(exc)})
        try:
            search_chunks = SearchIndex(index, self.settings.vault_dir).rebuild(source="all")
        except Exception as exc:  # noqa: BLE001 - keep manifest traceable.
            search_chunks = 0
            failures.append({"stage": "final_search_index", "error": str(exc)})
        status = "completed" if not failures else "completed_with_failures"
        return {"status": status, "wiki_paths": wiki_paths, "search_chunks": search_chunks, "failures": failures}

    def _analysis_summary(self, analysis) -> dict[str, object]:
        return {
            "document_id": analysis.document_id,
            "title": analysis.title,
            "tldr": analysis.tldr,
            "claims": analysis.claims[:5],
            "evidence": analysis.evidence[:5],
            "limitations": analysis.limitations[:5],
            "open_questions": analysis.open_questions[:5],
            "concepts": analysis.concepts[:10],
        }

    def _fetch_record(self, result: SearchResult, fetch_result: FullTextFetchResult) -> dict[str, str]:
        return {
            "title": result.title,
            "doi": result.doi,
            "url": result.url,
            "pdf_url": result.pdf_url,
            "status": fetch_result.status,
            "source": fetch_result.source,
            "error": fetch_result.error,
        }

    def _duplicate_counts(self, results: list[SearchResult]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in results:
            key = item.doi or item.url or item.title.strip().lower()
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _should_fetch_fulltext(self, result: SearchResult, plan, duplicate_counts: dict[str, int]) -> bool:
        if not (result.pdf_url or result.url):
            return False
        if result.requires_fulltext:
            return True
        text = f"{result.title} {result.summary}".lower()
        scoped_terms = [plan.topic, plan.design_goal, *plan.user_constraints.values()]
        relevance_hits = sum(1 for term in scoped_terms if term and term.lower() in text)
        evidence_terms = [
            "mutation",
            "mutagenesis",
            "variant",
            "kcat",
            "km",
            "kinetic",
            "structure",
            "pdb",
            "crystal",
            "substrate",
            "specificity",
        ]
        evidence_hits = sum(1 for term in evidence_terms if term in text)
        key = result.doi or result.url or result.title.strip().lower()
        repeated = duplicate_counts.get(key, 0) > 1
        return relevance_hits > 0 or evidence_hits > 0 or repeated

    def _write_deep_synthesis(
        self,
        run_dir: Path,
        provider: LLMProvider,
        plan,
        results: list[SearchResult],
        question_answers: dict[str, str],
        rounds: list[dict[str, str]],
        fetch_records: list[dict[str, str]],
        pipeline_report: dict[str, object],
        profile: DepthProfile,
    ) -> tuple[Path, str]:
        evidence = "\n".join(
            f"- [{idx+1}] {item.title} | source={item.source} | year={item.published or 'N/A'} | doi={item.doi or 'N/A'} | url={item.url}"
            for idx, item in enumerate(results[:20])
        )
        answers = "\n\n".join(f"### {qid}\n{answer}" for qid, answer in question_answers.items())
        prompt = f"""Topic: {plan.topic}
Design goal: {plan.design_goal}
Constraints: {json.dumps(plan.user_constraints, ensure_ascii=False)}

Evidence matrix:
{evidence or "No evidence found."}

Question answers:
{answers or "No question answers available."}

Fetch records:
{json.dumps(fetch_records, ensure_ascii=False, indent=2)}

Pipeline report:
{json.dumps(pipeline_report, ensure_ascii=False, indent=2)}

Structured analyses from discovered papers:
{json.dumps(pipeline_report.get("analysis_summaries", []), ensure_ascii=False, indent=2)}

LLM strategy: {profile.llm_strategy}

Write a concise dry-lab enzyme-design synthesis using references/literature-synthesis-schema.md as the main schema and references/literature-coverage-checklist.md as the coverage checklist. Do not invent facts. Use "Not found in current evidence" when missing. Keep literature evidence separate from MODEL_HYPOTHESIS and CREATIVE_HYPOTHESIS. Identify AI-for-protein routes that deserve user discussion: PLM or variant-effect ranking, MPNN redesign, ligand-aware design, structure prediction, Rosetta-style scoring, MD review, scaffold search, motif scaffolding, or backbone generation. For each proposed route, state the design question it answers, uncertainty, cost tier, and pivot trigger. End with 2-4 explicit co-design questions for the user. For quick depth, keep only brief conclusions and Gap Analysis. For standard depth, write the full report. For deep depth, write the full report and be strict about conflicts, missing negative evidence, and unresolved gaps. Include sections as appropriate: Enzyme Profile and Engineering Anchor, Function Boundary, Mechanism and Structure, Substrate Specificity, Designable Space and Site Masks, Mutation Evidence Dataset, Negative Dataset and Failure Modes, Kinetics and Conditions, AI Design Priors, User Co-Design Questions, Gap Analysis."""
        try:
            synthesis = provider.chat(
                [
                    {
                        "role": "system",
                        "content": "You are a rigorous enzyme-engineering synthesis assistant. Ground every design claim in provided evidence. Preserve gaps and conflicts.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
        except Exception as exc:  # noqa: BLE001 - write a traceable fallback artifact.
            synthesis_failure = str(exc)
            synthesis = f"Deep synthesis failed: {exc}"
        else:
            synthesis_failure = ""
        lines = [
            f"# Deep Synthesis: {plan.topic}",
            "",
            f"- Design Goal: {plan.design_goal}",
            f"- Evidence Count: {len(results)}",
            f"- Search Rounds: {len(rounds)}",
            "",
            synthesis,
        ]
        return write_artifact_markdown(run_dir / "deep_synthesis.md", lines), synthesis_failure
