# AI Methods For Enzyme Design

## Selection Principle

Choose each component because it answers a specific design question. Use
hybrid pipelines when they reduce uncertainty or improve candidate quality.

## Method Matrix

| Component | Design question | Example method families |
| --- | --- | --- |
| Homolog and scaffold retrieval | What evolutionary design space is plausible? | MSA, HMM search, embedding search, Foldseek-like search, ASR |
| Residue-mask construction | Which sites are fixed, restricted, or redesignable? | conservation, coevolution, contacts, pocket analysis, LLM reasoning |
| Variant proposal | Which substitutions or combinations deserve exploration? | PLM logits, variant-effect models, EVmutation-like scores, combinatorial search |
| Structure-conditioned generation | Which sequences fit the fold and mask? | ProteinMPNN, LigandMPNN, SolubleMPNN, ThermoMPNN, inverse folding |
| Structure or complex prediction | Does fold, pocket, interface, or motif geometry survive? | AlphaFold-like and complex predictors |
| Energetic evaluation | Are packing, clashes, stability proxies, and interfaces acceptable? | Rosetta-style, FoldX-like, docking scores |
| Dynamics review | Does conformational behavior remain acceptable? | MD, enhanced sampling, RMSF, key-contact occupancy, pocket-volume analysis |
| Backbone or scaffold generation | Is a new topology justified? | RFdiffusion-like models, motif scaffolding, generative backbone models |
| Multi-objective selection | Which candidates remain non-dominated? | hard filters, weighted scores, Pareto fronts, clustering, uncertainty-aware ranking |

## Route Selection Heuristics

| Situation | Start with | Escalate when |
| --- | --- | --- |
| Credible scaffold, narrow optimization goal | PLM or variant-effect scan plus local masks | scores conflict or structural regions need redesign |
| Pocket or cofactor geometry dominates | ligand-aware local redesign | local sequence changes cannot recover geometry |
| Stability or flexibility dominates | conservation, stability proxies, and dynamics-informed masks | local redesign repeatedly destabilizes one region |
| Existing scaffold appears constrained | homolog and structural scaffold retrieval | no retrieved scaffold preserves motif and target geometry |
| Motif is known but topology must change | motif-preserving backbone generation | only after cheaper mutation and scaffold routes are inadequate |
| Several metrics compete | Pareto ranking and diversity clustering | model disagreement remains high among finalists |

## Common AI Routes

### Existing-Scaffold Optimization

Use when the current fold is credible and the target is achievable through
mutation:

```text
PLM or variant-effect scan
  -> mask refinement
  -> local MPNN generation
  -> structure prediction
  -> energetic filters
  -> Pareto and diversity selection
```

### Ligand-Aware Pocket Redesign

Use when substrate, cofactor, or catalytic geometry dominates:

```text
fixed catalytic motif and ligand pose
  -> LigandMPNN-like local redesign
  -> complex prediction or docking
  -> pocket-geometry filters
  -> Rosetta-like refinement
  -> MD for top diverse candidates
```

### Stability Optimization

Use when global stability or local flexibility limits the design:

```text
reference structure review
  -> conservation and dynamics-derived masks
  -> ThermoMPNN, PLM, or Rosetta-guided proposals
  -> delta-delta-G and packing filters
  -> structure prediction
  -> MD on finalists
```

### Motif-Preserving Scaffold Exploration

Use when the current scaffold is unlikely to satisfy requirements:

```text
catalytic motif definition
  -> homolog or structural scaffold retrieval
  -> motif-preserving scaffold selection
  -> MPNN sequence design
  -> fold and motif-RMSD filters
```

### New-Backbone Design

Use only when cheaper routes are insufficient:

```text
fixed motif and topology constraints
  -> RFdiffusion-like backbone generation
  -> MPNN design
  -> fold prediction
  -> motif-RMSD, geometry, novelty, and developability ranking
```

## Dry-Lab Metrics

Record method, model version, units, threshold, and interpretation.

| Metric family | Examples |
| --- | --- |
| Sequence plausibility | PLM log-likelihood delta, perplexity, variant-effect score, conservation violations |
| Fold confidence | pLDDT-like confidence, predicted aligned error, fold agreement |
| Motif preservation | catalytic-residue RMSD, distance and angle deviations, cofactor contacts |
| Pocket geometry | contact recovery, pocket volume, ligand-interaction recovery, docking consistency |
| Stability proxy | predicted delta-delta-G, Rosetta total score, packing, clashes, buried unsatisfied polar atoms |
| Dynamics | RMSD, RMSF, key-distance distributions, pocket-volume distributions, contact occupancy |
| Developability proxy | aggregation, solubility, exposed hydrophobics, sequence liabilities |
| Diversity and novelty | sequence identity, mutation count, embedding distance, cluster coverage |
| Uncertainty | ensemble disagreement, seed variance, out-of-distribution indicators |

Do not impose universal cutoffs. Justify thresholds from the objective,
reference baseline, calibration, or an explicit user decision.
