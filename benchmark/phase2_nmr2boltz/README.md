# Phase 2: nmr2boltz restraint-assisted Boltz benchmark

This directory contains the complete second-phase workflow and its generated
artifacts. The ten phase-1 failures are rerun with the same Boltz command and
random seed. The constrained YAMLs add the nmr2boltz restraint blocks and
reference the byte-identical phase-1 protein MSAs to prevent a fresh server
query from changing the evolutionary input. The separately documented 8Q5Q
representation correction is the only target-chemistry change.

The deposited NEF file is the primary conversion source. The paired NMR-STAR
file is converted independently as a format-parity audit and is never combined
with NEF, because the two files encode the same experiment rather than
independent evidence.

Three constrained arms are retained:

- `exact`: all executable non-ambiguous `atom_contact` restraints;
- `union`: all executable ambiguity-preserving `atom_contact_union` groups;
- `combined`: both sets in one input (the primary treatment requested).

Each model is compared with every usable conformer in the deposited NMR
ensemble using the same symmetry-aware CAPRI-like analysis as phase 1.
Constraint satisfaction is measured independently from the generated
coordinates.

One preregistered representation correction is required by fail-closed target
validation. PDB 8Q5Q contains protonated deoxycytidine `DNR` (CCD parent `DC`)
at position 5 of both chains, whereas phase 1 used the canonical parent letter
`C`. Its phase-2 target declares `position: 5, ccd: DNR` and uses the official
RCSB CCD file. A matched modified-but-unconstrained control is rerun for this
entry, so the effect of the modification is not attributed to NMR restraints.

Run order:

```bash
python3 benchmark/phase2_nmr2boltz/scripts/prepare_cases.py
bash benchmark/phase2_nmr2boltz/scripts/run_conversions.sh
python3 benchmark/phase2_nmr2boltz/scripts/build_inputs.py
bash benchmark/phase2_nmr2boltz/scripts/run_all.sh
python3 benchmark/phase2_nmr2boltz/scripts/analyze_phase2.py
python3 benchmark/phase2_nmr2boltz/scripts/validate_phase2.py
```

The final concise report is `summary/CONCISE_REPORT.md`.
