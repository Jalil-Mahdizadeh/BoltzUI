# Docker Hub Description

## Short Description

BoltzUI web app for Boltz 2.2.1 with a pre-baked model cache and exact atom_contact constraints.

## Overview

This image packages the BoltzUI web interface on top of a cached Boltz 2.2.1 runtime image. It includes a reproducible Boltz runtime patch for Boltz2-only `atom_contact` constraints, allowing exact non-covalent atom-atom distance guidance through the existing contact potential path.

The image is built for NVIDIA GPU execution through Docker Desktop or a Linux Docker host with NVIDIA container support.

## Highlights

- Boltz version: `2.2.1`
- Cache path: `/opt/boltz-cache`
- Environment variable: `BOLTZ_CACHE=/opt/boltz-cache`
- Includes Boltz2 checkpoints and molecule cache
- Adds `atom_contact` YAML constraints for exact atom-atom contact guidance
- `atom_contact` requires `force: true`, `--use_potentials`, and `max_distance` in `2.0-20.0` Angstrom
- The UI defaults to `--sampling_steps 400` and `--step_scale 1.0` because those settings improved atom-contact satisfaction in local benchmarks
- `--use_potentials` stays off by default for general tasks, but the server blocks `atom_contact` inputs unless it is enabled
- MSA defaults match upstream Boltz: `max_msa_seqs=8192`, `subsample_msa=true`, and `num_subsampled_msa=1024`
- Starts the BoltzUI web server on port `5173`
- Designed for bind-mounted workspaces at `/workspace/BoltzUI`
- Full `boltz predict` option sidebar with collapsed sections by default
- MSA server enabled by default, with server, credential, and limit controls grouped under MSA settings
- Collapsible generated command, run history, and live log panels
- Embedded 3D structure preview with confidence color legend
- Inputs are saved under `workspace/inputs/` and prediction folders are written under `workspace/results/`
- Example inputs included in the repository under `workspace/inputs/`

## Quick Start

```bash
docker run --rm \
  --gpus all \
  --shm-size=8g \
  -p 5173:5173 \
  -v "${PWD}:/workspace/BoltzUI" \
  -w /workspace/BoltzUI \
  boltzui:221-atomcontact
```

Open `http://localhost:5173`.

## VRAM Note

Boltz2 inference can consume substantial GPU memory. On 8 GB GPUs, use `--max_parallel_samples 1` and reduce `--diffusion_samples` or `--recycling_steps` if CUDA runs out of memory.

## Build From Source

Make sure the local `boltzui:221` base image exists, then run:

```bash
docker build -t boltzui:221-atomcontact .
```

The build applies and compiles the Boltz atom-contact patch, then verifies that `boltz` and `node` are available before producing the image.
