# BoltzUI

BoltzUI is a Dockerized web app for Boltz 2.2.1. The Docker image starts the web interface, exposes it on port `5173`, and runs predictions inside the same container. This build is layered on the local `boltz:221` image and adds reproducible Boltz2-only exact `atom_contact` and ambiguous `atom_contact_union` guidance, corrected `max_parallel_samples` denoiser chunking, neutral-pH hydrogen placement, and optional Amber energy minimization.

## Repository Contents

- `Dockerfile` - builds the patched BoltzUI web app image on top of the local `boltz:221` image.
- `patches/boltz_atom_contact/` - reproducible Boltz runtime patch applied during Docker build.
- `server.js`, `public/`, `package.json` - BoltzUI web interface for configuring, launching, and inspecting Boltz runs.
- `run.sh` - optional launcher for the BoltzUI container.
- `requirements.txt` - Python package pin for Boltz.
- `requirements-postprocess.txt` - pinned OpenMM, CUDA plugin, and PDBFixer dependencies included in the image.
- `REQUIREMENTS.md` - host, GPU, disk, and cache requirements.
- `DOCKER_HUB.md` - copy-ready Docker Hub overview text.
- `workspace/inputs/` - Boltz YAML/JSON/FASTA inputs. Example inputs live here.
- `workspace/results/` - default Boltz output directory. Boltz creates `boltz_results_<input-stem>/` folders here.

## Build The Image

The patched build expects the base workflow image to already exist locally:

```bash
docker image inspect boltz:221 >/dev/null
```

Build:

```bash
docker build -t boltzui:221-exact-union .
```

The final `boltzui:221-exact-union` image contains the Boltz runtime from `boltz:221`, Node.js, the BoltzUI web app, exact and union atom-contact support, bounded denoiser sample chunking, OpenMM, its CUDA 12 plugin, and PDBFixer. No second runtime image is required.

## Run The Web UI

Run the container:

```bash
docker run --rm --gpus all \
  --shm-size=8g \
  -p 5173:5173 \
  -v "$(pwd):/workspace/BoltzUI" \
  -w /workspace/BoltzUI \
  boltzui:221-exact-union
```

PowerShell equivalent:

```powershell
docker run --rm --gpus all --shm-size=8g `
  -p 5173:5173 `
  -v "${PWD}:/workspace/BoltzUI" `
  -w /workspace/BoltzUI `
  boltzui:221-exact-union
```

Then open:

```text
http://localhost:5173
```

After building the image, `bash run.sh` runs the same container command on Unix-like shells.

BoltzUI exposes every `boltz predict` option from the installed 2.2.1 CLI plus its two post-processing flags, builds a command preview, launches jobs with collapsible live logs, summarizes existing `workspace/results/boltz_results_*` folders, and opens generated PDB structures in an embedded 3Dmol workspace. Inputs and results are kept under `workspace/` by default so the repository root stays clear.

The sidebar is collapsed by section by default. `Input` selects the prediction file, `Settings` contains the full flag set, and `MSA settings` groups MSA server, credential, and limit controls under one section. The structure preview includes a 0-100 confidence color legend whenever the viewer color mode is set to `Confidence`.

### Hydrogens And Energy Minimization

The `Output` settings contain two mutually exclusive switches, both off by default:

- `Add hydrogens` / `--addh` writes hydrogenated copies.
- `Add hydrogens + energy minimize` / `--addh-energy-min` adds hydrogens and then minimizes the copies.

BoltzUI runs predictions through the installed `boltzui-predict` pass-through command. It removes the two BoltzUI-only flags before invoking upstream `boltz`, waits for prediction to finish, and then post-processes every generated PDB or mmCIF model. Original Boltz models are never overwritten. Derived files are written below `postprocessed/addh/` or `postprocessed/addh_energy_min/` in the same result directory and appear as separate model variants in the result browser. `boltzui_postprocess.json` records hashes, atom counts, protonation variants, terminal repairs, software and force-field settings, platform, energies, and coordinate displacement. Derived PDB files retain Boltz confidence B-factors; newly added atoms inherit the residue confidence.

Hydrogens are placed with OpenMM `Modeller.addHydrogens()` at pH 7.0 using Amber14 templates. This applies the usual dominant neutral-pH states, recognizes disulfide-bonded cysteine, and chooses a histidine tautomer from the local hydrogen-bond geometry. It is not a microscopic pKa calculation or constant-pH simulation.

Minimization uses Amber14 ff14SB for protein, OL15 for DNA, OL3 for RNA, and GBn2 implicit solvent with `NoCutoff`, `HBonds` constraints, and OpenMM's L-BFGS minimizer (10 kJ/mol/nm tolerance, at most 250 iterations). CUDA mixed precision with deterministic forces is preferred; OpenCL and four-thread CPU execution are fallbacks. Boltz has already exited before post-processing starts, so its GPU allocation is released first.

The current safe scope is standard protein, RNA, and DNA residues. Ligands and modified residues are rejected instead of being silently assigned unsuitable parameters. Boltz emits a 5-prime phosphate for a first RNA/DNA residue, whereas Amber OL3/OL15 use a standard 5-prime hydroxyl terminus; derived nucleic-acid copies therefore remove terminal `P`, `OP1`, and `OP2` atoms before protonation, and record that normalization explicitly. The original model remains byte-identical.

### Prediction Presets

Preset values are generated from `lib/prediction-config.js`, which is also used by the server and browser. Selecting a named preset resets all visible prediction controls to its resolved values. Editing any prediction control changes the selected state to `Custom`.

<!-- BEGIN GENERATED PREDICTION PRESETS -->
| Preset | Sampling steps | Step scale | Potentials | Status |
|---|---:|---:|---|---|
| Standard Boltz-2 | 200 | 1.5 | Off | Standard |
| Atom-contact exploration | 400 | 1.0 | On | Experimental |

The atom-contact exploration preset is experimental. Its lower step scale changes the reverse-diffusion update and sample diversity and may interact with inference-time potential guidance; it is not a mathematical guarantee of restraint satisfaction.
<!-- END GENERATED PREDICTION PRESETS -->

## YAML Builder

The dedicated YAML Builder page at `http://localhost:5173/builder.html` is the primary authoring surface for Boltz input files and is available from the distinctive `YAML Builder` button at the top of the sidebar. It provides schema-guided templates for structure, multimer, protein-ligand, affinity, pocket constraints, token contact constraints, exact atom contact constraints, union atom contact constraints, and template-based predictions, then writes ordinary `.yaml` files into `workspace/inputs/`.

The builder covers Boltz YAML features that are not available in FASTA: any number of protein/DNA/RNA polymers, multiple identical chain IDs, automatic/custom/empty protein MSA modes, cyclic polymers, modified residues, any number of ligands by SMILES or CCD code, pocket constraints, repeatable token-level contacts, repeatable exact atom-pair upper-distance restraints, repeatable ambiguous atom-pair OR groups, covalent bonds, structural templates, and the Boltz-2 affinity property. Affinity runs still need a single ligand copy as the binder. The generated YAML remains directly editable before saving.

The Token, Exact atom-contact, and Union atom-contact sections each have a dedicated nmr2boltz loader. `token_constraints.yaml` replaces only the token-contact cards, `atom_constraints_exact.yaml` replaces only the exact-contact cards, and `atom_constraints_union.yaml` replaces only the union-group cards; sequences, ligands, settings, and all other constraint types are preserved. The loaders parse YAML on the server and validate the corresponding constraint structure. An empty `constraints: []` file intentionally clears the corresponding section.

### Constraint Types

- `contact` is the existing token-level proximity constraint. For protein/RNA/DNA polymers, a token is a residue or nucleotide selected by `[CHAIN_ID, RES_IDX]`; for ligands/non-polymers, a token is an atom selected by `[CHAIN_ID, ATOM_NAME]`.
- `pocket` keeps the existing binder/contact behavior unchanged.
- `bond` is the existing covalent atom-level bond constraint using `[CHAIN_ID, RES_IDX, ATOM_NAME]`.
- `atom_contact` is a patched Boltz2-only exact atom-pair upper-distance restraint using `[CHAIN_ID, RES_IDX, ATOM_NAME]`.
- `atom_contact_union` is a patched Boltz2-only OR group containing two or more exact atom-pair alternatives, each with its own upper-distance bound.

`atom_contact` requires `force: true` and `max_distance` in the `2.0-20.0` Angstrom range. It contributes token-level contact conditioning for the containing tokens and one exact atom-index pair to Boltz's soft inference-time contact guidance. Multiple restraints on the same token pair use the minimum distance for token conditioning while every exact atom pair remains in the atom-level potential. This does not mathematically guarantee the final distance. The experimental Atom-contact exploration preset changes the reverse-diffusion sampling schedule and enables optional physical potentials; final satisfaction must be checked in `atom_contact_restraints.json`.

`atom_contact_union` also requires group-level `force: true`, at least two alternatives, and a finite `2.0-20.0` Angstrom bound on every alternative. Reversed duplicate pairs within one group, identical endpoints, unresolved atoms, and partial groups are rejected. All alternatives in a group receive the same Boltz potential `union_index`; separate groups receive separate indices. A union is therefore satisfied when any one alternative is satisfied. Union alternatives deliberately do not set binary token-contact conditioning, because marking every alternative as a contact would change the intended OR relation into AND. Optional `--use_potentials` physical steering is independent of both exact and union contact guidance.

Example:

```yaml
version: 1
sequences:
  - protein:
      id: A
      sequence: K
      msa: empty
  - protein:
      id: B
      sequence: D
      msa: empty
constraints:
  - atom_contact:
      atom1: [A, 1, NZ]
      atom2: [B, 1, OD1]
      max_distance: 3.5
      force: true
```

The redistributable test fixture is available at `fixtures/atom_contact_example.yaml`.

Union example:

```yaml
constraints:
  - atom_contact_union:
      alternatives:
        - atom1: [A, 10, CG1]
          atom2: [A, 42, CB]
          max_distance: 7.0
        - atom1: [A, 10, CG2]
          atom2: [A, 42, CB]
          max_distance: 7.0
      force: true
```

The complete union fixture is `fixtures/atom_contact_union_example.yaml`. Constraints-only loader fixtures matching nmr2boltz output are under `fixtures/nmr2boltz/`.

### Run Provenance And Restraint Audit

Every completed, stopped, or failed submitted process writes `boltzui_run.json` into its `workspace/results/boltz_results_<input-stem>/` directory. Manifest schema version 3 records the Git commit when available, Boltz version, selected preset, resolved parameters, credential-free command arguments, input SHA-256, MSA configuration, post-processing report when requested, timestamps, exit status, and submitted exact and union atom-contact restraints.

Atom-contact runs also write `atom_contact_restraints.json` in the same directory. Report schema version 3 measures every exact pair and every union alternative in each generated PDB or mmCIF structure and adds compact per-model exact/union aggregates for NMR-scale restraint sets. A union group is satisfied if any alternative is within its own bound, violated only when every alternative resolves and violates, and indeterminate when unresolved alternatives prevent a definitive violation. The result viewer exposes both JSON files, shows exact and union summaries separately from Boltz confidence metrics, and renders at most 500 audit rows for the selected model with violations first; the complete measurements remain in the JSON report.

PDB reports use the one-character chain identifiers present in the PDB file. Use mmCIF output when identifiers cannot be represented unambiguously in PDB. For mmCIF, the reporter resolves matching author identifiers first and also supports label identifiers without mixing the two namespaces.

## Prediction Options

The sidebar exposes these Boltz `predict` options:

- `DATA` - input YAML/JSON/FASTA path, for example `workspace/inputs/NusA_open.yaml`. No default.
- `--out_dir PATH` - base directory where predictions are saved. BoltzUI default: `workspace/results`; Boltz appends `boltz_results_<input-stem>`.
- `--cache PATH` - cache directory for model and molecule data. Default is `~/.boltz`, or `$BOLTZ_CACHE` if set. This image uses `/opt/boltz-cache`.
- `--checkpoint PATH` - optional structure checkpoint path. Default is `None`; Boltz uses the bundled/default model checkpoint.
- `--devices INTEGER` - number of devices to use. Default: `1`.
- `--accelerator [gpu|cpu|tpu]` - accelerator backend. Default: `gpu`.
- `--recycling_steps INTEGER` - number of recycling iterations. Default: `3`.
- `--sampling_steps INTEGER` - number of diffusion sampling steps. Determined by the selected preset; see the generated preset table above.
- `--diffusion_samples INTEGER` - number of generated structure samples. Default: `1`.
- `--max_parallel_samples INTEGER` - maximum samples passed through each denoiser call. BoltzUI default: `1`. The patched runtime treats this as a true chunk size.
- `--step_scale FLOAT` - reverse-diffusion step scale. Determined by the selected preset; changing it affects reverse-diffusion updates and sample diversity and can interact with potential guidance.
- `--write_full_pae` - writes full PAE as an NPZ file. Default: `True`.
- `--write_full_pde` - writes full PDE as an NPZ file. Default: `False`.
- `--output_format [pdb|mmcif]` - structure output format. BoltzUI default: `pdb`.
- `--num_workers INTEGER` - dataloader worker count. BoltzUI default: `0`.
- `--override` - overwrites existing predictions. Default: `False` for standard tasks and `True` when the input contains `atom_contact` or `atom_contact_union`; users can explicitly disable it in Custom settings.
- `--addh` - preserves original models and writes neutral-pH hydrogenated copies. Default: `False`.
- `--addh-energy-min` - preserves original models and writes neutral-pH hydrogenated, Amber14/GBn2-minimized copies. Default: `False`; mutually exclusive with `--addh`.
- `--seed INTEGER` - random seed. BoltzUI default: `1`; use `-1` for a random seed.
- `--use_msa_server` - generates missing protein MSAs through the MMSeqs2 server. BoltzUI default: `True`.
- `--msa_server_url TEXT` - MSA server URL, used with `--use_msa_server`. Default: `https://api.colabfold.com`.
- `--msa_pairing_strategy TEXT` - MSA pairing strategy, `greedy` or `complete`, used with `--use_msa_server`. Default: `greedy`.
- `--msa_server_username TEXT` - username for MSA server basic auth. Default: `None`; can also use `$BOLTZ_MSA_USERNAME`.
- `--msa_server_password TEXT` - password for MSA server basic auth. Default: `None`; can also use `$BOLTZ_MSA_PASSWORD`.
- `--api_key_header TEXT` - custom API-key header name. Option default: `None`; when API-key auth is used and no header is provided, Boltz uses `X-API-Key`.
- `--api_key_value TEXT` - custom API-key header value. Default: `None`.
- `--use_potentials` - enables Boltz's additional FK/physical steering potentials. It is optional for `atom_contact` and `atom_contact_union` because contact guidance remains active independently, but it defaults to on in the experimental Atom-contact exploration preset.
- `--model [boltz1|boltz2]` - model family. Default: `boltz2`.
- `--method TEXT` - method metadata/conditioning value selected from Boltz 2.2.1's supported methods. Default: `x-ray diffraction` (`X-RAY DIFFRACTION` in the UI).
- `--preprocessing-threads INTEGER` - preprocessing thread count. Default: `1`.
- `--affinity_mw_correction` - enables molecular-weight correction for affinity prediction. Default: `False`.
- `--sampling_steps_affinity INTEGER` - affinity sampling steps. Default: `200`.
- `--diffusion_samples_affinity INTEGER` - affinity diffusion samples. Default: `5`.
- `--affinity_checkpoint PATH` - optional affinity checkpoint path. Default: `None`; Boltz uses the bundled/default affinity checkpoint.
- `--max_msa_seqs INTEGER` - maximum MSA sequences used. BoltzUI default: `8192`, matching upstream Boltz.
- `--subsample_msa` - subsamples MSA sequences. BoltzUI default: `True`, matching upstream Boltz.
- `--num_subsampled_msa INTEGER` - number of MSA sequences after subsampling. BoltzUI default: `1024`, matching upstream Boltz.
- `--no_kernels` - disables optional optimized kernels. BoltzUI default: `True`.
- `--write_embeddings` - writes `s` and `z` embeddings to NPZ. Default: `False`.
- `--help` - prints command help.

## GPU Guidance

Boltz2 can fill small laptop GPUs. On an 8 GB GPU, keep:

```bash
--max_parallel_samples 1
```

This limits denoiser activations, but the minimal patch still allocates coordinate,
noise, mask, and guidance state for all `diffusion_samples`. Peak VRAM therefore
does not become independent of the total sample count.

If a run fails with CUDA out-of-memory, lower:

```bash
--diffusion_samples
--recycling_steps
```

For a very conservative first test, set these options in the sidebar:

```bash
--diffusion_samples 1
--recycling_steps 3
--max_parallel_samples 1
```

## Diffusion Chunking Benchmark

The original Boltz 2.2.1 implementation used a remainder-derived argument to
`torch.chunk`; for 10 samples, `max_parallel_samples=1` incorrectly produced one
10-sample denoiser call. This image uses `Tensor.split(max_parallel_samples)`.

The supplied 69-residue sequence was run with `msa: empty`, seed `42`, 200 sampling
steps, 3 recycling steps, step scale 1.5, and 10 PDB samples on the 8151 MiB laptop
GPU. Peak values are total GPU memory reported by `nvidia-smi`, including the desktop.

| Runtime | Effective denoiser batches | Time | Peak GPU | Mean aligned all-atom RMSD vs pre-fix | Exact PDBs |
|---|---|---:|---:|---:|---:|
| Pre-fix, requested parallel limit 1 | `10` | 124.0 s | 2855 MiB | reference | 10/10 |
| Fixed, parallel limit 1 | `1 x 10 calls` | 275.9 s | 2743 MiB | 0.000370 A | 0/10 |
| Fixed, parallel limit 2 | `2 x 5 calls` | 183.1 s | 2743 MiB | 0.000411 A | 0/10 |
| Fixed, parallel limit 5 | `5 x 2 calls` | 125.1 s | 2785 MiB | 0.000419 A | 0/10 |
| Fixed, parallel limit 10 | `10` | 109.3 s | 2855 MiB | 0.000000 A | 10/10 |

The fixed parallel-limit-10 run reproduced all baseline PDB and confidence files
exactly. Smaller chunks changed floating-point execution shape: corresponding models
remained sub-milliangstrom-equivalent, but were not byte-identical. The largest
confidence-score change was `0.000238`.

## Laptop Smoke Benchmark

A tiny local smoke test was run on this machine without writing outputs to the repository:

- Input: 40 amino acids, single protein chain, `msa: empty`.
- Settings: `diffusion_samples=1`, `recycling_steps=1`, `sampling_steps=5`, `max_parallel_samples=1`, `num_workers=0`, `--no_kernels`.
- CPU result: `506.502 s`.
- GPU result: `50.981 s`.
- GPU speedup: about `9.9x`.

This test confirms that the laptop GPU can run a very small Boltz2 job, but it does not prove that the full 495-residue NusA examples will fit in 8 GB VRAM.

## Laptop GPU Length Boundary

The maximum confirmed successful GPU prediction length on this laptop was measured with a synthetic single-chain protein and the same conservative benchmark settings:

- `msa: empty`
- `--accelerator gpu`
- `--devices 1`
- `--diffusion_samples 1`
- `--recycling_steps 1`
- `--sampling_steps 5`
- `--max_parallel_samples 1`
- `--num_workers 0`
- `--no_kernels`
- `--output_format pdb`

Results on the NVIDIA RTX PRO 2000 Blackwell Generation Laptop GPU with 8151 MiB VRAM:

| Sequence length | Result | Elapsed time |
|---:|---|---:|
| 100 aa | Success | `72.222 s` |
| 300 aa | Success | `72.338 s` |
| 500 aa | Success | `90.550 s` |
| 700 aa | Success | `131.974 s` |
| 750 aa | Failed: CUDA driver `device not ready` | `137.883 s` before failure |
| 800 aa | Failed: CUDA driver `device not ready` | `160.515 s` before failure |
| 900 aa | Failed: CUDA driver `device not ready` | `61.546 s` before failure |

For this laptop, treat `700 aa` as the largest confirmed working length for minimal GPU testing. This is not a general production limit: real inputs with MSAs, higher `sampling_steps`, more `diffusion_samples`, more `recycling_steps`, `--use_potentials`, or parallel sampling can require substantially more VRAM. Full-quality UI settings can be much heavier than this benchmark.

## Real NusA GPU Ladder

The real 495-residue `NusA_open.yaml` sequence was tested on the same laptop GPU. All runs used `--accelerator gpu`, `--devices 1`, `--no_kernels`, `--max_parallel_samples 1`, `--num_workers 0`, and disposable output directories inside the container.

| Step | Key settings | Result | Elapsed time |
|---|---|---|---:|
| Minimal single-sequence | `msa: empty`, `diffusion_samples=1`, `recycling_steps=1`, `sampling_steps=5` | Success | `83.473 s` |
| Enable full local MSA | local MSA, default `max_msa_seqs=8192`, `num_subsampled_msa=1024` | Failed in MSA module: CUDA driver `device not ready` | `66.852 s` before failure |
| Cap MSA to 128 | `max_msa_seqs=128`, `num_subsampled_msa=128` | Success | `94.789 s` |
| Cap MSA to 256 | `max_msa_seqs=256`, `num_subsampled_msa=256` | Success | `94.137 s` |
| Cap MSA to 512 | `max_msa_seqs=512`, `num_subsampled_msa=512` | Success | `86.743 s` |
| Cap MSA to 768 | `max_msa_seqs=768`, `num_subsampled_msa=768` | Success | `86.845 s` |
| Cap MSA to 1024 | `max_msa_seqs=1024`, `num_subsampled_msa=1024` | Success | `91.458 s` |
| Cap MSA to 2048 | `max_msa_seqs=2048`, `num_subsampled_msa=2048` | Success | `109.463 s` |
| Cap MSA to 3072 | `max_msa_seqs=3072`, `num_subsampled_msa=3072` | Success | `97.220 s` |
| Cap MSA to 4096 | `max_msa_seqs=4096`, `num_subsampled_msa=4096` | Success | `111.988 s` |
| Cap MSA to 5120 | `max_msa_seqs=5120`, `num_subsampled_msa=5120` | Success | `89.704 s` |
| Increase sampling | capped MSA 1024, `sampling_steps=50` | Success | `93.239 s` |
| Default sampling | capped MSA 1024, `sampling_steps=200` | Success | `106.235 s` |
| Default recycling | capped MSA 1024, `recycling_steps=3`, `sampling_steps=200` | Success | `149.053 s` |
| High recycling | capped MSA 1024, `recycling_steps=10`, `sampling_steps=200` | Success | `241.689 s` |
| Add potentials | capped MSA 1024, `recycling_steps=10`, `sampling_steps=200`, `--use_potentials` | Success | `298.748 s` |
| Two requested samples, pre-fix runtime | previous settings plus `diffusion_samples=2` | Success | `366.732 s` |

For this laptop, the first practical failure was not the 495-residue sequence length itself. It was allowing Boltz to ingest up to the default `max_msa_seqs=8192` MSA sequences. A cap of `5120` was confirmed to work for the minimal MSA test; the heavier setting ladder used `1024` as the conservative cap. Those historical measurements predate the chunking fix, so their `max_parallel_samples=1` setting did not actually serialize multiple samples. With the patched image, keep MSA capped and denoiser samples serial:

```bash
--max_msa_seqs 5120
--num_subsampled_msa 5120
--max_parallel_samples 1
```

The original heavier 20-sample setting was not run end-to-end. The patched 10-sample benchmark confirms correct denoiser serialization, but also shows that peak VRAM falls only modestly because full trajectory and guidance state remains allocated for every requested sample.
