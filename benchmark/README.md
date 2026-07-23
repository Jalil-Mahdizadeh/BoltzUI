# Boltz 2.2.1 multichain solution-NMR challenge benchmark

This directory contains a reproducible, failure-enriched challenge-set benchmark
for unconstrained Boltz 2.2.1 predictions of multichain solution-NMR structures.
Every screened and executed candidate is retained. Executed candidate directories
are renamed to `<pdb-id>-passed` when every generated model is significantly wrong,
or `<pdb-id>-skipped` when at least one generated model is reasonably accurate.

## Scientific scope

This is deliberately a **failure-enriched challenge set**, because selection
continues until ten Boltz failures have been found. It must not be presented as an
unbiased estimate of Boltz accuracy on solution-NMR structures. The complete
screening log and all skipped runs are retained to make the selection process
auditable.

Eligible entries must:

- have experimental method `SOLUTION NMR`;
- have an initial PDB release date after 2023-06-01, the reported Boltz-2 PDB
  training cutoff;
- contain exactly two deposited polymer chain instances (a reproducible subset of
  the requested two-or-more-chain scope);
- contain only Boltz-supported protein, RNA, or DNA polymer types;
- contain no deposited non-polymer entities, avoiding failures caused by omitting
  cofactors, metal ions, detergents, or small-molecule ligands from the input;
- have 10-1000 total polymer residues and at least 5 residues per chain;
- have at least 95% of deposited polymer residues modeled;
- contain at least 10 inter-chain native residue contacts in the NMR ensemble;
- have a compact experimental ensemble, with medoid-centered 90th-percentile
  backbone RMSD no greater than 5.0 Angstrom;
- provide both combined NMR data in NEF and NMR-STAR format through the PDB
  archive.

Only standard sequence polymers are used. Entries with unsupported hybrid polymer
types, non-polymer entities, multi-character author chain IDs (incompatible with
unambiguous legacy PDB output), or malformed/incomplete coordinate ensembles are
screened out before GPU inference.

Selection used three auditable size stages. Stage 1 used 40-350 total residues.
After its retained outcomes made ten failures mathematically impossible unless
every remaining entry passed, stage 2 prospectively expanded only the size window
to 20-500 residues. When that retained pool could no longer yield ten failures,
stage 3 expanded only the size window to 10-1000 residues, the logical range
given the 5-residue-per-chain minimum. All other eligibility and classification
criteria remained fixed. Complete earlier-stage queries and tables are retained
under `screening/stage1_40_350/` and `screening/stage2_20_500/`.

The 10-1000-residue pool with the strict ensemble p90 cutoff of 4.0 Angstrom
produced nine failures and was then exhausted. A final, explicitly labeled
compactness-sensitivity stage admitted only near-threshold ensembles with p90
between 4.0 and 5.0 Angstrom. The full strict-pool state is retained under
`screening/stage3_10_1000_p90_4/`; individual ensemble p90 values remain in every
candidate record and result table.

## Classification

Each of 10 Boltz predictions is compared with every experimental NMR conformer.
Equivalent chains in homomers are permuted, and the best symmetry-aware match is
used. Protein backbone atoms are N/CA/C; nucleic-acid backbone representatives are
P/C4'/C1'. Native residue contacts use a 5.0 Angstrom inter-chain heavy-atom cutoff.

CAPRI-like quality classes are assigned from:

- `Fnat`: fraction of experimental inter-chain residue contacts recovered;
- `iRMSD`: interface-backbone RMSD after interface superposition;
- `LRMSD`: smaller-chain RMSD after superposition on the larger chain.

The tiers used here are:

- high: `Fnat >= 0.5` and (`LRMSD <= 1.0` or `iRMSD <= 1.0`);
- medium: `Fnat >= 0.3` and (`LRMSD <= 5.0` or `iRMSD <= 2.0`);
- acceptable: `Fnat >= 0.1` and (`LRMSD <= 10.0` or `iRMSD <= 4.0`);
- incorrect: all other cases.

A PDB entry is `passed` only when all 10 Boltz models are incorrect relative to
every conformer in the experimental NMR ensemble. It is `skipped` when any model
is acceptable, medium, or high quality. This conservative best-of-10,
best-of-ensemble rule avoids labeling borderline cases as failures.

## Prediction protocol

Inputs contain sequences only: no contacts, templates, pockets, bonds, or other
constraints. The command is fixed in `config.json` and mirrors the requested
protocol, including 400 sampling steps, 10 diffusion samples, sample chunk size 1,
physical potentials, the ColabFold MSA server, seed 1, and PDB output. Experimental
method conditioning is fixed to `x-ray diffraction` to match the supplied command,
even though the reference structures were determined by solution NMR.

## Layout

- `config.json`: immutable selection, prediction, and classification settings.
- `scripts/`: discovery, preparation, inference, comparison, and orchestration.
- `screening/`: complete RCSB query response and candidate/filter tables.
- `candidates/`: all executed candidate inputs, metadata, logs, and outputs.
- `summary/`: machine-readable and manuscript-oriented final reports.

Official source services:

- RCSB Search API: `https://search.rcsb.org/rcsbsearch/v2/query`
- RCSB Data API: `https://data.rcsb.org/rest/v1/core`
- PDB coordinate files: `https://files.rcsb.org/download/<PDB>.pdb`
- PDBx/mmCIF fallback: `https://files.rcsb.org/download/<PDB>.cif`
- Combined NEF/NMR-STAR:
  `https://files.rcsb.org/pub/pdb/data/structures/divided/nmr_data/<middle>/<pdb>_nmr-data.{nef,str}.gz`
