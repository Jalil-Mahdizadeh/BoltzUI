#!/usr/bin/env bash
set -e

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
