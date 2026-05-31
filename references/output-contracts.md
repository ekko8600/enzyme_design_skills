# Output Contracts

## Candidate Sequence Record

Every proposed or generated sequence must have a structured record:

```json
{
  "candidate_id": "stable unique id",
  "parent_id": "reference or previous candidate id",
  "sequence": "amino-acid sequence",
  "mutations": ["A123V"],
  "scaffold_id": "reference scaffold or generated backbone id",
  "provenance": ["EVIDENCE", "MODEL_HYPOTHESIS"],
  "generation": {
    "method": "model or search method",
    "version": "version or commit",
    "parameters": {},
    "seed": 0
  },
  "metrics": {},
  "hard_filter_status": "pass|fail|pending",
  "pareto_rank": null,
  "cluster_id": "",
  "decision": "retain|reject|regenerate|review",
  "rationale": ""
}
```

## Final Deliverables

Produce:

- ranked candidate table in CSV or JSON;
- FASTA for retained sequences;
- lineage and provenance records;
- metric matrix with model versions and configurations;
- Pareto-front and diversity-cluster summary;
- rejected-candidate log with reasons;
- computational decision log;
- reproducible commands and artifact manifest.

## Literature Dossier

The evidence dossier must include:

- enzyme profile;
- immutable, restricted, redesignable, and unknown regions;
- mutation evidence dataset;
- negative dataset;
- homologs and structural templates;
- AI-design priors;
- conflicts;
- gap analysis.
