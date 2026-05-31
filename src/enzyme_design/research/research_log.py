"""Research log rendering."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from enzyme_design.research.fulltext import FullTextFetchResult
from enzyme_design.research.planner import ResearchPlan, ResearchQuestion
from enzyme_design.research.search import SearchResult


def write_research_log(
    vault_dir: Path,
    plan: ResearchPlan,
    results: list[SearchResult],
    question_answers: dict[str, str],
    rounds: list[dict[str, str]],
    path: Path | None = None,
) -> Path:
    slug = _slug(plan.topic)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = path or vault_dir / "research_logs" / f"{date}-{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Research Log: {plan.topic}",
        "",
        f"- Date: {date}",
        "- Mode: iterative network exploration",
        f"- Design Goal: {plan.design_goal}",
        "",
        "## User Constraints",
        *([f"- {k}: {v}" for k, v in plan.user_constraints.items()] or ["- N/A"]),
        "",
        "## Question Graph",
    ]
    lines.append("## Required User Confirmations")
    confirmations = [q for q in plan.questions if q.needs_user_confirmation]
    if confirmations:
        for q in confirmations:
            lines.extend([f"### {q.question_id}", f"- Prompt: {q.confirmation_prompt}", *[f"- [ ] {opt}" for opt in q.confirmation_options], ""] )
    else:
        lines.append("- None")
    lines.append("")
    for question in plan.questions:
        lines.extend(_render_question(question, question_answers.get(question.question_id, "待补充证据。")))

    lines.extend(["## 文献模板问题清晰回答", "下列答案对应 literature coverage checklist / synthesis schema 的核心问题簇：", ""])
    lines.extend(_render_template_answers(plan, question_answers))

    lines.extend(["", "## Multi-round Exploration Trace"])
    for item in rounds:
        lines.extend([
            f"### Round {item.get('round_id', '?')} - {item.get('question_id', 'unknown')}",
            f"- Query: {item.get('query', '')}",
            f"- Result Count: {item.get('result_count', '0')}",
            f"- Gap: {item.get('gap', 'N/A')}",
            "",
        ])

    lines.append("## Results")
    for result in results:
        lines.extend([
            f"### {result.title}",
            f"- Source: {result.source}",
            f"- URL: {result.url}",
            f"- DOI: {result.doi or 'N/A'}",
            f"- Published: {result.published or 'N/A'}",
            f"- Authors: {', '.join(result.authors or []) or 'N/A'}",
            f"- Summary: {result.summary or 'No abstract available.'}",
            "",
        ])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_result_markdown(
    vault_dir: Path,
    result: SearchResult,
    fulltext_markdown: str = "",
    fetch_status: FullTextFetchResult | None = None,
) -> Path:
    slug_base = result.doi.replace("/", "-") if result.doi else _slug(result.title)
    filename = f"{slug_base[:120]}.md"
    path = vault_dir / "papers" / "discovered" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {result.title}",
        "",
        "## Metadata",
        f"- Source: {result.source}",
        f"- URL: {result.url}",
        f"- DOI: {result.doi or 'N/A'}",
        f"- Published: {result.published or 'N/A'}",
        f"- Authors: {', '.join(result.authors or []) or 'N/A'}",
        f"- PDF URL: {result.pdf_url or 'N/A'}",
        f"- Full Text Status: {(fetch_status.status if fetch_status else 'unknown')}",
        f"- Full Text Source: {(fetch_status.source if fetch_status and fetch_status.source else 'N/A')}",
        "",
        "## Abstract / Summary",
        result.summary or "No abstract available from metadata endpoint.",
        "",
    ]
    if fetch_status and fetch_status.error:
        lines.extend(["## Full Text Fetch Error", fetch_status.error, ""])
    if fulltext_markdown:
        lines.extend(["## Full Text", "", fulltext_markdown.strip(), ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_question(question: ResearchQuestion, answer: str) -> list[str]:
    deps = ", ".join(question.depends_on) if question.depends_on else "none"
    return [
        f"### {question.question_id}: {question.section}",
        f"- Prompt: {question.prompt}",
        f"- Depends on: {deps}",
        f"- Required Evidence: {question.required_evidence}",
        "- Current Answer:",
        answer,
        "",
    ]


def _slug(value: str) -> str:
    return "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())[:80]


def _render_template_answers(plan: ResearchPlan, question_answers: dict[str, str]) -> list[str]:
    mapping = [
        ("功能定义与边界", "q1_function_boundary"),
        ("机制与结构关系", "q2_mechanism_structure"),
        ("突变证据与失败案例", "q3_mutation_evidence"),
        ("AI设计先验", "q4_ai_design_priors"),
        ("必须用户确认的干实验设计契约", "q5_drylab_contract"),
        ("需要邀请用户共同判断的策略议题", "q6_user_strategy_discussion"),
    ]
    lines: list[str] = []
    for title, qid in mapping:
        answer = question_answers.get(qid, "待补充证据。")
        lines.extend([f"### {title}", answer, ""])
    return lines
