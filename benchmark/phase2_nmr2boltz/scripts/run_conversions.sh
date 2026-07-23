#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
phase2_dir="$(dirname "$script_dir")"
benchmark_dir="$(dirname "$phase2_dir")"
repo_dir="$(dirname "$benchmark_dir")"
sif="/mimer/NOBACKUP/groups/theo-storage/Jalil/Images/nmr2boltz.sif"

if [[ $# -gt 0 ]]; then
  ids=("$@")
else
  ids=(9xap 9jo6 9ezo 9ezp 8voh 8ivb 9kad 8q5q 9jvn 8x8t)
fi

for id in "${ids[@]}"; do
  case_dir="$phase2_dir/cases/$id"
  target="/workspace/BoltzUI/benchmark/phase2_nmr2boltz/cases/$id/source/${id}_target.yaml"
  for format in nef nmr_star; do
    if [[ "$format" == "nef" ]]; then
      extension="nef"
      format_flag="nef"
    else
      extension="str"
      format_flag="nmr-star"
    fi
    input="/workspace/BoltzUI/benchmark/phase2_nmr2boltz/cases/$id/source/${id}_nmr-data.$extension"
    output="/workspace/BoltzUI/benchmark/phase2_nmr2boltz/cases/$id/conversion/$format"
    log="$case_dir/conversion/${format}.log"
    ccd_args=()
    if [[ "$id" == "8q5q" ]]; then
      ccd_args=(--ccd /workspace/BoltzUI/benchmark/phase2_nmr2boltz/cases/8q5q/source/DNR.cif)
    fi
    mkdir -p "$(dirname "$log")"
    echo "Converting $id $format_flag"
    apptainer exec \
      --bind "$repo_dir:/workspace/BoltzUI" \
      --pwd /workspace/BoltzUI \
      "$sif" \
      nmr2boltz convert "$input" \
      --format "$format_flag" \
      --target-yaml "$target" \
      "${ccd_args[@]}" \
      -o "$output" 2>&1 | tee "$log"
  done
done
