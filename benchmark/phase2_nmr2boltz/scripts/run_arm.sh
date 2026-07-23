#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 PDB_ID ARM GPU_INDEX" >&2
  exit 2
fi

pdb_id="${1,,}"
arm="$2"
gpu_index="$3"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
phase2_dir="$(dirname "$script_dir")"
benchmark_dir="$(dirname "$phase2_dir")"
repo_dir="$(dirname "$benchmark_dir")"
case_dir="$phase2_dir/cases/$pdb_id"
arm_dir="$case_dir/$arm"
sif="/cephyr/users/sayyed/Alvis/Desktop/mimer_theo-storage/Jalil/Images/boltzui-221-exact-union.sif"

command_json="$arm_dir/command.json"
log_dir="$arm_dir/logs"
log_file="$log_dir/boltz.log"
status_file="$log_dir/execution_status.json"

if [[ ! -f "$command_json" ]]; then
  echo "Missing or non-applicable arm command: $command_json" >&2
  exit 2
fi
mkdir -p "$log_dir"

result_host="$arm_dir/results/boltz_results_${pdb_id}_${arm}"
if [[ "${FORCE_RERUN:-0}" != "1" && -f "$status_file" ]]; then
  completed_models="$(find "$result_host" -type f -name '*_model_*.pdb' 2>/dev/null | wc -l)"
  audit_ready=1
  if [[ "$arm" != "modified_unconstrained" && ! -f "$result_host/atom_contact_restraints.json" ]]; then
    audit_ready=0
  fi
  if jq -e '.exit_code == 0' "$status_file" >/dev/null 2>&1 \
    && [[ "$completed_models" -eq 10 ]] \
    && [[ "$audit_ready" -eq 1 ]]; then
    echo "Already complete: $pdb_id $arm"
    exit 0
  fi
fi

mapfile -t boltz_args < <(
  apptainer exec \
    --bind "$repo_dir:/workspace/BoltzUI" \
    --pwd /workspace/BoltzUI \
    "$sif" \
    node -e '
      const command = require(process.argv[1]);
      for (const value of command.arguments) process.stdout.write(`${value}\n`);
    ' "/workspace/BoltzUI/benchmark/phase2_nmr2boltz/cases/$pdb_id/$arm/command.json"
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

audit_exit_code=null
if [[ "$exit_code" -eq 0 && "$arm" != "modified_unconstrained" ]]; then
  input="/host/BoltzUI/benchmark/phase2_nmr2boltz/cases/$pdb_id/$arm/input/${pdb_id}_${arm}.yaml"
  result="/host/BoltzUI/benchmark/phase2_nmr2boltz/cases/$pdb_id/$arm/results/boltz_results_${pdb_id}_${arm}"
  set +e
  apptainer exec \
    --bind "$repo_dir:/host/BoltzUI" \
    --pwd /workspace/BoltzUI \
    "$sif" \
    node /host/BoltzUI/benchmark/phase2_nmr2boltz/scripts/restraint_audit.js \
    "$input" "$result" 2>&1 | tee "$log_dir/restraint_audit.log"
  audit_exit_code="${PIPESTATUS[0]}"
  set -e
  if [[ "$audit_exit_code" -ne 0 ]]; then
    exit_code="$audit_exit_code"
  fi
fi

ended_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '{"started_at":"%s","ended_at":"%s","gpu_index":%s,"exit_code":%s,"restraint_audit_exit_code":%s}\n' \
  "$started_at" "$ended_at" "$gpu_index" "$exit_code" "$audit_exit_code" > "$status_file"
exit "$exit_code"
