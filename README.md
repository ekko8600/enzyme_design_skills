# enzyme-design

AI-first dry-lab enzyme sequence design skill for OpenCode.

The user invokes one skill:

```text
Use enzyme-design to improve the thermostability of Proteinase K while
preserving catalytic geometry. Discuss the AI strategy with me before running
expensive jobs.
```

The skill coordinates literature evidence, LLM co-design, AI-for-protein
method selection, computational planning, iterative scoring, and ranked
sequence delivery.

## OpenCode Installation

Import this repository as an OpenCode skills package. OpenCode should load:

```text
.opencode/skills/enzyme-design
```

The OpenCode directory is self-contained: it includes `SKILL.md` and the
references needed during planning. Users only need to invoke `enzyme-design`.

The optional Python runtime provides local literature ingestion, retrieval,
wiki generation, and serial exploration:

```bash
python -m pip install -e .
enzyme-design doctor
```

## Workflow

| Stage | Purpose | Output |
| --- | --- | --- |
| 0 | Clarify objective, sequence, constraints, and compute budget | Design inputs and open questions |
| 1 | Collect source-traceable evidence and design constraints | Evidence dossier and residue masks |
| 2 | Discuss 2-4 AI routes with the user | Approved AI-first design spec |
| 3 | Resolve capabilities and write dry-lab work packages | Approved computational plan |
| 4 | Generate, score, refine, and rank sequences | FASTA, metrics, lineage, rejection log |

Expensive PLM inference, MPNN generation, structure prediction, Rosetta, MD,
and backbone generation require an approved spec and plan.

## AI-For-Protein Scope

The skill can reason about:

- PLM and variant-effect ranking;
- MSA, conservation, coevolution, ASR, and homolog retrieval;
- ProteinMPNN, LigandMPNN, SolubleMPNN, ThermoMPNN, and inverse folding;
- AlphaFold-like structure and complex prediction;
- docking, Rosetta-style scoring, FoldX-like scoring, and MD;
- scaffold search, motif transplantation, RFdiffusion-like backbone design;
- hard filters, uncertainty, Pareto fronts, and diversity clustering.

The LLM does not silently choose important tradeoffs. It invites the user to
discuss scaffold scope, catalytic constraints, model depth, candidate
diversity, uncertainty, and ranking policy.

## Repository Layout

```text
.opencode/skills/enzyme-design/   OpenCode-ready skill package
SKILL.md                          Canonical skill source
references/                       Canonical progressive references
scripts/sync_opencode_skill.py    Sync canonical files into OpenCode package
src/enzyme_design/                Optional literature runtime
tests/                            Runtime regression tests
```

After editing the canonical skill or references, refresh the OpenCode package:

```bash
python scripts/sync_opencode_skill.py
python scripts/validate_opencode_skill.py
```

## Runtime Commands

```bash
enzyme-design ingest <paper.pdf> --parser auto
enzyme-design analyze <document-id> --dry-run
enzyme-design ask --question "<question>" --dry-run --rebuild-index
enzyme-design explore --topic "<topic>" --depth deep --allow-network
enzyme-design build-wiki
enzyme-design doctor
```

Use `ENZYME_DESIGN_*` environment variables for runtime paths and privacy
controls. Legacy `LITERATURE_WIKI_*` variables remain supported as fallbacks.
