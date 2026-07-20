# Boltz atom_contact patch

This directory contains the reproducible patch layer that adds Boltz2-only
exact `atom_contact` and ambiguous `atom_contact_union` constraints and
corrects diffusion sample chunking in the installed Boltz runtime in the
Docker image.

The patch is applied during `docker build` by `apply_atom_contact_patch.py`.
It locates the installed Boltz source files through Python imports and
`inspect.getfile`, verifies the Boltz 2.2.1 source SHA-256 hashes, then patches
explicit source anchors. The patcher is idempotent and compiles the modified
files before the image build continues. `--check` performs compatibility
validation without editing installed files.

The Boltz 2.2.1 diffusion implementation passes a remainder-derived value to
`torch.chunk`, so `max_parallel_samples=1` can process every requested sample
in one denoiser call. This patch uses `Tensor.split(max_parallel_samples)`,
making the option a true maximum denoiser batch size. It deliberately does not
change RNG generation, outer-loop sampling, confidence execution, or output order.

Supported YAML:

```yaml
constraints:
  - atom_contact:
      atom1: [A, 145, NZ]
      atom2: [B, 37, OD1]
      max_distance: 3.5
      force: true

  - atom_contact_union:
      alternatives:
        - atom1: [A, 145, NZ]
          atom2: [B, 37, OD1]
          max_distance: 3.5
        - atom1: [A, 145, CE]
          atom2: [B, 37, OD1]
          max_distance: 4.2
      force: true
```

Rules:

- `atom_contact` and `atom_contact_union` are only supported for Boltz2.
- `atom1` and `atom2` must be `[CHAIN_ID, RES_IDX, ATOM_NAME]`.
- Residue indices are 1-indexed in YAML.
- `max_distance` must be finite and in the `2.0-20.0` Angstrom range.
- `force: true` is required because specific atom-pair distance guidance uses
  a soft inference-time contact potential.
- Boltz contact guidance remains active without `--use_potentials`. That flag
  enables additional FK/physical steering and remains on by default in the
  experimental UI preset.
- `atom_contact` adds token-level contact conditioning and exactly one atom-index
  pair to the contact potential. Multiple atom contacts between the same token
  pair use the minimum token threshold independent of YAML order, while every
  exact atom pair is preserved. It is sampling guidance, not a mathematical
  guarantee or final minimizer. The experimental UI preset changes the
  reverse-diffusion sampling schedule; lower step scale changes the update and
  sample diversity and may interact with guidance.
  Final distances must be checked in `atom_contact_restraints.json`.
- `atom_contact_union` requires at least two unique alternatives. Every
  alternative retains its own bound, and all alternatives in one group share
  one contact-potential `union_index`. Separate union groups use separate
  indices.
- Union alternatives do not enter binary token-contact conditioning. Applying
  that conditioning to every alternative would recreate AND semantics even
  though the coordinate potential is grouped as OR.
- Reversed duplicate alternatives, same-atom endpoints, unresolved selectors,
  non-finite/out-of-range bounds, missing group-level `force: true`, and
  Boltz-1 inputs are rejected before featurization.
