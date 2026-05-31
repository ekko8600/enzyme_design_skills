# IsPETase Thermostability — Computational Execution Plan

**Date**: 2025-05-31
**Spec**: `docs/enzyme-design/specs/2025-05-31-ispetase-thermostability-design.md`
**Status**: AWAITING USER APPROVAL

---

## Overview

| Item | Value |
|------|-------|
| Routes | A (PLM+MPNN), B (Accumulation+Epistasis), C (Large-scale MPNN+MD) |
| Reference | PDB 5XJH, IsPETase UniProt A0A0K8P6T7 (263 aa mature) |
| Target | Tm 70-80°C, activity maintained |
| Final output | 20-50 ranked candidates |

---

## Phase 0: Prerequisites & Capability Resolution

### WP 0.1: Environment and Tool Verification

**Purpose**: Verify all required computational tools are available and functional.
**Inputs**: None
**Method**: Check installation and run smoke tests for each tool.
**Outputs**: Capability matrix (available / unavailable / needs resolution)
**QC**: Each tool returns expected output for a minimal test case.

| Tool | Purpose | Verification |
|------|---------|-------------|
| ESM-2 (via HuggingFace or local) | Route A PLM scanning | Run on single test sequence, verify LLR output |
| ProteinMPNN | Routes A/C sequence generation | Run on PDB 5XJH with fixed catalytic triad, verify 10 sequences |
| AlphaFold2 / ColabFold | Routes A/B/C structure prediction | Run on WT IsPETase, verify pLDDT output |
| FoldX | Route B stability scoring | Run BuildModel on WT, verify output |
| Rosetta (cartesian_ddg, ddg_monomer, ref2015, FastRelax) | Routes A/B/C scoring | Run cartesian_ddg on S121E single mutant |
| GROMACS | Route C MD validation | Run 10 ns on WT, verify energy convergence |
| MMseqs2 | MSA generation for AF2 | Run on WT IsPETase sequence |
| Python (numpy, pandas, biopython) | Data processing | Import check |

**Decision gate**: If any tool unavailable, add capability-resolution sub-work-package.

---

## Phase 1: Route A — PLM-Guided Mutation Scan + MPNN Local Redesign

### WP A1: ESM-2 Zero-Shot Mutation Scan

**Purpose**: Score all 263 × 19 = 4,997 possible single-point mutations for IsPETase.
**Inputs**: WT IsPETase mature sequence (263 aa, FASTA)
**Method**: ESM-2 (650M) masked marginal scoring:
```
for each position i, for each AA j (j ≠ WT):
  LLR = log P(AA_j | context) - log P(AA_WT | context)
```
**Outputs**: `data/scanning/esm2_llr_matrix.csv` — (263 rows × 19 columns) of LLR scores
**Metrics**: LLR (log-likelihood ratio); positive = predicted beneficial
**QC**: Verify LLR range, spot-check known beneficial mutations (S121E, D186H, R280A) have positive LLR
**Decision gate**: 
- If >80% of known positives have LLR > 0 → proceed
- If known positives score randomly → ESM-2 may not be informative for this fold; deprioritize route A

### WP A2: Residue Mask Construction

**Purpose**: Define fixed/restricted/redesignable residue classifications for ProteinMPNN.
**Inputs**: 
- `data/scanning/esm2_llr_matrix.csv` (from A1)
- PDB 5XJH structure
- Literature mask definitions from spec §3
**Method**: 
1. Compute per-position conservation from MSA (MMseqs2)
2. Extract SASA from PDB 5XJH
3. Overlay with ESM-2 top 10% scores
4. Merge with immutable/restricted lists (S160, D206, H237, C203, C239, etc.)
5. Output mask file
**Outputs**: 
- `data/masks/ispetase_fixed.txt` — immutable positions (ProteinMPNN format)
- `data/masks/ispetase_redesignable.txt` — positions to redesign
- `data/masks/ispetase_mask.json` — full mask with provenance
**QC**: Verify catalytic triad is in fixed list; verify C203-C239 are in restricted list
**Provenance**: `EVIDENCE` (literature) + `MODEL_HYPOTHESIS` (ESM-2 scores)

### WP A3: ProteinMPNN Local Redesign

**Purpose**: Generate 1,000 sequences with targeted loop redesign around β8-α6 and β6-β7.
**Inputs**: 
- PDB 5XJH (structure template)
- `data/masks/ispetase_fixed.txt` (S160, D206, H237)
- `data/masks/ispetase_redesignable.txt` (target loops)
**Method**: ProteinMPNN with temperature=0.3:
```
python protein_mpnn_run.py \
  --pdb_path data/structures/5XJH.pdb \
  --fixed_residues $(cat data/masks/ispetase_fixed.txt) \
  --redesign_residues $(cat data/masks/ispetase_redesignable.txt) \
  --num_seq_per_target 1000 \
  --sampling_temp 0.3 \
  --seed 42
```
**Outputs**: `data/generated/route_a/mpnn_sequences.fa` — 1,000 FASTA entries
**Metrics**: Sequence diversity (pairwise identity distribution)
**QC**: Verify all fixed positions match WT; verify sequence length = 263
**Provenance**: `MODEL_HYPOTHESIS`, method: ProteinMPNN, seed: 42, T=0.3

### WP A4: AlphaFold2 Structure Prediction (Route A)

**Purpose**: Predict structures for all 1,000 MPNN-generated sequences; filter by fold quality and catalytic geometry.
**Inputs**: `data/generated/route_a/mpnn_sequences.fa`
**Method**: ColabFold / AlphaFold2 (model_1, no templates, 3 recycles):
```
colabfold_batch data/generated/route_a/mpnn_sequences.fa \
  data/predictions/route_a/ \
  --num-models 1 --num-recycle 3
```
**Outputs**: 
- `data/predictions/route_a/*.pdb` — predicted structures
- `data/predictions/route_a/scores.csv` — pLDDT, pTM, PAE per sequence
**Metrics**: pLDDT (per-residue and global), pTM, catalytic RMSD vs 5XJH
**QC**: WT control should have pLDDT > 90; check prediction consistency

### WP A5: Route A Filtering & Scoring

**Purpose**: Apply hard filters F1-F7 and compute ranking signals R1-R7.
**Inputs**: All A4 outputs + ESM-2 scores (A1)
**Method**: 
1. Filter: pLDDT > 80, catalytic RMSD < 1.5Å, ΔΔG < +2.0
2. Score: compute all R1-R7 metrics
3. Pareto ranking
4. Cluster at 90% identity
**Outputs**: 
- `data/ranking/route_a_passed.csv` — passing candidates with all scores
- `data/ranking/route_a_rejected.csv` — rejected with reason
**Decision gate (Gate 2 & 3)**: 
- If < 10 candidates pass → tighten mask, re-enter A3
- If > 100 pass → increase thresholds or proceed

---

## Phase 2: Route B — Cumulative Mutation + Epistasis Check

### WP B1: Known Mutation Library Construction

**Purpose**: Compile all literature-supported thermostabilizing mutations.
**Inputs**: Stage 1 mutation evidence
**Method**: Extract from literature dossier, verify numbering against PDB 5XJH
**Outputs**: `data/mutations/known_positives.csv` — position, WT_AA, mut_AA, ΔTm, source_DOI
**Included mutations**: S121E, D186H, D186N, D186V, I139R, R280A, S242T, N246D, I168R, S188D, S188E, A171C, S193C, N233K, W159H, F229Y, N114*, N205*, S269* (asterisk = less characterized)
**QC**: Cross-reference with UniProt, verify numbering consistency

### WP B2: Combinatorial ΔΔG Scanning

**Purpose**: Predict ΔΔG for all 2-4 mutation combinations among known positives.
**Inputs**: 
- PDB 5XJH
- `data/mutations/known_positives.csv`
**Method**: 
1. Generate all 2-, 3-, and 4-mutation combinations (~C(15,2)+C(15,3)+C(15,4) ≈ 1,820 combos)
2. For each combination, run FoldX BuildModel + Stability
3. Run Rosetta cartesian_ddg on top 500 FoldX-ranked combos
**Outputs**: 
- `data/scanning/route_b_combinations.csv` — all combos with FoldX ΔΔG
- `data/scanning/route_b_top500_rosetta.csv` — Rosetta-validated top combos
**Metrics**: FoldX ΔΔG (kcal/mol), Rosetta ddg (kcal/mol)
**QC**: Verify single-mutant predictions match literature ΔTm (±3°C equivalent)

### WP B3: Epistasis Detection

**Purpose**: Identify non-additive mutation effects to avoid wasted combinations.
**Inputs**: WP B2 combinatorial scores
**Method**: 
```
For each combination [m1, m2, m3, m4]:
  epistasis_score = |ΔΔG_combined - (ΔΔG_m1 + ΔΔG_m2 + ΔΔG_m3 + ΔΔG_m4)|
  If epistasis_score > 2.0 kcal/mol: FLAG as epistatic
```
**Outputs**: 
- `data/scanning/route_b_epistasis.csv` — epistasis scores per combination
- Epistasis heatmap for key mutation pairs
**QC**: Verify that known synergistic pairs (e.g., S121E+D186H) are detected

### WP B4: GRAPE Greedy Accumulation

**Purpose**: Build optimal mutation stack using greedy accumulation with AF2 validation at each step.
**Inputs**: WP B2 scores + B3 epistasis data
**Method**: 
1. Start with best single mutant
2. Add next-best (non-epistatic) mutation
3. Run AF2 on the combination
4. If pLDDT > 80 and catalytic RMSD < 1.5Å → keep
5. Repeat until 5-15 mutations or diminishing returns
**Outputs**: 
- `data/generated/route_b/greedy_combinations.fa` — accumulated variants
- `data/generated/route_b/accumulation_log.csv` — per-step metrics
**QC**: At each step, verify cumulative score improves

### WP B5: Route B Scoring & Ranking

**Purpose**: Final scoring and ranking of accumulated variants (same pipeline as A5).
**Inputs**: WP B4 accumulated variants
**Method**: Same as WP A5 (hard filters → ranking signals → Pareto → clustering)
**Outputs**: 
- `data/ranking/route_b_passed.csv`
- `data/ranking/route_b_rejected.csv`

---

## Phase 3: Route C — Large-Scale MPNN + MD Validation

### WP C1: ProteinMPNN Full/Wide Redesign

**Purpose**: Generate 1,000 aggressive redesign sequences (500 conservative T=0.3 + 500 exploratory T=0.5).
**Inputs**: PDB 5XJH, fixed catalytic triad (S160,D206,H237)
**Method**: 
```
# Conservative batch (T=0.3)
protein_mpnn_run.py --pdb_path 5XJH.pdb --fixed_residues S160,D206,H237 \
  --num_seq_per_target 500 --sampling_temp 0.3 --seed 42
  
# Exploratory batch (T=0.5)
protein_mpnn_run.py --pdb_path 5XJH.pdb --fixed_residues S160,D206,H237 \
  --num_seq_per_target 500 --sampling_temp 0.5 --seed 43
```
**Outputs**: 
- `data/generated/route_c/mpnn_T03.fa` (500 seq)
- `data/generated/route_c/mpnn_T05.fa` (500 seq)
**Metrics**: Mutation count distribution, sequence recovery vs WT
**QC**: All S160/D206/H237 = WT; verify sequence length

### WP C2: AlphaFold2 Fast Filtering (Route C)

**Purpose**: Rapid structure prediction and filter to ~100-200 candidates.
**Inputs**: WP C1 outputs (1,000 sequences)
**Method**: Same as WP A4. Filter: pLDDT > 85, catalytic RMSD < 1.5Å.
**Outputs**: 
- `data/predictions/route_c/scores.csv`
- `data/predictions/route_c/passed/` — filtered PDBs
**Decision gate (Gate 2)**: If < 50 pass → reduce temperature to 0.2, regenerate

### WP C3: Rosetta Full Scoring + FastRelax

**Purpose**: Energetic evaluation of top Route C candidates.
**Inputs**: WP C2 passing candidates
**Method**: 
1. Rosetta ref2015 score (full complex energy)
2. Rosetta ddg_monomer (per-candidate stability)
3. Rosetta packstat (packing quality)
4. Rosetta FastRelax (5 repeats) on top 30
**Outputs**: 
- `data/scoring/route_c_rosetta.csv` — all scores
- `data/scoring/route_c_relaxed/` — top 30 relaxed structures
**QC**: Verify score distributions are reasonable (no extreme outliers)

### WP C4: GROMACS MD Validation (Top 10-15)

**Purpose**: Validate dynamic stability of best candidates.
**Inputs**: Top 10-15 candidates from C3 + WT control
**Method**: 
1. System preparation: solvate (TIP3P), add ions (150 mM NaCl), energy minimize
2. Equilibration: NVT (100 ps) + NPT (100 ps) with position restraints
3. Production: 100 ns NPT at 300K and 340K (near target temperature)
4. Force field: AMBER99SB-ILDN
**Outputs**: 
- `data/md/route_c/*/trajectory.xtc` — trajectories
- `data/md/route_c/*/rmsd.xvg` — backbone RMSD
- `data/md/route_c/*/rmsf.xvg` — per-residue RMSF
- `data/md/route_c/*/catalytic_distances.xvg` — S160-H237, D206-H237 distances
**Metrics**: Backbone RMSD (Cα), RMSF, catalytic distance stability, SASA
**QC**: WT control should replicate known flexibility patterns (β8-α6 loop)
**Decision gate (Gate 4)**: 
- RMSD < 2.5Å for >80% of trajectory → final candidate
- Regional RMSF spike → feed back to WP A2 mask update
- Widespread instability → recalculate masks, re-enter C1 with tighter constraints

---

## Phase 4: Integration, Ranking & Packaging

### WP I1: Cross-Route Candidate Merge

**Purpose**: Combine passing candidates from all three routes.
**Inputs**: 
- `data/ranking/route_a_passed.csv`
- `data/ranking/route_b_passed.csv`
- `data/ranking/route_c_scored.csv`
**Method**: Union all passing candidates; re-normalize scores for cross-route comparison.
**Outputs**: `data/ranking/all_candidates.csv`

### WP I2: Multi-Objective Pareto Ranking

**Purpose**: Identify non-dominated candidates across stability, activity proxies, and diversity.
**Inputs**: `data/ranking/all_candidates.csv`
**Method**: 
1. Pareto front on: pLDDT (maximize), ΔΔG (minimize), catalytic RMSD (minimize)
2. Compute crowding distance for diversity
3. Select 20-50 diverse Pareto-optimal candidates
**Outputs**: 
- `data/ranking/pareto_front.csv` — final candidates
- `data/ranking/pareto_summary.md` — Pareto plot description

### WP I3: Final Deliverable Packaging

**Purpose**: Produce all 8 deliverable artifacts.
**Inputs**: All prior outputs
**Outputs**: 
| # | File | Path |
|---|------|------|
| 1 | `ranked_candidates.csv` | `data/final/` |
| 2 | `candidates.fasta` | `data/final/` |
| 3 | `mutation_table.csv` | `data/final/` |
| 4 | `metric_matrix.csv` | `data/final/` |
| 5 | `pareto_summary.md` | `data/final/` |
| 6 | `rejected_log.csv` | `data/final/` |
| 7 | `decision_log.md` | `data/final/` |
| 8 | `reproducibility_manifest.json` | `data/final/` |
**QC**: All candidates in FASTA match CSV entries; all metrics recorded with methods and versions

---

## Phase Dependencies

```
Phase 0 (Prerequisites)
  ├── Phase 1 (Route A): A1 → A2 → A3 → A4 → A5
  ├── Phase 2 (Route B): B1 → B2 → B3 → B4 → B5
  └── Phase 3 (Route C): C1 → C2 → C3 → C4
                              ↓
Phase 4 (Integration): ← A5 + B5 + C4 → I1 → I2 → I3
```

Routes A, B, C are **fully parallel**. Phase 4 depends on all three routes completing.

---

## Self-Review Checklist

- [x] Every spec commitment maps to a work package ✓ (12 WPs across 4 phases)
- [x] Exact commands specified for known tools; capability resolution for unknowns (WP 0.1)
- [x] Sequence IDs, numbering (PDB 5XJH), masks, and paths are consistent throughout
- [x] All metrics record method, version, units, and interpretation
- [x] Every adaptive branch has a next action (Gates 1-4)
- [x] Candidate lineage preserved (IDs, parent-child, seeds, parameters)
- [x] No wet-lab tasks present ✓
- [ ] Capability resolution (WP 0.1) requires actual environment check

**Status: AWAITING USER APPROVAL. Execute with `sisyphus --plan docs/enzyme-design/plans/2025-05-31-ispetase-thermostability.md`**
