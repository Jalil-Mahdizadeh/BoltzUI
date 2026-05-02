# Docker Hub Description

## Short Description

Boltz 2.2.1 with pre-baked model and molecule cache for no-download prediction startup.

## Overview

This image packages Boltz 2.2.1 together with the Boltz cache at `/opt/boltz-cache`, including the Boltz2 confidence checkpoint, affinity checkpoint, `mols.tar`, and extracted molecule data. It is intended for users who want reproducible local Boltz2 prediction runs without downloading model components on first use.

The image is built for NVIDIA GPU execution through Docker Desktop or a Linux Docker host with NVIDIA container support.

## Highlights

- Boltz version: `2.2.1`
- Cache path: `/opt/boltz-cache`
- Environment variable: `BOLTZ_CACHE=/opt/boltz-cache`
- Includes Boltz2 checkpoints and molecule cache
- Designed for bind-mounted workspaces at `/workspace`
- Example inputs included in the repository: `NusA_open.yaml`, `NusA_close.yaml`, and `affinity.yaml`

## Quick Start

```bash
docker run --rm -it \
  --gpus all \
  --shm-size=8g \
  -v "${PWD}:/workspace" \
  -w /workspace \
  --entrypoint /bin/bash \
  boltz:221 \
  -lc 'boltz predict NusA_open.yaml \
    --use_msa_server \
    --no_kernels \
    --cache /opt/boltz-cache \
    --diffusion_samples 20 \
    --recycling_steps 10 \
    --max_parallel_samples 1 \
    --step_scale 1.0 \
    --use_potentials \
    --output_format pdb'
```

## VRAM Note

Boltz2 inference can consume substantial GPU memory. On 8 GB GPUs, use `--max_parallel_samples 1` and reduce `--diffusion_samples` or `--recycling_steps` if CUDA runs out of memory.

## Build From Source

Place a populated `.boltz/` cache folder next to the Dockerfile, then run:

```bash
docker build -t boltz:221 .
```

The build verifies that the required cache files exist before producing the image.
