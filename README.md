# Boltz 2.2.1 Cached Docker Runner

This repository contains a small Boltz 2.2.1 Docker workflow for running predictions without downloading the Boltz cache at runtime. The Docker image bakes the cache into `/opt/boltz-cache`, and `run.sh` mounts the current folder as `/workspace`.

## Repository Contents

- `run.sh` - editable Docker run command for `NusA_open.yaml`.
- `Dockerfile` - builds a Boltz 2.2.1 image with the local `.boltz/` cache baked in.
- `requirements.txt` - Python package pin for Boltz.
- `REQUIREMENTS.md` - host, GPU, disk, and cache requirements.
- `DOCKER_HUB.md` - copy-ready Docker Hub overview text.
- `NusA_open.yaml`, `NusA_close.yaml`, `affinity.yaml` - example Boltz input files.
- `boltz_results_NusA_open/`, `boltz_results_NusA_close/` - example output folders.

## Build The Image

The build needs a local `.boltz/` folder with the downloaded Boltz2 components:

```text
.boltz/
  boltz2_aff.ckpt
  boltz2_conf.ckpt
  mols.tar
  mols/
```

Build:

```bash
docker build -t boltz:221 .
```

The `.boltz/` folder is ignored by Git, but it is intentionally included in the Docker build context so the image can be self-contained.

## Run A Prediction

Edit `run.sh` directly if you want a different input file or sampling settings, then run:

```bash
bash run.sh
```

The script uses this cache path:

```bash
--cache /opt/boltz-cache
```

That path is inside the image, so the first prediction should not download the Boltz model or molecule cache.

## CLI Options

`run.sh` intentionally keeps the command explicit so users can edit it directly.

Docker options:

- `docker run` - starts a new container from the image.
- `--rm` - removes the container after the run finishes.
- `-it` - runs interactively with a terminal attached.
- `--gpus all` - exposes all available NVIDIA GPUs to the container.
- `--shm-size=8g` - gives the container an 8 GB shared-memory segment.
- `-v "${PWD}:/workspace"` - mounts the current folder into the container.
- `-w /workspace` - runs commands from the mounted workspace.
- `--entrypoint /bin/bash` - starts Bash instead of the image default entrypoint.
- `boltz:221` - Docker image tag used for prediction.
- `-lc '...'` - asks Bash to run the quoted Boltz command.

Boltz `predict` options:

- `DATA` - input YAML/JSON/FASTA path, for example `NusA_open.yaml`. No default.
- `--out_dir PATH` - base directory where predictions are saved. Default: `./`; Boltz appends `boltz_results_<input-stem>`.
- `--cache PATH` - cache directory for model and molecule data. Default is `~/.boltz`, or `$BOLTZ_CACHE` if set. This image uses `/opt/boltz-cache`.
- `--checkpoint PATH` - optional structure checkpoint path. Default is `None`; Boltz uses the bundled/default model checkpoint.
- `--devices INTEGER` - number of devices to use. Default: `1`.
- `--accelerator [gpu|cpu|tpu]` - accelerator backend. Default: `gpu`.
- `--recycling_steps INTEGER` - number of recycling iterations. Default: `3`; `run.sh` uses `10`.
- `--sampling_steps INTEGER` - number of diffusion sampling steps. Default: `200`.
- `--diffusion_samples INTEGER` - number of generated structure samples. Default: `1`; `run.sh` uses `20`.
- `--max_parallel_samples INTEGER` - maximum samples predicted in parallel. Default: `None`; `run.sh` uses `1` to reduce VRAM pressure.
- `--step_scale FLOAT` - diffusion step scale. Default: `1.638` for Boltz-1 and `1.5` for Boltz-2; `run.sh` uses `1.0`.
- `--write_full_pae` - writes full PAE as an NPZ file. Default: `True`.
- `--write_full_pde` - writes full PDE as an NPZ file. Default: `False`.
- `--output_format [pdb|mmcif]` - structure output format. Default: `mmcif`; `run.sh` uses `pdb`.
- `--num_workers INTEGER` - dataloader worker count. Default: `2`.
- `--override` - overwrites existing predictions. Default: `False`.
- `--seed INTEGER` - random seed. Default: `None`.
- `--use_msa_server` - generates missing protein MSAs through the MMSeqs2 server. Default: `False`; `run.sh` enables it.
- `--msa_server_url TEXT` - MSA server URL, used with `--use_msa_server`. Default: `https://api.colabfold.com`.
- `--msa_pairing_strategy TEXT` - MSA pairing strategy, `greedy` or `complete`, used with `--use_msa_server`. Default: `greedy`.
- `--msa_server_username TEXT` - username for MSA server basic auth. Default: `None`; can also use `$BOLTZ_MSA_USERNAME`.
- `--msa_server_password TEXT` - password for MSA server basic auth. Default: `None`; can also use `$BOLTZ_MSA_PASSWORD`.
- `--api_key_header TEXT` - custom API-key header name. Option default: `None`; when API-key auth is used and no header is provided, Boltz uses `X-API-Key`.
- `--api_key_value TEXT` - custom API-key header value. Default: `None`.
- `--use_potentials` - enables steering potentials. Default: `False`; `run.sh` enables it.
- `--model [boltz1|boltz2]` - model family. Default: `boltz2`.
- `--method TEXT` - method metadata/conditioning value. Default: `None`.
- `--preprocessing-threads INTEGER` - preprocessing thread count. Default: `1`.
- `--affinity_mw_correction` - enables molecular-weight correction for affinity prediction. Default: `False`.
- `--sampling_steps_affinity INTEGER` - affinity sampling steps. Default: `200`.
- `--diffusion_samples_affinity INTEGER` - affinity diffusion samples. Default: `5`.
- `--affinity_checkpoint PATH` - optional affinity checkpoint path. Default: `None`; Boltz uses the bundled/default affinity checkpoint.
- `--max_msa_seqs INTEGER` - maximum MSA sequences used. Default: `8192`.
- `--subsample_msa` - subsamples MSA sequences. Default: `True`.
- `--num_subsampled_msa INTEGER` - number of MSA sequences after subsampling. Default: `1024`.
- `--no_kernels` - disables optional optimized kernels. Default: `False`; `run.sh` enables it for compatibility.
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

For a very conservative first test, edit `run.sh` to:

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

For this laptop, treat `700 aa` as the largest confirmed working length for minimal GPU testing. This is not a general production limit: real inputs with MSAs, higher `sampling_steps`, more `diffusion_samples`, more `recycling_steps`, `--use_potentials`, or parallel sampling can require substantially more VRAM. The default `run.sh` settings are much heavier than this benchmark.

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
