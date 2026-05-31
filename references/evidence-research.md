# Evidence Research

## Purpose

Build a source-traceable evidence and constraint dossier for enzyme design.
Use the bundled `enzyme-design` literature runtime when local ingestion,
retrieval, wiki generation, or serial network exploration is useful.

## Deep Exploration

When parallel agents are available, dispatch independent lanes:

| Lane | Scope |
| --- | --- |
| `function-boundary` | function, substrate boundary, side reactions, homolog families |
| `structure-mechanism` | catalytic residues, motifs, structures, dynamics, cofactors |
| `mutation-evidence` | positive and negative variants, transferability, context |
| `conditions-metrics` | comparable quantitative measurements and conditions |
| `ai-design-priors` | computational methods, model precedents, useful datasets |
| `risk-gaps` | conflicts, failed transfers, missing evidence, uncertainty |

Child agents must return structured findings and evidence IDs. They must not
write shared files. Deduplicate by DOI, PMID, URL, database ID, or normalized
title.

## Dossier Contract

Extract:

- enzyme profile and design objective;
- immutable, restricted, redesignable, and unknown regions;
- positive and negative mutation evidence;
- homologs, scaffolds, templates, and ligand-bound structures;
- AI-design precedents and transferable priors;
- conflicts and gap analysis.

Use `high` confidence only for direct primary evidence or curated databases.
Use `medium` for indirect evidence and cross-study patterns. Use `low` for
model predictions, weak abstracts, analogies, or unresolved inference.

## Research Rules

- Preserve contradictory claims.
- Never invent residue numbers, structures, substrates, or effects.
- Distinguish reported variants from proposed variants.
- Continue into co-design when evidence is weak; carry gaps as
  `OPEN_QUESTION`.

For CLI commands and privacy controls, read
[literature-runtime.md](literature-runtime.md).
