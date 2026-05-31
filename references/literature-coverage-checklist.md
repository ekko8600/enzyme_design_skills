# Literature Coverage Checklist

Use this checklist during evidence synthesis. Mark unsupported items as
`Not found in current evidence`.

## Identity And Function

- What enzyme, family, EC class, organism, and sequence are in scope?
- What reaction, substrate, product, cofactor, and side reactions are known?
- Which application-specific property is being optimized?

## Mechanism And Structure

- Which catalytic residues, motifs, metals, cofactors, and proton-transfer
  networks are supported by evidence?
- Which PDB, predicted structures, ligand-bound structures, homologous
  templates, or complexes are useful?
- Which loops, channels, pockets, interfaces, domain boundaries, and dynamic
  regions affect the target property?

## Design Space

- Which residues are immutable, restricted, redesignable, or unknown?
- Which positions are supported by positive or negative mutation evidence?
- Which homologs, consensus patterns, coevolution signals, or ancestral states
  provide useful priors?
- Which parts of the protein can tolerate local redesign?
- Is scaffold replacement or backbone generation justified?

## Quantitative Evidence

- Which kinetic, stability, specificity, binding, structural, or computational
  metrics exist?
- Are baselines and conditions comparable?
- Which evidence should become a hard constraint versus a ranking prior?

## AI Design Priors

- Which PLMs, variant-effect predictors, inverse-folding models, MPNN variants,
  structure predictors, docking methods, Rosetta-style scores, MD analyses, or
  generative backbone models have relevant precedent?
- Are training-domain mismatch, out-of-distribution risk, or missing
  calibration likely?
- Which cheap filters should run before expensive calculations?
- Which intermediate outputs should alter masks, thresholds, or model routes?

## Gaps And Conflicts

- Which claims conflict?
- Which important facts remain unsupported?
- Which unknowns require user decisions?
- Which unknowns can be reduced by computational exploration?
