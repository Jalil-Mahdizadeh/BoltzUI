# 8VOH token-only attribution test

## Result

Token-level constraints contributed a real but inconsistent improvement. The
atom-guided arms were responsible for most of the robust ensemble-level rescue,
with the six exact atom restraints providing the dominant contribution and the
four union atom groups adding a smaller best-case improvement.

All arms used the same 10-member NMR reference ensemble, seed 1, fixed phase-1
MSAs, three recycling steps, 400 sampling steps, ten diffusion samples, and one
parallel sample. The token arm used the nine unique contacts emitted by
`nmr2boltz 0.1.0` from the deposited NEF. All validation checks passed.

| Arm | CAPRI classes across 10 models | Best Fnat | Best iRMSD (A) | Median Fnat | Median iRMSD (A) | Generated token contacts satisfied |
|---|---:|---:|---:|---:|---:|---:|
| Unconstrained | 10 incorrect | 0.000 | 15.16 | 0.000 | 17.30 | 0/90 (0.0%) |
| Token only | 2 acceptable, 8 incorrect | 0.344 | 3.45 | 0.000 | 13.51 | 16/90 (17.8%) |
| Exact atom | 9 acceptable, 1 incorrect | 0.438 | 2.19 | 0.344 | 2.95 | 63/90 (70.0%) |
| Union atom | 10 incorrect | 0.250 | 4.11 | 0.031 | 8.89 | 13/90 (14.4%) |
| Combined atom | 1 medium, 8 acceptable, 1 incorrect | 0.594 | 1.50 | 0.344 | 3.03 | 63/90 (70.0%) |

Every generated token constraint was satisfied in every reference conformer
(90/90), confirming that the contact set is structurally consistent with the
deposited NMR ensemble.

## Attribution

Relative to token only, the combined atom arm improved the paired CAPRI rank in
7/10 samples and worsened none. Median paired changes were +0.328 Fnat,
-6.45 A iRMSD, -11.62 A LRMSD, and -4.38 A global backbone RMSD. Exact atom
versus token only produced the same 7/10 rank-improvement pattern, with median
paired changes of +0.250 Fnat and -5.93 A iRMSD. This is strong evidence that
atom-specific coordinate guidance contributed substantially beyond token
conditioning.

Adding union atom groups to the exact arm improved CAPRI rank in 1/10 models and
worsened none. It raised the best Fnat from 0.438 to 0.594 and improved the best
iRMSD from 2.19 A to 1.50 A, producing the only medium-quality model. Median
Fnat and CAPRI rank did not change, so the union contribution was detectable but
smaller and concentrated in the best sample.

The token constraints are soft conditioning rather than hard restraints. Their
limited realization explains the inconsistent token-only outcome: the two
acceptable token-only models satisfied 5/9 and 7/9 contacts, while the remaining
models satisfied at most 4/9 and usually 0/9. The exact and combined atom arms
made 9/10 models satisfy at least 5/9 generated token contacts.

## Limitation

This is a strong directional attribution test, not an exact additive
decomposition. The generated token YAML contains six contacts derived from exact
groups plus three unique contacts collapsed from four union groups. The combined
atom arm internally applies binary token conditioning only for its six exact
contacts; union alternatives intentionally remain coordinate-potential-only.
The token-only arm therefore contains slightly more coarse-grained information
than the token component of the combined arm. Its markedly weaker performance
despite that advantage strengthens the evidence for an atom-level contribution,
but a six-contact exact-token-only arm would be required for a perfectly matched
component ablation.

Machine-readable results are in `analysis/comparison_summary.json`, paired
effects in `analysis/paired_effect.json`, individual token-distance audits in
`analysis/token_constraint_audits.json`, and validation gates in
`analysis/validation_report.json`.
