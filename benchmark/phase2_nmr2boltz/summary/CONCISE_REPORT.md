# Concise phase-2 report

## Outcome

The primary exact+union treatment rescued **5/10** phase-1 failures to CAPRI acceptable-or-better in the best of 10 samples. Exact-only rescued **4/10** applicable entries and union-only rescued **1/9** (9KAD had no union groups).

At the individual-sample level, exact+union produced **21/100** acceptable-or-better models, versus **0/100** in the matched unconstrained controls; exact-only produced **15/100** and union-only **7/90**.

Across entries, the combined arm changed best-of-10 Fnat by a median **0.126**, interface RMSD by **-3.36 Å**, ligand RMSD by **-5.21 Å**, and global backbone RMSD by **-1.74 Å** relative to the matched unconstrained control (negative RMSD changes are improvements).

## Per-entry best-of-10 results

| PDB | exact / union (inter-chain) | matched baseline | exact | union | exact+union | ΔFnat | ΔiRMSD Å | median exact / union satisfaction |
|---|---:|---|---|---|---|---:|---:|---:|
| 9XAP | 199/16 (11/0) | incorrect (Fnat 0.08) | incorrect (Fnat 0.50) | incorrect (Fnat 0.17) | incorrect (Fnat 0.46) | 0.375 | -4.70 | 0.81/0.88 |
| 9JO6 | 527/8 (16/0) | incorrect (Fnat 0.07) | incorrect (Fnat 0.20) | incorrect (Fnat 0.07) | incorrect (Fnat 0.20) | 0.131 | -1.07 | 0.92/1.00 |
| 9EZO | 495/130 (13/6) | incorrect (Fnat 0.50) | incorrect (Fnat 0.50) | incorrect (Fnat 0.50) | acceptable (Fnat 0.53) | 0.029 | -4.36 | 0.96/0.95 |
| 9EZP | 495/143 (13/19) | incorrect (Fnat 0.23) | acceptable (Fnat 0.31) | incorrect (Fnat 0.36) | acceptable (Fnat 0.35) | 0.121 | -3.63 | 0.97/0.85 |
| 8VOH | 6/4 (6/4) | incorrect (Fnat 0.00) | acceptable (Fnat 0.44) | incorrect (Fnat 0.25) | medium (Fnat 0.59) | 0.594 | -13.65 | 0.33/0.75 |
| 8IVB | 6/8 (6/8) | incorrect (Fnat 0.38) | acceptable (Fnat 0.61) | medium (Fnat 0.71) | medium (Fnat 0.58) | 0.198 | -3.09 | 0.17/0.38 |
| 9KAD | 190/0 (50/0) | incorrect (Fnat 0.00) | incorrect (Fnat 0.00) | NA | incorrect (Fnat 0.00) | 0.000 | -0.07 | 0.73/NA |
| 8Q5Q | 948/8 (62/8) | incorrect (Fnat 0.19) | acceptable (Fnat 0.81) | incorrect (Fnat 0.41) | medium (Fnat 0.75) | 0.562 | -7.53 | 0.95/1.00 |
| 9JVN | 1/640 (1/0) | incorrect (Fnat 1.00) | incorrect (Fnat 1.00) | incorrect (Fnat 1.00) | incorrect (Fnat 1.00) | 0.000 | -0.04 | 0.00/0.94 |
| 8X8T | 756/113 (35/13) | incorrect (Fnat 0.12) | incorrect (Fnat 0.15) | incorrect (Fnat 0.12) | incorrect (Fnat 0.16) | 0.036 | -1.52 | 0.93/0.91 |

## Interpretation

Median model-level exact and union satisfaction in the combined arm was **0.86** and **0.91**, respectively. These are soft guidance potentials, so satisfaction was evaluated from the final coordinates rather than assumed.

NEF and NMR-STAR produced identical executable exact sets for **2/10** entries and identical union sets for **1/10**. The NEF conversion was therefore prespecified as the sole prediction source; NMR-STAR was retained as an independent format-parity audit, not added as duplicate evidence.

The 8Q5Q deposition contains protonated deoxycytidine DNR at position 5 in both chains. Because phase 1 used its canonical parent C, phase 2 reran a DNR-matched unconstrained control; this prevents the modification correction from being credited to the restraints.

This is a restraint-assisted reconstruction benchmark, not an independent de novo validation: the restraints and reference ensemble come from the same deposition. The set was deliberately selected for baseline failures (n=10), and exact-only versus union-only arms contain unequal amounts of experimental information. Conclusions should therefore be stated as effect sizes on this challenge set, not as population-wide accuracy.

Machine-readable results: `phase2_results.json` and `phase2_results.tsv`. Validation: `validation_report.json`.
