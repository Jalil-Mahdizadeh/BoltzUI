# Docker Hub Description

## Short Description

BoltzUI web app for Boltz 2.2.1 with a pre-baked model and molecule cache.

## Overview

This image packages the BoltzUI web interface on top of a cached Boltz 2.2.1 runtime image. It is intended for users who want a local browser UI that starts predictions inside the same Docker container without downloading model components on first use.

The image is built for NVIDIA GPU execution through Docker Desktop or a Linux Docker host with NVIDIA container support.

## Highlights

- Boltz version: `2.2.1`
- Cache path: `/opt/boltz-cache`
- Environment variable: `BOLTZ_CACHE=/opt/boltz-cache`
- Includes Boltz2 checkpoints and molecule cache
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
  boltzui:221
```

Open `http://localhost:5173`.

## VRAM Note

Boltz2 inference can consume substantial GPU memory. On 8 GB GPUs, use `--max_parallel_samples 1` and reduce `--diffusion_samples` or `--recycling_steps` if CUDA runs out of memory.

## Build From Source

Make sure the cached `boltz:221` base image exists locally, then run:

```bash
docker build -t boltzui:221 .
```

The build verifies that `boltz` and `node` are available before producing the image.
