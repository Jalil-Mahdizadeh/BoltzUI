# Manuscript results

The staged search yielded 10 passed failure PDBs and 28 skipped PDBs after 38 entries were executed. The passed set represents 9 unique unordered sequence-input clusters. 9 passed entries came from the strict p90 <= 4.0 A pool and 1 from the labeled 4.0-5.0 A compactness-sensitivity stage.

Every passed entry had 10/10 CAPRI-incorrect predictions under the best-of-NMR-ensemble and symmetry-aware rule. Values below describe the best (least wrong) prediction for each passed entry.

| PDB | Polymer(s) | Lengths | Selection stage | p90 RMSD (A) | Best Fnat | Best iRMSD (A) | Best LRMSD (A) | Best ipTM |
|---|---|---:|---|---:|---:|---:|---:|---:|
| 9XAP | polypeptide(L) | 21+21 | size_stage_1_40_350 | 1.31 | 0.083 | 9.38 | 19.53 | 0.793 |
| 9JO6 | polypeptide(L) | 140+41 | size_stage_1_40_350 | 3.50 | 0.072 | 15.11 | 27.67 | 0.387 |
| 9EZP | polypeptide(L) | 57+19 | size_stage_1_40_350 | 1.39 | 0.227 | 7.39 | 23.27 | 0.954 |
| 9EZO | polypeptide(L) | 57+19 | size_stage_1_40_350 | 2.25 | 0.500 | 7.11 | 23.83 | 0.960 |
| 9KAD | polyribonucleotide | 14+14 | size_stage_2_20_500 | 1.21 | 0.000 | 7.46 | 15.25 | 0.654 |
| 9JVN | polydeoxyribonucleotide+polyribonucleotide | 8+8 | size_stage_3_10_1000 | 0.34 | 1.000 | 9.17 | 16.56 | 0.155 |
| 8VOH | polypeptide(L) | 194+58 | size_stage_1_40_350 | 2.04 | 0.000 | 15.16 | 45.59 | 0.761 |
| 8X8T | polypeptide(L) | 61+62 | compactness_sensitivity_p90_5 | 4.21 | 0.120 | 11.70 | 18.13 | 0.680 |
| 8Q5Q | polydeoxyribonucleotide | 15+15 | size_stage_2_20_500 | 0.33 | 0.250 | 10.52 | 14.84 | 0.468 |
| 8IVB | polypeptide(L) | 76+169 | size_stage_1_40_350 | 0.84 | 0.382 | 5.01 | 14.63 | 0.643 |

Skipped entries (at least one acceptable-or-better model): 9T3O, 9VUY, 9K70, 25SJ, 9XEA, 9DKG, 9VJL, 21GE, 9MES, 9BXE, 9I8B, 8YZL, 9EZN, 8YAP, 8WVS, 9CPJ, 8UWU, 8WLS, 8QKX, 8X1V, 8HT7, 8HQB, 8HPB, 8IMH, 8FG1, 8B4S, 8PEK, 8DDD.

This is a deliberately failure-enriched challenge set: search and execution continued until the requested target was reached. These counts must not be interpreted as an unbiased Boltz accuracy estimate. Distinct PDB experimental states sharing a sequence input are clustered in the TSV/JSON outputs and are not independent sequence-level replicates.
