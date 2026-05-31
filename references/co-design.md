# Co-Design Workflow

## Purpose

Use structured dialogue to turn evidence and user intent into an approved
AI-first enzyme-design spec.

## Conversation Rules

- Ask one question at a time.
- Prefer concrete options when the tradeoff is clear.
- Propose 2-4 routes before settling on one.
- Lead with a recommendation and state why.
- Present the spec section by section and obtain approval after each section.
- Return to earlier assumptions when new model results invalidate them.
- Use LLM reasoning actively: synthesize evidence, generate hypotheses,
  compare routes, identify hidden assumptions, and surface disagreement.
- Do not collapse consequential tradeoffs without user input.

## User Discussion Checkpoints

Invite the user to reason together when the answer depends on priorities rather
than facts. Use one focused question at a time.

| Checkpoint | Discuss with the user |
| --- | --- |
| Objective | Which property is primary when metrics conflict? |
| Search scope | Conservative mutations, local redesign, scaffold search, or new backbone? |
| Catalytic constraints | Which residues and geometries are inviolable versus negotiable? |
| Model portfolio | Cheap broad PLM ranking or deeper structure, Rosetta, and MD review? |
| Candidate selection | Confidence-heavy shortlist or more diverse exploratory portfolio? |
| Uncertainty | Which unresolved model disagreements justify another computational round? |

For each checkpoint:

1. summarize relevant evidence and uncertainty;
2. explain why the decision changes the pipeline;
3. offer 2-3 concrete options with tradeoffs;
4. recommend one option;
5. ask the user to choose, revise, or propose an alternative.

The LLM may introduce creative hypotheses beyond literature when they remain
clearly labeled and falsifiable through computational analysis.

## Sequence-Design Contract

Resolve:

- reference sequence and residue numbering;
- fixed, restricted, redesignable, and backbone-flexible regions;
- ligand, cofactor, motif, and interface constraints;
- mutation scope: single-site, combinatorial, local redesign, full inverse
  folding, scaffold search, or new backbone;
- hard filters, ranking signals, Pareto policy, and diversity requirement;
- candidate count, compute budget, iteration ceiling, and final output size.

## LLM Reasoning Canvas

Before recommending a route, reason through this canvas and show the compact
result to the user:

| Field | Required content |
| --- | --- |
| Objective | Primary metric, secondary metrics, unacceptable regressions |
| Fixed knowledge | Evidence-backed residues, motifs, structures, and priors |
| Unknowns | Missing facts and model uncertainties that could change the route |
| Hypotheses | Evidence-backed, model-derived, and creative ideas kept separate |
| Search-space policy | Current scaffold, local redesign, alternative scaffold, or new backbone |
| Candidate routes | 2-4 plausible AI pipelines |
| Information gain | What each computational step teaches before the next decision |
| Cost ladder | Cheap filters first; expensive structure, Rosetta, MD, or generation only when justified |
| User decisions | Priority tradeoffs that cannot be settled from evidence alone |

The canvas is not hidden chain-of-thought. It is a concise decision record:
assumptions, alternatives, evidence, uncertainty, and recommendations.

## Strategy Proposal Template

For each route include:

- objective and rationale;
- provenance labels for important claims;
- required inputs;
- generation models;
- scoring, filtering, and uncertainty models;
- computational cost;
- risks;
- pivot trigger;
- expected sequence deliverables.

## Adaptive Decision Loops

Define branches before execution:

```text
cheap sequence scoring
  -> if interpretable high-scoring regions emerge: refine masks and generate
  -> if scores conflict: add evolutionary or structural constraints

structure prediction
  -> if fold and catalytic geometry pass: run energetic filters
  -> if fold passes but motif fails: tighten constraints and regenerate
  -> if fold fails broadly: reduce redesign scope or switch scaffold

MD or Rosetta review
  -> if proxies improve: retain on Pareto front
  -> if one region repeatedly destabilizes: revise mask and regenerate
  -> if models disagree: preserve uncertainty and add an orthogonal model
```

Each branch must name inputs, inspected metrics, criteria, and next action.

## Design Spec

Save to:

`docs/enzyme-design/specs/YYYY-MM-DD-<topic>-design.md`

Include:

1. objective and reference inputs;
2. evidence map and provenance labels;
3. residue masks and numbering;
4. selected AI route and rejected alternatives;
5. generation models and constraints;
6. scoring matrix, hard filters, Pareto ranking, and diversity policy;
7. adaptive decision gates and pivot rules;
8. final sequence requirements and reproducibility metadata.

Self-review placeholders, contradictions, overconfident model claims, missing
thresholds, numbering ambiguity, incomplete branches, and scope creep. Obtain
user approval before planning execution.
