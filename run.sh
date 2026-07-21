#!/usr/bin/env bash
set -e

docker run --rm \
  --gpus all \
  --shm-size=8g \
  -p 5173:5173 \
  -v "${PWD}:/workspace/BoltzUI" \
  -w /workspace/BoltzUI \
  boltzui:221-exact-union
