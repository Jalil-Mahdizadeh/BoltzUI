# Boltz atom_contact patch

This directory contains the reproducible patch layer that adds Boltz2-only
`atom_contact` constraints to the installed Boltz runtime in the Docker image.

The patch is applied during `docker build` by `apply_atom_contact_patch.py`.
It locates the installed Boltz source files through Python imports and
`inspect.getfile`, then patches explicit source anchors. The patcher is
idempotent and compiles the modified files before the image build continues.

Supported YAML:

```yaml
constraints:
  - atom_contact:
      atom1: [A, 145, NZ]
      atom2: [B, 37, OD1]
      max_distance: 3.5
      force: true
```

Rules:

- `atom_contact` is only supported for Boltz2.
- `atom1` and `atom2` must be `[CHAIN_ID, RES_IDX, ATOM_NAME]`.
- Residue indices are 1-indexed in YAML.
- `max_distance` must be finite and in the `2.0-20.0` Angstrom range.
- `force: true` is required because exact atom-atom enforcement uses
  inference-time contact potentials.
- Predictions using `atom_contact` must run with `--use_potentials`.
- `atom_contact` is sampling guidance, not a final minimizer. Local benchmarks
  gave stronger satisfaction with `--sampling_steps 400`, `--step_scale 1.0`,
  multiple diffusion samples, and post-run distance filtering.
