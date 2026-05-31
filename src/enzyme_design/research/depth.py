"""Depth-based exploration budget profiles."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DepthProfile:
    """Effective exploration budget for one run."""

    depth: str
    effective_limit: int
    effective_max_rounds: int
    effective_reflection_cycles: int
    unique_result_cap: int
    fulltext_cap: int
    llm_strategy: str

    def to_dict(self) -> dict[str, int | str]:
        return asdict(self)


_DEFAULTS: dict[str, DepthProfile] = {
    "quick": DepthProfile(
        depth="quick",
        effective_limit=3,
        effective_max_rounds=3,
        effective_reflection_cycles=1,
        unique_result_cap=6,
        fulltext_cap=2,
        llm_strategy="brief conclusions and gap analysis only",
    ),
    "standard": DepthProfile(
        depth="standard",
        effective_limit=5,
        effective_max_rounds=5,
        effective_reflection_cycles=2,
        unique_result_cap=10,
        fulltext_cap=5,
        llm_strategy="full report with evidence-grounded design brief",
    ),
    "deep": DepthProfile(
        depth="deep",
        effective_limit=8,
        effective_max_rounds=6,
        effective_reflection_cycles=3,
        unique_result_cap=18,
        fulltext_cap=10,
        llm_strategy="full report with stricter conflict, gap, and negative-evidence analysis",
    ),
}


def resolve_depth_profile(
    depth: str,
    *,
    limit: int | None = None,
    max_rounds: int | None = None,
    reflection_cycles: int | None = None,
) -> DepthProfile:
    """Resolve requested depth plus explicit overrides into an effective budget."""
    base = _DEFAULTS.get(depth, _DEFAULTS["standard"])
    return DepthProfile(
        depth=base.depth,
        effective_limit=limit if limit is not None else base.effective_limit,
        effective_max_rounds=max_rounds if max_rounds is not None else base.effective_max_rounds,
        effective_reflection_cycles=reflection_cycles if reflection_cycles is not None else base.effective_reflection_cycles,
        unique_result_cap=max((limit if limit is not None else base.effective_limit) * 2, base.unique_result_cap),
        fulltext_cap=base.fulltext_cap,
        llm_strategy=base.llm_strategy,
    )
