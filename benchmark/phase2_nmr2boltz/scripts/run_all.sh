#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runner="$script_dir/run_arm.sh"

worker() {
  local gpu="$1"
  shift
  local task
  local pdb_id
  local arm
  for task in "$@"; do
    pdb_id="${task%%:*}"
    arm="${task#*:}"
    echo "GPU $gpu: starting $pdb_id $arm"
    bash "$runner" "$pdb_id" "$arm" "$gpu"
    echo "GPU $gpu: completed $pdb_id $arm"
  done
}

gpu0=(
  8ivb:exact 8ivb:union 8ivb:combined
  9ezo:exact 9ezo:union 9ezo:combined
  8q5q:modified_unconstrained 8q5q:exact 8q5q:union 8q5q:combined
  9xap:exact 9xap:union 9xap:combined
  9kad:exact 9kad:combined
)

gpu1=(
  8voh:exact 8voh:union 8voh:combined
  9ezp:exact 9ezp:union 9ezp:combined
  9jo6:exact 9jo6:union 9jo6:combined
  8x8t:exact 8x8t:union 8x8t:combined
  9jvn:exact 9jvn:union 9jvn:combined
)

status=0
worker 0 "${gpu0[@]}" &
pid0=$!
worker 1 "${gpu1[@]}" &
pid1=$!
wait "$pid0" || status=1
wait "$pid1" || status=1
exit "$status"
