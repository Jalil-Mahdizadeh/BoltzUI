# 8VOH forced-token rerun

## Conclusion

The suspicion was correct. `force: false` did not disable token conditioning, but it did disable Boltz's coordinate-potential enforcement. Changing only the nine `force` values to `true` changed the token-only ensemble from **2 acceptable / 8 incorrect** models to **10 acceptable / 0 incorrect** models.

For 8VOH, forced residue-level contacts are sufficient to explain most of the robust, ensemble-wide improvement previously attributed to the combined atom constraints. The combined arm still produced the single best model, so the atom-specific constraints may contribute useful best-case precision, but they did not improve the median ensemble over forced token contacts in this run.

## Results

All prediction arms contain 10 models and were evaluated against all 10 usable deposited NMR conformers. Lower RMSD is better; higher Fnat is better.

| Arm | CAPRI classes (10 models) | Best class | Median Fnat | Median interface RMSD | Generated-token contacts satisfied | Confidence-selected model |
|---|---:|---:|---:|---:|---:|---|
| Unconstrained | 10 incorrect | incorrect | 0.000 | 17.30 Å | 0/90 (0.0%) | incorrect; Fnat 0.000; iRMSD 16.27 Å |
| Token, `force:false` | 2 acceptable, 8 incorrect | acceptable | 0.000 | 13.51 Å | 16/90 (17.8%) | acceptable; Fnat 0.250; iRMSD 3.83 Å |
| Token, `force:true` | **10 acceptable** | acceptable | **0.438** | **2.54 Å** | **73/90 (81.1%)** | acceptable; Fnat 0.438; iRMSD 3.01 Å |
| Exact atom | 9 acceptable, 1 incorrect | acceptable | 0.344 | 2.95 Å | 63/90 (70.0%) | acceptable; Fnat 0.375; iRMSD 3.68 Å |
| Union atom | 10 incorrect | incorrect | 0.031 | 8.89 Å | 13/90 (14.4%) | incorrect; Fnat 0.250; iRMSD 4.11 Å |
| Combined exact + union atom | 1 medium, 8 acceptable, 1 incorrect | **medium** | 0.344 | 3.03 Å | 63/90 (70.0%) | acceptable; Fnat 0.344; iRMSD 3.38 Å |

Matched `force:true` versus `force:false` results:

- CAPRI rank improved for 8/10 paired model indices and worsened for 0/10.
- Median paired Fnat increased by 0.406.
- Median paired interface RMSD decreased by 10.58 Å.
- Median paired ligand RMSD decreased by 19.49 Å.
- Median paired global backbone RMSD decreased by 7.28 Å.

Forced token versus combined atom results:

- The forced-token ensemble had better medians: Fnat 0.438 versus 0.344 and interface RMSD 2.54 versus 3.03 Å.
- In paired model-index comparisons, combined improved one CAPRI rank and worsened one; the other eight ranks were unchanged.
- The combined arm's best model was better than the forced-token arm's best: medium versus acceptable, Fnat 0.594 versus 0.500, and interface RMSD 1.50 versus 2.33 Å.
- The confidence-selected forced-token model was better than the confidence-selected combined model: Fnat 0.438 versus 0.344 and interface RMSD 3.01 versus 3.38 Å.

## What `force` changes

Inspection of Boltz 2.2.1 in the pinned image showed that native token contacts always populate the model's token contact-conditioning feature. With `force:false`, they are omitted from `process_contact_feature_constraints`. With `force:true`, each residue pair additionally becomes one coordinate-potential group containing the Cartesian product of the two residues' atoms, so its geometry is a minimum-heavy-atom distance restraint.

Thus the earlier `force:false` arm measured **token conditioning only**. This rerun measures **token conditioning plus forced residue-pair coordinate potentials**.

## Important attribution caveat

The nmr2boltz token file contains nine residue pairs: six derived from exact groups and three collapsed from union groups. The combined atom arm contributes only the six exact groups to Boltz's binary token conditioning; its union groups remain alternative atom-potential groups. Therefore this is a biologically matched comparison, but not a strict equal-component ablation.

The defensible 8VOH conclusion is: **forced token contacts drive the consistent ensemble improvement, while atom-specific constraints contribute, at most, a smaller and less consistent best-case gain in this experiment.** This single target should not be used alone to generalize the conclusion across the full benchmark.

## Validation

Validation passed: the two token inputs differ only in nine `force` booleans; the processed record contains nine forced token contacts and zero exact/union atom contacts; 10 PDBs and all expected confidence, PAE, PDE, and pLDDT files are present; and all nine generated token contacts are satisfied in every deposited NMR conformer.

