#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 CANDIDATE_DIRECTORY GPU_INDEX" >&2
  exit 2
fi

candidate_dir="$(realpath "$1")"
gpu_index="$2"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
benchmark_dir="$(dirname "$script_dir")"
repo_dir="$(dirname "$benchmark_dir")"
sif="/cephyr/users/sayyed/Alvis/Desktop/mimer_theo-storage/Jalil/Images/boltzui-221-exact-union.sif"

case "$candidate_dir" in
  "$benchmark_dir"/candidates/*) ;;
  *)
    echo "Candidate must be under $benchmark_dir/candidates" >&2
    exit 2
    ;;
esac

command_json="$candidate_dir/command.json"
log_file="$candidate_dir/logs/boltz.log"
status_file="$candidate_dir/logs/execution_status.json"
if [[ ! -f "$command_json" ]]; then
  echo "Missing $command_json" >&2
  exit 2
fi

mapfile -t boltz_args < <(
  apptainer exec \
    --bind "$repo_dir:/workspace/BoltzUI" \
    --pwd /workspace/BoltzUI \
    "$sif" \
    node -e '
      const command = require(process.argv[1]);
      for (const value of command.arguments) process.stdout.write(`${value}\n`);
    ' "$command_json"
)

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set +e
apptainer exec \
  --nv \
  --env "CUDA_VISIBLE_DEVICES=$gpu_index" \
  --bind "$repo_dir:/workspace/BoltzUI" \
  --pwd /workspace/BoltzUI \
  "$sif" \
  boltz "${boltz_args[@]}" 2>&1 | tee "$log_file"
exit_code="${PIPESTATUS[0]}"
set -e
ended_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

printf '{"started_at":"%s","ended_at":"%s","gpu_index":%s,"exit_code":%s}\n' \
  "$started_at" "$ended_at" "$gpu_index" "$exit_code" > "$status_file"
exit "$exit_code"

