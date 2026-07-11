# BoltzUI

BoltzUI is a Dockerized web app for Boltz 2.2.1. The Docker image starts the web interface, exposes it on port `5173`, and runs `boltz predict` inside the same container. This patched build is layered on the local `boltzui:221` image and adds a reproducible Boltz2-only `atom_contact` runtime patch for specific atom-pair distance guidance.

## Repository Contents

- `Dockerfile` - builds the patched BoltzUI web app image on top of the local `boltzui:221` image.
- `patches/boltz_atom_contact/` - reproducible Boltz runtime patch applied during Docker build.
- `server.js`, `public/`, `package.json` - BoltzUI web interface for configuring, launching, and inspecting Boltz runs.
- `run.sh` - optional launcher for the BoltzUI container.
- `requirements.txt` - Python package pin for Boltz.
- `REQUIREMENTS.md` - host, GPU, disk, and cache requirements.
- `DOCKER_HUB.md` - copy-ready Docker Hub overview text.
- `workspace/inputs/` - Boltz YAML/JSON/FASTA inputs. Example inputs live here.
- `workspace/results/` - default Boltz output directory. Boltz creates `boltz_results_<input-stem>/` folders here.

## Build The Image

The atom-contact build expects the patched base workflow image to already exist locally:

```bash
docker image inspect boltzui:221 >/dev/null
```

Build:

```bash
docker build -t boltzui:221-atomcontact .
```

The final `boltzui:221-atomcontact` image contains the Boltz runtime from `boltzui:221`, Node.js, the BoltzUI web app, and the `atom_contact` Boltz runtime patch.

## Run The Web UI

Run the container:

```bash
docker run --rm --gpus all \
  --shm-size=8g \
  -p 5173:5173 \
  -v "$(pwd):/workspace/BoltzUI" \
  -w /workspace/BoltzUI \
  boltzui:221-atomcontact
```

PowerShell equivalent:

```powershell
docker run --rm --gpus all --shm-size=8g `
  -p 5173:5173 `
  -v "${PWD}:/workspace/BoltzUI" `
  -w /workspace/BoltzUI `
  boltzui:221-atomcontact
```

Then open:

```text
http://localhost:5173
```

After building the image, `bash run.sh` runs the same container command on Unix-like shells.

BoltzUI exposes every `boltz predict` option from the installed 2.2.1 CLI, builds a command preview, launches jobs with collapsible live logs, summarizes existing `workspace/results/boltz_results_*` folders, and opens generated PDB structures in an embedded 3Dmol workspace. Inputs and results are kept under `workspace/` by default so the repository root stays clear.

The sidebar is collapsed by section by default. `Input` selects the prediction file, `Settings` contains the full flag set, and `MSA settings` groups MSA server, credential, and limit controls under one section. The structure preview includes a 0-100 confidence color legend whenever the viewer color mode is set to `Confidence`.

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

The dedicated YAML Builder page at `http://localhost:5173/builder.html` is the primary authoring surface for Boltz input files and is available from the distinctive `YAML Builder` button at the top of the sidebar. It provides schema-guided templates for structure, multimer, protein-ligand, affinity, pocket constraints, token contact constraints, atom contact constraints, and template-based predictions, then writes ordinary `.yaml` files into `workspace/inputs/`.

The builder covers Boltz YAML features that are not available in FASTA: any number of protein/DNA/RNA polymers, multiple identical chain IDs, automatic/custom/empty protein MSA modes, cyclic polymers, modified residues, any number of ligands by SMILES or CCD code, pocket constraints, repeatable token-level contact constraints with individual max distances, repeatable atom-pair upper-distance restraints, repeatable covalent bond constraints, structural templates, and the Boltz-2 affinity property. Affinity runs still need a single ligand copy as the binder. The generated YAML remains editable before saving.

### Constraint Types

- `contact` is the existing token-level proximity constraint. For protein/RNA/DNA polymers, a token is a residue or nucleotide selected by `[CHAIN_ID, RES_IDX]`; for ligands/non-polymers, a token is an atom selected by `[CHAIN_ID, ATOM_NAME]`.
- `pocket` keeps the existing binder/contact behavior unchanged.
- `bond` is the existing covalent atom-level bond constraint using `[CHAIN_ID, RES_IDX, ATOM_NAME]`.
- `atom_contact` is a patched Boltz2-only atom-pair upper-distance restraint using `[CHAIN_ID, RES_IDX, ATOM_NAME]`.

`atom_contact` requires `force: true`, prediction with `--use_potentials`, and `max_distance` in the `2.0-20.0` Angstrom range. It contributes token-level contact conditioning for the containing tokens and one exact atom-index pair to the soft inference-time contact potential. This does not mathematically guarantee the final distance. The experimental Atom-contact exploration preset changes the reverse-diffusion sampling schedule; final satisfaction must be checked in `atom_contact_restraints.json`.

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

### Run Provenance And Restraint Audit

Every completed, stopped, or failed submitted process writes `boltzui_run.json` into its `workspace/results/boltz_results_<input-stem>/` directory. It records the Git commit when available, Boltz version, selected preset, resolved parameters, credential-free command arguments, input SHA-256, MSA configuration, timestamps, exit status, and submitted atom-contact restraints.

Atom-contact runs also write `atom_contact_restraints.json` in the same directory. The report measures every requested atom pair in every generated PDB or mmCIF structure and records observed distance, excess above the requested maximum, satisfaction, or an explicit unresolved endpoint. The result viewer exposes both JSON files and shows a compact restraint table separately from Boltz confidence metrics.

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
- `--max_parallel_samples INTEGER` - maximum samples predicted in parallel. Default: `None`.
- `--step_scale FLOAT` - reverse-diffusion step scale. Determined by the selected preset; changing it affects reverse-diffusion updates and sample diversity and can interact with potential guidance.
- `--write_full_pae` - writes full PAE as an NPZ file. Default: `True`.
- `--write_full_pde` - writes full PDE as an NPZ file. Default: `False`.
- `--output_format [pdb|mmcif]` - structure output format. BoltzUI default: `pdb`.
- `--num_workers INTEGER` - dataloader worker count. BoltzUI default: `0`.
- `--override` - overwrites existing predictions. Default: `False`.
- `--seed INTEGER` - random seed. BoltzUI default: `1`; use `-1` for a random seed.
- `--use_msa_server` - generates missing protein MSAs through the MMSeqs2 server. BoltzUI default: `True`.
- `--msa_server_url TEXT` - MSA server URL, used with `--use_msa_server`. Default: `https://api.colabfold.com`.
- `--msa_pairing_strategy TEXT` - MSA pairing strategy, `greedy` or `complete`, used with `--use_msa_server`. Default: `greedy`.
- `--msa_server_username TEXT` - username for MSA server basic auth. Default: `None`; can also use `$BOLTZ_MSA_USERNAME`.
- `--msa_server_password TEXT` - password for MSA server basic auth. Default: `None`; can also use `$BOLTZ_MSA_PASSWORD`.
- `--api_key_header TEXT` - custom API-key header name. Option default: `None`; when API-key auth is used and no header is provided, Boltz uses `X-API-Key`.
- `--api_key_value TEXT` - custom API-key header value. Default: `None`.
- `--use_potentials` - enables soft inference-time steering potentials. Required for `atom_contact`; enabled by the experimental Atom-contact exploration preset.
- `--model [boltz1|boltz2]` - model family. Default: `boltz2`.
- `--method TEXT` - method metadata/conditioning value. Default: `None`.
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
| Two serial samples | previous settings plus `diffusion_samples=2` | Success | `366.732 s` |

For this laptop, the first practical failure was not the 495-residue sequence length itself. It was allowing Boltz to ingest up to the default `max_msa_seqs=8192` MSA sequences. A cap of `5120` was confirmed to work for the minimal MSA test; the heavier setting ladder below used `1024` as the conservative cap. For NusA on this 8 GB GPU, keep MSA capped and samples serial:

```bash
--max_msa_seqs 5120
--num_subsampled_msa 5120
--max_parallel_samples 1
```

The original heavier 20-sample setting was not run end-to-end. With `max_parallel_samples=1`, additional diffusion samples are expected to increase runtime substantially while keeping peak VRAM closer to the one-sample case, but this was only verified up to `diffusion_samples=2`.
