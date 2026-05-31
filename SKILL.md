---
name: enzyme-design
description: >-
  Use when designing or optimizing enzyme sequences with literature evidence,
  protein language models, structure prediction, inverse folding, MPNN,
  Rosetta, docking, MD, scaffold search, motif scaffolding, or generative
  protein models. Applies to stability, activity-proxy, specificity, pocket,
  interface, solubility, developability, and multi-objective dry-lab design.
---

# Enzyme Design

## Scope

Use this single skill for end-to-end AI-first enzyme sequence design:

1. frame requirements;
2. collect evidence and constraints;
3. co-design an AI strategy with the user;
4. write an approved computational plan;
5. generate, score, refine, and rank sequences;
6. package reproducible sequence deliverables.

This skill covers dry-lab work only. Do not plan expression, purification,
assays, wet-lab screening, or physical validation.

## Progressive References

Read only the references required by the current stage:

| Stage | Required reference |
| --- | --- |
| Evidence retrieval, paper ingestion, local knowledge-base queries | [evidence-research.md](references/evidence-research.md) |
| Strategy creation or method selection | [ai-methods.md](references/ai-methods.md) |
| Brainstorming, approvals, or design-spec writing | [co-design.md](references/co-design.md) |
| Computational work-package planning or execution | [computational-planning.md](references/computational-planning.md) |
| Candidate schemas, metric records, or final artifacts | [output-contracts.md](references/output-contracts.md) |
| Literature runtime CLI usage | [literature-runtime.md](references/literature-runtime.md) |

## Non-Negotiable Rules

### Separate Evidence From Hypotheses

Label important design statements:

- `EVIDENCE`: cited literature, database, or user data;
- `INFERENCE`: reasoned transfer from evidence;
- `MODEL_HYPOTHESIS`: model-, score-, or simulation-derived proposal;
- `CREATIVE_HYPOTHESIS`: LLM/user-generated design idea;
- `DECISION`: user-approved constraint, threshold, or route;
- `OPEN_QUESTION`: unresolved item that may alter design.

Never present model scores as facts. Preserve model version, inputs,
configuration, seeds, and candidate lineage.

### Approve Before Expensive Execution

Before the user approves both the design spec and computational plan, do not
run PLM inference, sequence generation, structure prediction, docking,
Rosetta, MD, backbone generation, GPU jobs, or large batches.

Literature retrieval, local inspection, reasoning, and plan writing are
allowed. If the user explicitly wants to override the gate, explain the risk
and record the override as a `DECISION`.

## Workflow

### Stage 0: Frame Requirements

Ask one question at a time. Collect the minimum useful context:

- reference sequence, accession, structure, or family;
- design objective and priority tradeoffs;
- substrate, ligand, cofactor, catalytic residues, and fixed motifs;
- allowed mutations, redesignable regions, forbidden sites, and backbone
  policy;
- candidate budget, compute budget, and desired final sequence count.

Carry unknowns forward as `OPEN_QUESTION`.

### Stage 1: Build Evidence And Constraints

Read [evidence-research.md](references/evidence-research.md). Use deep
literature exploration when the request is design-sensitive or the evidence
base is thin. Produce a dossier with:

- immutable, restricted, redesignable, and unknown regions;
- positive and negative variants;
- homologs, templates, ligand-bound structures, and useful priors;
- conflicts, uncertainty, and evidence gaps.

Literature constrains the search space. It does not choose the AI route.

### Stage 2: Co-Design The AI Strategy

Read [co-design.md](references/co-design.md) and
[ai-methods.md](references/ai-methods.md). Collaborate with the user to:

1. define the sequence-design contract;
2. propose 2-4 distinct AI routes with tradeoffs;
3. recommend a route or portfolio;
4. define generation methods, filters, metrics, Pareto ranking, diversity
   selection, and adaptive decision gates;
5. write and self-review the design spec;
6. obtain user approval.

The LLM should create strategies, not merely summarize papers. It may propose
novel model combinations and hypothesis-driven redesign loops when provenance,
risk, and decision criteria remain explicit.

Do not silently resolve consequential tradeoffs. Invite the user to discuss:

- conservative optimization of the current scaffold versus exploratory
  scaffold or backbone design;
- catalytic-geometry preservation versus broader sequence exploration;
- candidate diversity versus confidence;
- cheap broad screening versus expensive MD or Rosetta depth;
- weighted ranking versus Pareto selection;
- uncertainty that should remain visible rather than collapsed into one score.

For each discussion point, explain why it matters, present concrete options,
state a recommendation, and ask one focused question.

### Stage 3: Write The Computational Plan

Read [computational-planning.md](references/computational-planning.md) and
[output-contracts.md](references/output-contracts.md). Convert the approved
spec into reproducible dry-lab work packages.

Use exact commands only for verified tools. Add capability-resolution and
smoke-test tasks for unavailable components. Obtain user approval before
execution.

### Stage 4: Execute And Iterate

Execute approved work packages. Use cheap filters before expensive methods.
At each decision gate:

1. inspect recorded metrics and uncertainty;
2. retain, reject, regenerate, or review candidates;
3. revise masks, thresholds, or model route when required;
4. return to Stage 2 if the strategy materially changes.

Finish with ranked FASTA sequences, metric tables, candidate lineage,
rejection reasons, model metadata, decision logs, and reproducible commands.

## Common Mistakes

1. Treating AI methods as a side note instead of the main design machinery.
2. Ranking by one score instead of hard constraints, orthogonal metrics,
   uncertainty, diversity, and Pareto analysis.
3. Running MD or backbone generation before cheaper filters narrow candidates.
4. Hiding speculative designs behind confident wording.
5. Inventing commands, available models, residue effects, or thresholds.
6. Letting wet-lab planning dilute the sequence-design objective.
