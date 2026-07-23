#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
benchmark_dir="$(dirname "$script_dir")"
repo_dir="$(dirname "$benchmark_dir")"
summary_dir="$benchmark_dir/summary"
sif="/cephyr/users/sayyed/Alvis/Desktop/mimer_theo-storage/Jalil/Images/boltzui-221-exact-union.sif"
output="$summary_dir/environment.txt"
temporary="$output.tmp"

mkdir -p "$summary_dir"
{
  echo "captured_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "repository=$repo_dir"
  echo "repository_commit=$(git -C "$repo_dir" rev-parse HEAD)"
  echo "hostname=$(hostname)"
  echo "kernel=$(uname -srmo)"
  echo "apptainer_version=$(apptainer version)"
  echo "sif=$sif"
  stat --printf='sif_bytes=%s\nsif_mtime=%y\n' "$sif"
  echo "sif_sha256=$(sha256sum "$sif" | cut -d ' ' -f 1)"
  apptainer exec "$sif" python -c '
import importlib.metadata as metadata
import numpy
import torch
print("boltz_version=" + metadata.version("boltz"))
print("python_version=" + __import__("platform").python_version())
print("torch_version=" + torch.__version__)
print("numpy_version=" + numpy.__version__)
print("torch_cuda_version=" + str(torch.version.cuda))
'
  nvidia-smi --query-gpu=index,name,uuid,memory.total,driver_version \
    --format=csv,noheader
} > "$temporary"
mv "$temporary" "$output"
sha256sum "$output" > "$summary_dir/environment.txt.sha256"
printf '%s\n' "$output"
