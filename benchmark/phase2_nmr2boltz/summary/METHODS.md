# Phase-2 methods

The challenge set comprised the ten solution-NMR, two-polymer entries for which
all ten sequence-only Boltz predictions in phase 1 were CAPRI-incorrect against
every usable conformer of the deposited ensemble: 9XAP, 9JO6, 9EZO, 9EZP,
8VOH, 8IVB, 9KAD, 8Q5Q, 9JVN, and 8X8T.

Each deposited combined NEF file was converted with nmr2boltz
0.1.0-validated using its conservative defaults: `sum-r6` atom-set averaging,
rejection of missing upper bounds, rejection of geometric pseudoatoms,
0 Å projection margin, and the Boltz-compatible 2–20 Å range. The exact Boltz
target YAML was supplied during conversion, making incompatible chain,
residue, identity, or atom mappings fatal. The paired NMR-STAR file was
converted independently with the same settings as a format-parity audit.
NMR-STAR restraints were not combined with NEF restraints because the two
files are alternative representations of the same deposited experiment.

Three constrained inputs were generated per entry: non-ambiguous exact
contacts only, ambiguous union groups only, and their combination. A
non-applicable union-only arm was recorded but not run for 9KAD because its
conversion emitted no union groups. PDB 8Q5Q required an explicit DNR
(N3-protonated deoxycytidine; CCD parent DC) modification at residue 5 in both
identical chains. An additional DNR-matched unconstrained control was run so
that the representation correction was not attributed to NMR restraints.

Protein inputs reused byte-identical raw MSA CSV files from the corresponding
phase-1 calculations. This held evolutionary information fixed across arms.
All command-line arguments, including Boltz 2.2.1, model, method metadata,
400 sampling steps, 3 recycling steps, 10 serial diffusion samples, step scale
1.0, seed 1, physical potentials, output format, and worker settings, were
otherwise unchanged. Exact and union contacts were applied by the immutable
patched Boltz container identified in `../provenance/environment.json`.

Every generated model was compared with every usable conformer of its
deposited NMR ensemble. Sequence-aware residue mapping and all
sequence-equivalent chain permutations were evaluated. The retained comparison
for each predicted model was ordered by CAPRI-like class, Fnat, interface
backbone RMSD, ligand RMSD, and global backbone RMSD, matching phase 1. Native
inter-chain contacts used a 5 Å heavy-atom cutoff. High, medium, and acceptable
classes used the thresholds stored in `../../config.json`; all other models
were classified as incorrect.

Effects were summarized both per fixed model index and as best-of-ten changes
relative to the matched unconstrained control. Positive Fnat changes and
negative RMSD changes indicate improvement. Exact-contact satisfaction was the
fraction of resolved pairs within their projected upper bound. A union group
was satisfied if any resolved alternative met its own bound, violated only
when every alternative resolved and violated, and otherwise indeterminate.
Satisfaction was evaluated independently from final coordinates for both
predictions and deposited conformers.

This experiment measures restraint-assisted reconstruction on a deliberately
selected failure set. Because the restraints and reference structures derive
from the same deposition, it is not an independent de novo test, and the ten
entries should not be treated as a population-random sample.
