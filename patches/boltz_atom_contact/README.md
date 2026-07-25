# Boltz atom_contact patch

This directory contains the reproducible patch layer that adds Boltz2-only
exact `atom_contact`, ambiguous `atom_contact_union`, and CSP-derived
`interface_contact` constraints and
corrects both union-potential reduction and diffusion sample chunking in the
installed Boltz runtime in the Docker image.

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

  - interface_contact:
      patch1:
        chain: A
        residues: [12, 15, 19]
      patch2:
        chain: B
        residues: [34, 40, 43]
      max_distance: 6.0
      force: true
```

Rules:

- `atom_contact`, `atom_contact_union`, and `interface_contact` are only supported for Boltz2.
- `atom1` and `atom2` must be `[CHAIN_ID, RES_IDX, ATOM_NAME]`.
- Residue indices are 1-indexed in YAML.
- `max_distance` must be finite and in the `2.0-20.0` Angstrom range.
- `force: true` is required because specific atom-pair distance guidance uses
  an inference-time contact potential.
- Boltz contact guidance remains active without `--use_potentials`. That flag
  enables additional FK/physical steering and remains on by default in the
  experimental UI preset.
- `atom_contact` adds token-level contact conditioning and exactly one atom-index
  pair to the contact potential. Multiple atom contacts between the same token
  pair use the minimum token threshold independent of YAML order, while every
  distinct exact atom pair is preserved. Reversed duplicate exact pairs are
  rejected, and intra-token pairs do not set diagonal token conditioning.
  It is sampling guidance, not a mathematical
  guarantee or final minimizer. The experimental UI preset changes the
  reverse-diffusion sampling schedule; lower step scale changes the update and
  sample diversity and may interact with guidance.
  Final distances must be checked in `contact_restraints.json`.
- `atom_contact_union` requires at least two unique alternatives. Every
  alternative retains its own bound, and all alternatives in one group share
  one contact-potential `union_index`. Separate union groups use separate
  indices. Each group uses the exact minimum flat-bottom violation; a satisfied
  alternative therefore gives the group zero energy and distant alternatives
  cannot pull it. This also avoids exponential underflow on large violations.
- Union alternatives do not enter binary token-contact conditioning. Applying
  that conditioning to every alternative would recreate AND semantics even
  though the coordinate potential is grouped as OR.
- `interface_contact` accepts exactly two nonempty protein-residue patches.
  Different chains and two disjoint, non-neighbor regions on one chain are
  supported.
- For every active residue on each side, the runtime creates one potential
  group containing all eligible heavy-atom pairs to the opposite patch. The
  group distance is the literal closest pair, matching the final report. Each
  reciprocal direction contributes `0.5` times the mean 2-Angstrom Huber
  penalty. The normalized energy is patch-size-independent and every violated
  active residue receives a bounded gradient. Sampling scales that gradient by
  `4.0` before translating every modeled atom in each affected residue
  coherently and capping its norm at `0.5`. Interface energy participates in
  particle resampling; the clash term does not.
- This is HADDOCK-inspired reciprocal AIR topology, not raw HADDOCK D^-6
  energy. Raw D^-6 is a pseudo-distance that can be shorter than every physical
  pair, so it cannot share BoltzUI's literal `max_distance` pass/fail meaning.
- Interface bounds must be finite and in the `4.0-20.0` Angstrom range. The UI
  defaults to `6.0` Angstrom. Guidance and reporting apply the same literal
  closest-heavy-atom bound. Linear and cyclic same-chain neighbors and explicit
  structure bonds are excluded from attraction. Every active residue must have
  an eligible opposite-patch residue, and a forced interface fails if cropping
  removes any submitted active selector. `force: true` activates guidance;
  `force: false` is retained for post-run reporting and adds no binary or
  potential guidance.
- An interface-only repulsive term protects nonbonded cross-patch atom pairs
  below `2.5` Angstrom. It excludes ordinary and cyclic sequence neighbors and
  explicit structure bonds. It is not a whole-structure clash score.
- Duplicate or reversed definitions of the same patch pair are rejected.
  Multiple distinct interfaces remain independent and additive.
- Interface tensors and potentials are separate from the native token-contact
  tensors and potential.
- Interface definitions do not use constraint subsampling or FreeSASA-based
  passive-residue expansion.
- Reversed duplicate alternatives, same-atom endpoints, unresolved selectors,
  non-finite/out-of-range bounds, missing group-level `force: true`, and
  Boltz-1 inputs are rejected before featurization.
