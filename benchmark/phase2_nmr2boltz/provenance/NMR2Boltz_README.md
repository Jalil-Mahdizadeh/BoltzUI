# nmr2boltz

`nmr2boltz` converts proton-containing distance restraints in **NEF** and **NMR-STAR** into conservative heavy-atom upper-bound contacts suitable for the `atom_contact` extension in BoltzUI/Boltz-2.

It is deliberately not a blind text converter. The program separates four different operations that are often conflated:

1. parsing the STAR data model and preserving restraint-group logic;
2. mapping source chain/sequence identifiers onto the exact Boltz input sequence;
3. resolving each proton to its directly bonded heavy atom from chemical topology;
4. projecting an upper bound with an explicit mathematical policy and quarantining unresolved OR ambiguity;
5. proving both projected atoms belong to their mapped component before executable YAML is written.

The default output contains only contacts that can be imposed **simultaneously** without changing the logical meaning of the source restraints.

## Installation

Python 3.10 or newer:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
pytest
```

Basic conversion:

```bash
nmr2boltz convert experiment.nef -o converted
nmr2boltz convert entry.str -o converted
```

For a protein, DNA, or RNA complex, request only contacts between different
mapped Boltz chain IDs:

```bash
nmr2boltz convert complex.nef --exclude-intrachain -o interchain
```

The comparison is applied after source-to-Boltz residue and chain mapping.
Exact same-chain contacts are omitted from `atom_constraints_exact.yaml`.
Ambiguous groups are retained in `atom_constraints_union.yaml` only when every
alternative is inter-chain. A group that mixes intra- and inter-chain
alternatives is omitted in full because keeping only its inter-chain branches
would narrow and strengthen the source OR restraint. Every omission is recorded
as `intrachain_filtered` in the audit outputs. With `--strict`, these audited
filter records produce the documented status 3.

To omit contacts within one mapped residue while retaining inter-residue
contacts:

```bash
nmr2boltz convert experiment.nef --exclude-intraresidue -o nonlocal
```

This policy applies to both exact and union output after residue mapping and
heavy-atom projection. An all-intraresidue OR group is omitted in full. A group
mixing intraresidue and inter-residue alternatives is also omitted in full,
because deleting only its intraresidue branches would narrow and strengthen
the source disjunction. Audit records use `intraresidue_filtered`, preserve
every source row and projected alternative, and distinguish all-local from
mixed residue scope.

For data lacking an explicit upper limit, the safe default is rejection. A heuristic may be requested explicitly:

```bash
nmr2boltz convert experiment.nef \
  --missing-upper-policy target-plus-uncertainty \
  -o converted
```

For modified residues, provide a local wwPDB Chemical Component Dictionary file or directory:

```bash
nmr2boltz convert experiment.nef --ccd ./ccd -o converted
```

Standard protein and RNA/DNA atom inventories are built in. Modified residues,
ligands, and ions are accepted only when embedded or supplied CCD topology
proves the atom name; declared author/canonical component aliases are both
retained so a verified canonical topology can validate an author name such as
`HSD`. Unknown component topology is quarantined, never guessed.

When the source numbering does not match the exact Boltz input, provide a tab-separated map:

```text
source_chain  source_sequence_code  source_residue_name  boltz_chain  boltz_residue_index
A             24B                   GLY                  A            25
```

```bash
nmr2boltz convert experiment.nef --residue-map residue_map.tsv -o converted
```

The residue map must be injective: two distinct source residues may not map to
the same Boltz chain/index, even when their residue names are identical. When a
restraint omits its chain and its author and canonical sequence identifiers
uniquely select different records, conversion rejects the endpoint instead of
choosing one identifier by iteration order.

The safer production path also supplies the exact Boltz input. Conversion stops
before writing executable constraints if a mapped chain, residue index, declared
modification, residue identity, exact-contact endpoint, or union-alternative
endpoint is incompatible with that target:

```bash
nmr2boltz convert experiment.nef \
  --target-yaml boltz_input.yaml \
  -o converted
```

## Docker

Build:

```bash
docker build -t nmr2boltz:0.1.0-validated .
```

Keep real inputs and outputs under `workspace/` and mount that directory at
`/workspace` for every run:

```bash
docker run --rm --network none --read-only --tmpfs /tmp:size=64m \
  -v "$PWD/workspace:/workspace" \
  nmr2boltz:0.1.0-validated \
  convert /workspace/input/experiment.nef -o /workspace/output/converted
```

Mount the writable workspace parent, not only the final output directory: the
rollback-safe writer creates its staging and backup directories beside the
requested output.

The image runs as numeric UID/GID 65532 by default. On Linux, add
`-u "$(id -u):$(id -g)"` if host-owned output files are preferred.
The validated image identifier, digest, offline/non-root smoke evidence, and
6M6O reproduction are recorded in [`VALIDATION.md`](VALIDATION.md).

## Reproducible benchmarks

`nmr2boltz benchmark` runs one or more conversions from a versioned YAML
manifest, verifies optional SHA-256 checksums, validates the sequence mapping
against the exact Boltz target, and compares observed audit metrics with pinned
expectations:

```bash
nmr2boltz benchmark workspace/benchmark.yaml \
  -o workspace/output/benchmark
```

Each case records its complete conversion bundle and a suite-level
`benchmark_summary.json`. A target mismatch, checksum mismatch, conversion
exception, or changed expected metric fails that case without preventing the
remaining corpus from running. A manifest case can set
`options: {exclude_intrachain: true}` to exercise the same inter-chain-only
policy reproducibly.

The paired-format deposited-structure corpus is run separately so that each
NEF/NMR-STAR pair is compared against every PDB conformer with sequence-aware
coordinate alignment:

```bash
python validation/benchmark_corpus.py benchmark/input \
  --output-directory benchmark/output \
  --reviewed-baseline benchmark/reviewed_baseline.json
```

Each PDB ID is written under `benchmark/output/<PDB-ID>/{nef,star}`. The root
`BENCHMARK_REPORT.md` and `benchmark_summary.json` record coordinate
satisfaction, conservative implication checks, and exact atom-pair/bound parity.
`FORMAT_DISCREPANCY_AUDIT.tsv` contains one traceable row for every NEF-only,
STAR-only, or different-bound contact, including source rows, expressions,
canonical expansions, resolved proton sets, pseudoatom handling, pair count,
averaging policy, source/projected bounds, and classification.
Files with valid sequence data but no distance-restraint loop produce an empty,
auditable conversion instead of failing format detection.

An `expected_format_difference` is accepted only through a tested semantic
allowlist: wildcard atom set versus explicit OR members, x/y assignment versus
a compatible physical set, rejected geometric Q/M pseudoatoms, or a verified
canonical naming alias. Unknown representation or rejection differences remain
`unresolved` and fail CI.

NMR-STAR canonical OR rows that retain one author-level atom name are
normalized before projection only when component topology proves a complete
proton set and the rows form its complete Cartesian product. This restores the
same `sum-r6` multiplicity used by the equivalent NEF atom set. Incomplete,
inconsistent, non-OR, or topology-unverified candidates fail closed; canonical
branches with different heavy parents remain union alternatives. Distinct
canonical spellings that topology resolves to the same physical proton remain
duplicate source evidence and are deduplicated only after projection; they are
not counted as additional physical protons.

The reviewed scientific interpretation of the current corpus is documented in
[`docs/BENCHMARK_DISCREPANCY_FINDINGS.md`](docs/BENCHMARK_DISCREPANCY_FINDINGS.md).

The corpus command is also a fail-closed CI gate. It exits nonzero for any
emitted atom-topology violation, projection implication failure, unresolved format discrepancy,
parser/projection bug, changed discrepancy digest, changed scientific metric,
or changed reviewed missing-coordinate set. Known coordinate limitations are
pinned by every contact identity, bound, source provenance, and a digest; they
are not count-only waivers.
Replacing the baseline is deliberately explicit and must follow scientific
review:

```bash
python validation/benchmark_corpus.py benchmark/input \
  --output-directory benchmark/output \
  --reviewed-baseline benchmark/reviewed_baseline.json \
  --write-reviewed-baseline
```

For a direct row-wise comparison of executable exact-contact bounds with every
deposited PDB conformer, generate the 12 per-entry CSV files:

```bash
python validation/distance_check.py benchmark/input \
  --conversion-output benchmark/output \
  --output-directory benchmark/distance_check
```

The generator independently applies each format's sequence map, cross-checks
the executable YAML bounds against conversion provenance, and fails on any
NEF/STAR coordinate-mapping disagreement for a common pair. Ambiguous union
alternatives are not flattened into independent rows. Current results and
artifact digests are in
[`benchmark/distance_check/README.md`](benchmark/distance_check/README.md).

## Output files

| File | Purpose |
|---|---|
| `atom_constraints_exact.yaml` | Non-ambiguous `atom_contact` constraints only. |
| `atom_constraints_union.yaml` | Ambiguous OR groups only, as metadata-free `atom_contact_union` constraints with one bound per alternative. |
| `heavy_atom_constraints.tsv` | Tabular `[X-Y: d]` result with Boltz chain, residue index, atom name, and bound. |
| `heavy_atom_constraints.txt` | Compact human-readable `[A:17:N -- A:42:CB : 6.20]` form. |
| `conversion_report.json` | Full machine-readable provenance, component-topology snapshot, formula terms, settings, warnings, ambiguity, and rejections. |
| `sequence_map.tsv` | Source identifier to Boltz residue-index mapping. This should be manually checked. |
| `sequences.fasta` | Clean polymer-only sequences extracted from the source mapping; caps, ions, and other non-polymers are omitted. |
| `ambiguous_groups.tsv` | Full audit metadata for the OR alternatives emitted in the union file, including any raw-to-Boltz minimum-bound adjustment. |
| `rejections.tsv` | Every restraint or group that could not be converted safely, with a reason and deterministic JSON provenance. |
| `summary.txt` | Concise run summary. |
| `hypotheses/*.yaml` | Optional assignment hypotheses generated with `--hypotheses N`. Each selects one alternative per ambiguous group. |

The complete output bundle is first written in a sibling staging directory.
Only after every artifact succeeds is it swapped into place; a failed write or
commit restores the prior bundle, preventing mixtures of old and new files.

## BoltzUI integration

The emitted YAML has the form:

```yaml
constraints:
- atom_contact:
    atom1: [A, 17, CG1]
    atom2: [A, 42, CB]
    max_distance: 8.009000
    force: true
```

Merge the list into the same Boltz input that defines the corresponding chains
and sequences. The current BoltzUI patch requires Boltz-2 and `force: true`.
Atom-contact guidance remains active independently of `--use_potentials`; that
flag enables additional FK/physical steering and is optional. The patch accepts
distances only in the interval 2–20 Å. The converter therefore:

- raises every exact or union-alternative value below 2 Å to 2 Å, which weakens
  the restraint and is recorded in provenance;
- never clips a value above 20 Å, because clipping would strengthen it;
- rejects an over-20 Å exact contact and quarantines a complete union group if
  any alternative exceeds 20 Å; it never strengthens an OR by dropping only
  the incompatible alternative.

## Projection policies

For an explicit proton pair with experimental upper bound `U`, directly bonded parents `P1/P2`, and conservative X-H bond-length envelopes `l1/l2`, the converter uses the triangle inequality:

```text
d(P1,P2) <= U + l1 + l2 + margin
```

For H-X only one X-H term is added. For heavy-heavy input no X-H term is added.

An atom-set expression such as `HG1%` may represent several proton pairs. The default `--averaging sum-r6` policy assumes the unnormalized effective distance

```text
r_eff = (sum_i r_i^-6)^(-1/6)
```

and uses the rigorous existence bound

```text
min_i(r_i) <= N^(1/6) U
```

for `N` explicit proton pairs. `--averaging mean-r6` uses the normalized mean convention and factor 1. `--averaging hard-or` also uses factor 1 and treats the source as an existential assignment alternative. The correct policy depends on how the deposited bounds were calibrated and whether pseudoatom/atom-set corrections were already incorporated.

## Ambiguity rules

The converter distinguishes:

- **atom set with one parent**, for example `VAL HG1% -> CG1`; this can collapse safely;
- **atom set with several parents**, for example `TYR HD% -> CD1 OR CD2`; this remains an OR group;
- **non-stereospecific x/y assignment**, which remains an assignment alternative unless all choices share a parent;
- **geometric Q/M pseudoatom**, which is rejected by default because it is not the same object as a wildcard atom set;
- **multiple rows with the same restraint ID**, which are treated as alternatives, not independent simultaneous contacts;
- **topology-proven canonical expansions of one author atom set**, whose complete OR-row Cartesian product is reconstructed before `sum-r6` projection;
- **non-null restraint-combination identifiers or non-OR NMR-STAR member logic**, which are preserved but not flattened because they may encode nested logic.

After residue mapping and proton-to-heavy projection, both heavy atoms are
checked against the mapped component topology before OR/pair deduplication. If
either endpoint is absent—or the component topology is unavailable—the whole
contact is quarantined as `atom_not_present_in_mapped_residue`. The writer then
repeats the invariant against the frozen target-topology snapshot before it
creates any output file. Coordinate absence is never used as atom-validity
evidence.

For external or embedded CCD data, a hydrogen must have exactly one heavy-atom
bond. Multiple heavy parents are retained as a deterministic topology conflict
and fail closed; bond-file ordering can never choose a parent. Malformed atom
or bond tables raise a contextual topology error rather than being ignored.

Inside one OR group, two alternatives that map to the same heavy pair are combined using the **larger** bound. Across independent restraint groups, duplicate heavy pairs are combined using the **smaller** bound.
If any alternative or atom-set branch in an OR group cannot be projected safely, none of the remaining alternatives are emitted because a partial OR would be stronger than the source restraint. Executable upper bounds are rounded upward at six decimal places so serialization never tightens them.

`--exclude-intrachain` applies the same completeness rule after projection and
topology validation, using the mapped Boltz chain IDs. A final writer invariant
prevents any same-chain exact contact or union alternative from entering an
inter-chain-only output bundle.

`--exclude-intraresidue` likewise applies before the exact/union split using
mapped Boltz chain and residue-index identity. Its final writer invariant
prevents any intraresidue exact contact or union alternative from entering the
filtered output bundle.

## Safe workflow for structure generation

1. Run the converter with default policies and inspect `sequence_map.tsv` first.
2. Use `atom_constraints_exact.yaml` as the high-confidence guidance set.
3. Run multiple Boltz diffusion samples rather than relying on one structure.
4. For ambiguous data, use `atom_constraints_union.yaml` only with a union-aware parser/potential, or generate several assignment hypotheses with `--hypotheses`.
5. Reconstruct hydrogens on candidate structures using an NMR-aware protonation/geometry tool.
6. Re-evaluate the original NEF/NMR-STAR restraints, including atom-set averaging and ensemble behavior, and rank/filter structures by violations.
7. Compare restrained and unrestrained predictions to detect over-guidance or numbering mistakes.

## Important limitations

- An NOE upper bound is an experimental/modeling restraint, not necessarily a literal hard instantaneous distance.
- Dynamic and conformational-ensemble averaging is not reproduced by a single heavy-atom contact.
- Exchangeable protons depend on protonation, tautomer, solvent, pH, and temperature.
- The built-in topology covers standard protein and common RNA/DNA atom inventories. Modified components, ligands, and ions require embedded NMR-STAR chemistry or a local CCD file; unknown topology fails closed.
- A consumer must implement `atom_contact_union` as one disjunction. Marking every OR alternative as an independent contact would overconstrain the model.
- A soft Boltz potential encourages a contact but does not guarantee restraint satisfaction. Post-prediction validation remains mandatory.
- Paired NEF and NMR-STAR exports can still encode genuinely different wildcard,
  stereospecific-assignment, or geometric-pseudoatom semantics; inspect
  `format_parity.json` before treating them as interchangeable.

## Documentation

- `docs/CLI_REFERENCE.md`: complete global, conversion, and benchmark CLI flag
  list with descriptions and effective default values.
- `docs/SCIENTIFIC_METHOD.md`: derivation, format interpretation, assumptions, and validation plan for NMR experts.
- `benchmark/output/BENCHMARK_REPORT.md`: current 12-structure paired-format benchmark and coordinate audit.
- `benchmark/distance_check/README.md`: exact-contact NEF/STAR bounds beside every deposited PDB-model distance.
- `docs/BOLTZUI_UNION_EXTENSION.md`: proposed representation and implementation path for ambiguity-aware atom contacts.
- `docs/EXPERT_REVIEW_CHECKLIST.md`: decisions that should be reviewed before production use.

## Primary references and specifications

- NMR Exchange Format specification and commented examples: https://github.com/NMRExchangeFormat/NEF
- Gutmanas et al., *NMR Exchange Format: a unified and open standard for representation of NMR restraint data*, Nature Structural & Molecular Biology (2015), DOI: 10.1038/nsmb.3041
- Biological Magnetic Resonance Data Bank: https://bmrb.io/
- PyNMRSTAR: https://github.com/uwbmrb/PyNMRSTAR and https://pypi.org/project/pynmrstar/
- wwPDB NMR data standards: https://www.wwpdb.org/documentation/file-format-content
- wwPDB Chemical Component Dictionary: https://www.wwpdb.org/data/ccd
- Boltz: https://github.com/jwohlwend/boltz
- BoltzUI atom-contact implementation used for the target schema: https://github.com/Jalil-Mahdizadeh/BoltzUI

To enumerate current-schema calculations for unresolved OR groups, add `--hypotheses N`. Each generated YAML is a separate alternative calculation; never concatenate them into one constraint set.
