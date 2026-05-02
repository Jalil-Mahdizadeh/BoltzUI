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