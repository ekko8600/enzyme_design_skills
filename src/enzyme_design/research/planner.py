"""Research planning helpers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResearchQuestion:
    """Structured question node for iterative exploration."""

    question_id: str
    section: str
    prompt: str
    required_evidence: str
    depends_on: list[str] = field(default_factory=list)
    needs_user_confirmation: bool = False
    confirmation_prompt: str = ""
    confirmation_options: list[str] = field(default_factory=list)


@dataclass
class ResearchPlan:
    """A transparent search plan for a topic exploration run."""

    topic: str
    design_goal: str
    questions: list[ResearchQuestion]
    keywords: list[str]
    exclude_terms: list[str] = field(default_factory=list)
    user_constraints: dict[str, str] = field(default_factory=dict)


_GOAL_KEYWORDS: dict[str, list[str]] = {
    "activity": ["kcat", "Km", "catalytic efficiency", "mutation activity"],
    "specificity": ["substrate specificity", "binding pocket", "selectivity", "mutant substrate"],
    "stability": ["thermostability", "Tm", "T50", "solvent tolerance"],
    "solubility": ["solubility", "aggregation", "developability", "surface hydrophobicity"],
    "developability": ["aggregation", "solubility", "sequence liability", "surface hydrophobicity"],
}


def build_research_plan(
    topic: str,
    *,
    goal: str = "activity",
    enzyme: str = "",
    target_substrate: str = "",
    host: str = "",
) -> ResearchPlan:
    """Create a deterministic question graph for iterative exploration."""
    clean = " ".join(topic.split())
    goal_clean = goal.strip().lower() or "activity"
    goal_terms = _GOAL_KEYWORDS.get(goal_clean, _GOAL_KEYWORDS["activity"])
    constraints = {
        "enzyme": enzyme.strip(),
        "target_substrate": target_substrate.strip(),
        "host": host.strip(),
        "goal": goal_clean,
    }
    scoped_phrase = " ".join(part for part in [enzyme.strip(), target_substrate.strip(), clean] if part)
    scoped_phrase = scoped_phrase or clean
    questions = [
        ResearchQuestion(
            question_id="q1_function_boundary",
            section="功能与边界",
            prompt=f"{scoped_phrase} 的核心功能、底物边界和副反应是什么？",
            required_evidence="原始研究+综述",
        ),
        ResearchQuestion(
            question_id="q2_mechanism_structure",
            section="机制与结构",
            prompt=f"{scoped_phrase} 的催化机制、关键位点和结构动态证据是什么？",
            required_evidence="结构实验+机制研究",
            depends_on=["q1_function_boundary"],
        ),
        ResearchQuestion(
            question_id="q3_mutation_evidence",
            section="突变证据",
            prompt=f"哪些突变在 {scoped_phrase} 上被证明有效或失败，条件是什么？",
            required_evidence="突变实验",
            depends_on=["q2_mechanism_structure"],
        ),
        ResearchQuestion(
            question_id="q4_ai_design_priors",
            section="AI设计先验",
            prompt=f"针对 {scoped_phrase} 的 {goal_clean} 目标，哪些 PLM、MPNN、结构预测、Rosetta、MD、脚手架搜索或生成式设计路线值得进入候选策略？每条路线回答什么问题？",
            required_evidence="AI方法论文+蛋白设计案例+多源证据汇总",
            depends_on=["q3_mutation_evidence"],
        ),
        ResearchQuestion(
            question_id="q5_drylab_contract",
            section="干实验设计契约",
            prompt=f"关于 {scoped_phrase} 的固定残基、可设计区域、允许突变数量、骨架策略、候选规模、算力预算和交付序列数量是否已明确？",
            required_evidence="用户输入",
            depends_on=["q4_ai_design_priors"],
            needs_user_confirmation=True,
            confirmation_prompt="请确认干实验设计契约。未明确的字段将保留为 OPEN_QUESTION，并在共创阶段逐项讨论。",
            confirmation_options=["已确认，可进入AI路线共创", "部分确认，保留开放问题后进入共创", "未确认，暂停并等待补充"],
        ),
        ResearchQuestion(
            question_id="q6_user_strategy_discussion",
            section="用户共创议题",
            prompt=f"针对 {scoped_phrase}，哪些 AI 路线分叉、目标权衡和不确定性最需要邀请用户共同判断？",
            required_evidence="前序证据+LLM推理+用户偏好",
            depends_on=["q4_ai_design_priors", "q5_drylab_contract"],
        ),
    ]
    keyword_base = [
        scoped_phrase,
        f"{scoped_phrase} review",
        f"{scoped_phrase} structure",
        f"{scoped_phrase} mutagenesis",
        f"{scoped_phrase} protein language model ProteinMPNN Rosetta molecular dynamics",
    ]
    keyword_goal = [f"{scoped_phrase} {term}" for term in goal_terms]
    return ResearchPlan(
        topic=clean,
        design_goal=goal_clean,
        questions=questions,
        keywords=keyword_base + keyword_goal,
        user_constraints={k: v for k, v in constraints.items() if v},
    )
