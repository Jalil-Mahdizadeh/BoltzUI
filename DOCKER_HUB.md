# Docker Hub Description

## Short Description

BoltzUI web app for Boltz 2.2.1 with exact and ambiguous union atom-pair guidance and bounded denoiser sample batches.

## Overview

This image packages the BoltzUI web interface on top of a cached Boltz 2.2.1 runtime image. Its reproducible runtime patch adds Boltz2-only exact `atom_contact` and OR-grouped `atom_contact_union` restraints and corrects `max_parallel_samples` so it limits each denoiser call.

The image is built for NVIDIA GPU execution through Docker Desktop or a Linux Docker host with NVIDIA container support.

## Highlights

- Boltz version: `2.2.1`
- Cache path: `/opt/boltz-cache`
- Environment variable: `BOLTZ_CACHE=/opt/boltz-cache`
- Includes Boltz2 checkpoints and molecule cache
- Adds exact `atom_contact` and ambiguous `atom_contact_union` YAML restraints
- Keeps one potential union index per OR group and excludes union alternatives from binary token-contact conditioning
- YAML Builder fields can directly load nmr2boltz `atom_constraints_exact.yaml` and `atom_constraints_union.yaml`
- Corrects Boltz 2.2.1 diffusion chunking so `max_parallel_samples` is a true denoiser batch limit
- Exact and union atom contacts require `force: true` and per-pair `max_distance` in `2.0-20.0` Angstrom; additional FK/physical potentials are optional and enabled by default in the experimental preset
- Exact pairs and union-group alternatives are measured after prediction, summarized per model, and reported separately from confidence; large audits show violations first while retaining every measurement in JSON
- MSA defaults match upstream Boltz: `max_msa_seqs=8192`, `subsample_msa=true`, and `num_subsampled_msa=1024`
- Starts the BoltzUI web server on port `5173`
- Designed for bind-mounted workspaces at `/workspace/BoltzUI`
- Full `boltz predict` option sidebar with collapsed sections by default
- MSA server enabled by default, with server, credential, and limit controls grouped under MSA settings
- Collapsible generated command, run history, and live log panels
- Embedded 3D structure preview with confidence color legend
- Inputs are saved under `workspace/inputs/` and prediction folders are written under `workspace/results/`
- Example inputs included in the repository under `workspace/inputs/`

## Prediction Presets

<!-- BEGIN GENERATED PREDICTION PRESETS -->
| Preset | Sampling steps | Step scale | Potentials | Status |
|---|---:|---:|---|---|
| Standard Boltz-2 | 200 | 1.5 | Off | Standard |
| Atom-contact exploration | 400 | 1.0 | On | Experimental |

The atom-contact exploration preset is experimental. Its lower step scale changes the reverse-diffusion update and sample diversity and may interact with inference-time potential guidance; it is not a mathematical guarantee of restraint satisfaction.
<!-- END GENERATED PREDICTION PRESETS -->

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

Boltz2 inference can consume substantial GPU memory. On 8 GB GPUs, use `--max_parallel_samples 1` and reduce `--diffusion_samples` or `--recycling_steps` if CUDA runs out of memory. Denoiser activations are chunked, but trajectory and guidance state still scale with the total diffusion sample count.

## Build From Source

Make sure the local `boltzui:221` base image exists, then run:

```bash
docker build -t boltzui:221-atomcontact .
```

The build applies and compiles the exact/union Boltz atom-contact and diffusion-chunking patch, runs compatibility tests, then verifies that `boltz` and `node` are available.
