# IsPETase Thermostability Engineering — Design Spec

**Date**: 2025-05-31
**Status**: APPROVED (Stage 2 complete)

---

## 1. Objective and Reference Inputs

| Field | Value | Provenance |
|-------|-------|------------|
| **Target enzyme** | IsPETase, _Piscinibacter sakaiensis_ (UniProt: A0A0K8P6T7, PETH_PISS1) | `EVIDENCE` |
| **Reference sequence** | Mature enzyme, residues 28-290 (263 aa), PDB 5XJH numbering | `EVIDENCE` |
| **Reference structure** | PDB 5XJH (1.54 Å, WT, apo) | `EVIDENCE` |
| **Catalytic triad** | S160 (nucleophile), D206 (charge relay), H237 (charge relay) | `EVIDENCE` |
| **Primary goal** | Thermostability: Tm 70-80°C (WT Tm ~48°C) | `DECISION` |
| **Secondary goal** | Maintain or improve PET hydrolytic activity | `DECISION` |
| **Trade-off policy** | Stability and activity equally weighted; no activity sacrifice for Tm gain alone | `DECISION` |

---

## 2. Evidence Map and Provenance Labels

### Confirmed Evidence (Stage 1 synthesis)

| Finding | Label | Key Sources |
|---------|-------|-------------|
| WT Tm = 46.8-48°C (DSF) | `EVIDENCE` | DOI: 10.1038/s41467-017-02255-z; 10.1038/s41598-020-79031-5 |
| Catalytic triad S160-D206-H237 confirmed by mutagenesis | `EVIDENCE` | DOI: 10.1038/s41467-017-02255-z; 10.1073/pnas.1718804115 |
| C203-C239 disulfide contributes ~13°C | `EVIDENCE` | DOI: 10.1038/s41467-017-02255-z |
| Lacks Ca²⁺ binding site (unlike thermostable homologs) | `EVIDENCE` | DOI: 10.1038/s41467-017-02255-z |
| β8-α6 loop is primary flexible region | `EVIDENCE` | DOI: 10.3390/molecules29061338 (MD) |
| D186 mutations yield +8.9 to +12.9°C | `EVIDENCE` | DOI: 10.3390/molecules29061338 |
| S121E/D186H/R280A foundational thermostabilizing set | `EVIDENCE` | DOI: 10.1073/pnas.1718804115 |
| Salt bridge I168R/S188E yields +8.7°C | `EVIDENCE` | DOI: 10.1016/j.ijbiomac.2023.125940 |
| FAST-PETase: ML-designed, Tm ~63°C | `EVIDENCE` | DOI: 10.1038/s41586-022-04599-z |
| HotPETase: Tm 80.5°C but 65°C activity ~3h | `EVIDENCE` | DOI: 10.1021/acscatal.3c02922 |
| IsPETase scaffold ceiling ~65-69°C without backbone redesign | `INFERENCE` | Synthesized from all engineered variant data |
| Stability-activity trade-off rooted in W185 dynamics | `INFERENCE` | DOI: 10.1002/anie.202501846; MD studies |
| Epistatic effects confirmed in combinatorial mutations | `EVIDENCE` | DOI: 10.1021/acssynbio.5c00494 |

### Open Questions

| Question | Label | Impact |
|----------|-------|--------|
| Can IsPETase scaffold realistically reach 70-80°C Tm without backbone redesign? | `OPEN_QUESTION` | May require scaffold search / backbone generation |
| Will multi-mutation combinations preserve fold? | `OPEN_QUESTION` | Will be answered by AF2 predictions (Gate 2) |
| Can MD-identified flexible regions be rigidified without activity loss? | `OPEN_QUESTION` | Will be answered by MD verification (Gate 4) |

---

## 3. Residue Masks and Numbering

**Numbering**: PDB 5XJH author numbering (UniProt numbering for residues 34-290). The mature enzyme (UniProt 28-290, 263 aa) starts at PDB 34.

| Classification | Residues / Regions | Rationale | Provenance |
|----------------|-------------------|-----------|------------|
| **Immutable** | S160, D206, H237 (catalytic triad) | Essential for catalysis; any mutation abolishes activity | `EVIDENCE` |
| **Immutable** | R87, S161, W185 (substrate binding) | Direct PET substrate interactions | `EVIDENCE` |
| **Restricted** | C203, C239 (disulfide bond) | Critical for structural integrity (~13°C contribution) | `EVIDENCE` |
| **Restricted** | C273, C289 (disulfide bond) | C-terminal stability | `EVIDENCE` |
| **Restricted** | Hydrophobic core residues (identified by SASA < 5%) | Maintain fold integrity | `INFERENCE` |
| **Designable (priority)** | β8-α6 loop region (residues ~185-210) | MD-identified primary flexible region | `EVIDENCE` |
| **Designable (priority)** | β6-β7 loop region (residues ~130-150) | MD-identified secondary flexible region | `EVIDENCE` |
| **Designable** | Surface loops and solvent-exposed residues | Can tolerate mutations without core disruption | `INFERENCE` |
| **Designable** | Known positive sites: S121, D186, I139, R280, S242, N246, I168, S188, A171, S193, N233, W159, F229 | Literature-supported thermostabilization sites | `EVIDENCE` |

---

## 4. Selected AI Routes and Rejected Alternatives

### Selected: Three-route parallel approach

| Route | Scope | Method | Role |
|-------|-------|--------|------|
| **A** | PLM-guided + MPNN local redesign | ESM-2 zero-shot → Mask → ProteinMPNN → AF2 → Rosetta | Discover novel mutations + targeted loop redesign |
| **B** | Cumulative mutation + epistasis check | Known positives → FoldX + Rosetta combinatorial → GRAPE → AF2 | Risk-controlled accumulation of proven stabilizers |
| **C** | Large-scale MPNN + MD | ProteinMPNN full/wide redesign → AF2 → Rosetta → GROMACS MD | Aggressive scaffold-wide exploration; backup if A+B insufficient |

### Rejected

- **LCC/KbPETase scaffold switch**: User decided to continue with IsPETase scaffold (`DECISION`)
- **Single-route only**: User opted for comprehensive coverage (`DECISION`)
- **RFdiffusion backbone generation**: Premature; only triggered if all three routes fail to approach target Tm

---

## 5. Generation Models and Constraints

| Route | Model | Parameters | Constraints |
|-------|-------|-----------|-------------|
| A1 | ESM-2 (650M) | LLR scoring, 263 pos × 19 AA | None (full scan) |
| A3 | ProteinMPNN | T=0.3, 1000 seq | Fixed S160,D206,H237; redesignable mask from A2 |
| B2 | FoldX BuildModel | --temperature 298 | Point mutations per combinatorial matrix |
| B2 | Rosetta cartesian_ddg | ref2015, 3 repeats | -- |
| B4 | GRAPE strategy | Greedy accumulation, 5-15 rounds | Epistasis check: |ΔΔG_pred − ΣΔΔG_single| > 2 kcal/mol |
| C1 | ProteinMPNN | T=0.3 (500 seq) + T=0.5 (500 seq) | Fixed S160,D206,H237; all else designable |
| A4/B5/C2 | AlphaFold2 | model_1, no templates | Single-chain prediction |
| C3 | Rosetta ref2015 + ddg_monomer | Default params | -- |
| C4 | Rosetta FastRelax | 5 repeats | -- |
| C5 | GROMACS | 100 ns, 300K, TIP3P | AMBER99SB-ILDN |

---

## 6. Scoring Matrix and Selection Policy

### Hard Filters (must pass ALL)

| # | Filter | Method | Threshold | Layer |
|---|--------|--------|-----------|-------|
| F1 | PLM likelihood | ESM-2 LLR | > 0 (better than WT) | Layer 1 |
| F2 | Conservation violation | MSA conservation score | < 3 high-conservation sites mutated | Layer 1 |
| F3 | Fold confidence | AlphaFold2 pLDDT | > 80 | Layer 2 |
| F4 | Catalytic geometry 1 | S160-H237 Cα distance | < WT + 2.0 Å | Layer 2 |
| F5 | Catalytic geometry 2 | S160-H237-D206 RMSD | < 1.5 Å | Layer 2 |
| F6 | Stability proxy | FoldX ΔΔG | < +2.0 kcal/mol | Layer 3 |
| F7 | No steric clashes | Rosetta fa_rep | < WT + 10% | Layer 3 |

### Ranking Signals (soft, for Pareto)

| # | Metric | Weight | Direction |
|---|--------|--------|-----------|
| R1 | ESM-2 LLR score | 0.15 | Higher better |
| R2 | AlphaFold2 pLDDT | 0.20 | Higher better |
| R3 | FoldX ΔΔG | 0.20 | Lower (more negative) better |
| R4 | Catalytic RMSD | 0.15 | Lower better |
| R5 | Rosetta packstat | 0.10 | Higher better |
| R6 | MSA conservation score | 0.10 | Higher (more conserved mutations) better |
| R7 | Number of mutations | 0.10 | Fewer better (parsimony) |

### Pareto and Diversity Policy

- Select Pareto-optimal candidates from each route independently
- Cluster by sequence identity (90% threshold using MMseqs2)
- Retain 1-3 representatives per cluster
- Final output: 20-50 ranked sequences

---

## 7. Adaptive Decision Gates

### Gate 1: Post PLM Scan (Route A only)
```
Input: ESM-2 LLR matrix (263×19)
Inspect: Top 5% mutation scores, their structural locations
  → Clustered in known regions: prioritize MPNN on those regions
  → Diffuse/no clear signal: add conservation + contact constraints
  → Flat (no high scores): deprioritize route A
Action: Update A2 mask OR reduce A weight in final ranking
```

### Gate 2: Post AF2 Prediction (All routes)
```
Input: Per-candidate AF2 output (pLDDT, PAE, catalytic distances)
Inspect: pLDDT distribution, catalytic geometry
  → pLDDT > 85 AND catalytic RMSD < 1.0 Å: pass to Layer 3
  → pLDDT 70-85 OR catalytic RMSD 1.0-2.0 Å: tighten constraints, regenerate
  → pLDDT < 70 OR catalytic RMSD > 2.0 Å: reduce design scope, regenerate
Action: Regenerate if >30% candidates fail
```

### Gate 3: Post Energy Scoring (All routes)
```
Input: FoldX ΔΔG, Rosetta packstat
Inspect: ΔΔG distribution, packing quality
  → Mean ΔΔG < -1.0 AND packstat > 0.60: consolidate candidates
  → Mean ΔΔG > 0: return to mask refinement
  → Bimodal: retain passing cluster, regenerate failing cluster
```

### Gate 4: Post MD Validation (Route C, or top candidates from A+B)
```
Input: GROMACS trajectories, RMSD/RMSF, key distances
Inspect: Backbone RMSD, catalytic distance stability, regional RMSF
  → RMSD < 2.5 Å AND catalytic distances stable: final candidate
  → Regional RMSF spike: update mask for that region, re-enter route A
  → Widespread instability: reduce design aggressiveness, re-enter route C
```

---

## 8. Final Deliverable Requirements

| # | Artifact | Format | Description |
|---|----------|--------|-------------|
| 1 | Ranked candidates | CSV | candidate_id, sequence, mutations, all metric scores, route, rank |
| 2 | Candidate FASTA | .fasta | All retained sequences with headers encoding candidate_id |
| 3 | Mutation table | CSV | candidate_id, mutation_list, route, source |
| 4 | Metric matrix | CSV | Full metric values with model versions and parameters |
| 5 | Pareto front summary | Markdown table | Non-dominated candidates with key metrics |
| 6 | Rejected candidate log | CSV | candidate_id, rejection gate, reason |
| 7 | Decision gate log | Markdown | Each gate outcome with branch decisions |
| 8 | Reproducibility manifest | JSON | Model versions, seeds, parameters, commands |

---

## 9. Self-Review Checklist

- [x] Objective and reference inputs defined
- [x] Evidence map with provenance labels
- [x] Residue masks and numbering convention (PDB 5XJH)
- [x] Three routes selected with rationale; rejected alternatives documented
- [x] Generation models and parameters specified per route
- [x] Hard filters (7) and ranking signals (7) defined
- [x] Adaptive decision gates (4) with inputs, criteria, and actions
- [x] Final deliverables specified
- [ ] No wet-lab tasks present
- [ ] No placeholders or unresolved numbering ambiguity

**Status: STAGE 2 COMPLETE — APPROVED BY USER. Proceed to Stage 3.**
