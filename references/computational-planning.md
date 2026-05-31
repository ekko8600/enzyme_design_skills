# Computational Planning

## Purpose

Convert an approved enzyme-design spec into reproducible dry-lab work
packages. Obtain user approval before running design jobs.

## Rules

- Use exact commands only for verified tools.
- Add a capability-resolution task before using an unavailable model or API.
- Run a smoke test before production batches.
- Separate generation, scoring, structure review, dynamics review, ranking,
  and packaging.
- Apply cheap filters before expensive MD or backbone generation.
- Preserve IDs, lineage, versions, parameters, seeds, masks, and provenance.
- Require artifacts and QC; do not promise scientific score improvements.
- Plan branches explicitly.
- Do not add wet-lab tasks.

## Work-Package Template

```markdown
### Work Package N: [Name]

**Purpose:** [computational question]
**Inputs:** [sequence, structure, mask, model, config, prior artifacts]
**Method:** [verified tool or capability-resolution step]
**Outputs:** [artifact paths and schemas]
**Metrics:** [computed metrics and units]
**QC:** [validity and reproducibility checks]
**Decision gate:** [criterion and branch]
**Provenance:** [lineage, version, parameters, seed, labels]
```

## Plan Location

Save to:

`docs/enzyme-design/plans/YYYY-MM-DD-<enzyme-name>-<goal>.md`

## Self-Review

Check:

1. Every spec commitment maps to a work package.
2. Every command refers to a verified or explicitly resolved capability.
3. Sequence IDs, numbering, masks, paths, and schemas are consistent.
4. Metrics record method, version, units, and interpretation.
5. Every branch has a next action.
6. Candidate lineage and reproducibility metadata remain visible.
7. No wet-lab tasks appear.
