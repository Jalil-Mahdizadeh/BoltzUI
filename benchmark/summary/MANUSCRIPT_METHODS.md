# Manuscript methods and benchmark accounting

## Study design

We constructed a deliberately failure-enriched challenge set for unconstrained
Boltz 2.2.1 prediction of multichain structures determined by solution NMR. This
design identifies well-defined failure examples; it does not estimate population
accuracy. RCSB PDB entries released after 2023-06-01 were searched for solution-NMR
structures containing exactly two polymer chain instances and both combined NEF
and NMR-STAR depositions. Protein, RNA, and DNA chains were eligible. Entries
containing non-polymer entities or unsupported polymer chemistry were excluded.
Eligible complexes contained 10-1000 total residues, at least
5 residues per chain, at least 10 NMR conformers, and at least
95% modeled polymer residues.

Screening was performed in three documented size stages. Stage 1 used 40-350 total
residues. Once the retained stage-1 outcomes meant that all remaining entries
would have to fail to reach the requested set size, stage 2 prospectively
expanded only the size window to 20-500 residues. When that pool could no longer
yield ten failures, stage 3 expanded only the size window to 10-1000 residues.
All other criteria and all classification thresholds remained fixed, and the
complete earlier-stage queries and tables were retained.

To minimize ambiguity from experimental disorder, coordinate ensembles were
required to have at least 10 median inter-chain residue contacts at a
5.0 A heavy-atom cutoff and a medoid-centered 90th-percentile
backbone RMSD no greater than 5.0 A. At least 90% sequence identity
and anchor coverage per chain and conformer were required for coordinate mapping.
The strict size-stage pool used p90 <= 4.0 A and yielded nine qualifying
failures. After that pool was exhausted, a labeled compactness-sensitivity stage
admitted only near-threshold ensembles with 4.0 < p90 <= 5.0 A; all individual
p90 values were retained.

## Prediction

Each input contained polymer sequences only, with no experimental contacts,
templates, covalent constraints, pockets, or restraints. Ten structures were
sampled with seed 1, three recycling steps, 400 sampling steps, physical
potentials, and ColabFold-server MSAs. The full fixed Boltz argument vector was:

`--devices 1 --accelerator gpu --model boltz2 --method x-ray diffraction --recycling_steps 3 --sampling_steps 400 --diffusion_samples 10 --max_parallel_samples 1 --step_scale 1.0 --seed 1 --use_potentials --use_msa_server --msa_server_url https://api.colabfold.com --msa_pairing_strategy greedy --max_msa_seqs 8192 --subsample_msa --num_subsampled_msa 1024 --output_format pdb --write_full_pae --override --num_workers 0 --preprocessing-threads 1 --no_kernels`

Method conditioning was set to `x-ray diffraction` to reproduce the supplied
benchmark command, although all reference entries were determined by solution
NMR.

## Evaluation

Every predicted model was compared with every usable experimental conformer.
Equivalent homomer chains were exhaustively permuted. Native inter-chain residue
contacts used a 5.0 A heavy-atom cutoff. CAPRI-like classes used
Fnat together with interface RMSD (iRMSD) and ligand RMSD (LRMSD): high quality,
Fnat >= 0.5 and (LRMSD <= 1.0 A or iRMSD <= 1.0 A); medium quality,
Fnat >= 0.3 and (LRMSD <= 5.0 A or iRMSD <= 2.0 A); acceptable quality,
Fnat >= 0.1 and (LRMSD <= 10.0 A or iRMSD <= 4.0 A); incorrect otherwise.
An entry was called passed only if all ten predictions were incorrect against
every NMR conformer. If any prediction was acceptable or better, the entry was
called skipped. All screened and executed files were retained.

## Accounting

- Initial RCSB search hits: 111
- Metadata-eligible entries: 52
- Coordinate-screened queue: 39
- Stage-1 search/metadata/coordinate counts: 64/36/24
- Stage-2 search/metadata/coordinate counts: 94/46/34
- Stage-3 strict-p90 search/metadata/coordinate counts: 111/52/36
- Final p90<=5 A coordinate-screened queue: 39
- Entries executed: 38
- Passed failure cases: 10
- Unique sequence-input clusters among passed cases: 9
- Skipped entries: 28
- Running/unclassified entries: 0

Because sampling continued until the target number of failures was reached, the
passed set must be described as a challenge set, not as a denominator-based
accuracy estimate. Distinct PDB depositions with the same unordered polymer
sequence input are reported as separate experimental states but grouped by
`sequence_input_cluster`; they must not be treated as independent sequence-level
replicates.
