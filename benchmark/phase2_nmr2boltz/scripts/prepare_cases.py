#!/usr/bin/env python3
"""Create self-contained phase-2 case inputs from the immutable phase-1 cases."""

import hashlib
import json
from pathlib import Path
import shutil


PHASE2 = Path(__file__).resolve().parents[1]
BENCHMARK = PHASE2.parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def main() -> None:
    config = json.loads((PHASE2 / "config.json").read_text())
    for pdb_id in config["pdb_ids"]:
        lower = pdb_id.lower()
        phase1 = BENCHMARK / "candidates" / f"{lower}-passed"
        if not phase1.is_dir():
            raise RuntimeError(f"Missing phase-1 passed case: {phase1}")

        case = PHASE2 / "cases" / lower
        source = case / "source"
        source.mkdir(parents=True, exist_ok=True)
        files = {
            "base_yaml": phase1 / "input" / f"{lower}_unconstrained.yaml",
            "reference_pdb": phase1 / "reference" / f"{lower}.pdb",
            "nef": phase1 / "nmr_data" / f"{lower}_nmr-data.nef",
            "nmr_star": phase1 / "nmr_data" / f"{lower}_nmr-data.str",
            "candidate_json": phase1 / "candidate.json",
            "baseline_classification": phase1 / "analysis" / "classification.json",
            "baseline_all_comparisons": phase1 / "analysis" / "all_comparisons.json",
        }
        manifest_files = {}
        for label, original in files.items():
            if not original.is_file():
                raise RuntimeError(f"Missing required input: {original}")
            destination = source / original.name
            shutil.copy2(original, destination)
            manifest_files[label] = {
                "phase1_path": str(original.relative_to(BENCHMARK)),
                "phase2_path": str(destination.relative_to(PHASE2)),
                "sha256": sha256(destination),
                "bytes": destination.stat().st_size,
            }
        base_text = (source / f"{lower}_unconstrained.yaml").read_text()
        target = source / f"{lower}_target.yaml"
        if pdb_id == "8Q5Q":
            sequence_line = "      sequence: ATTTCATTTCATTTC\n"
            if sequence_line not in base_text:
                raise RuntimeError("Cannot locate the 8Q5Q sequence line")
            target_text = base_text.replace(
                sequence_line,
                sequence_line
                + "      modifications:\n"
                + "        - position: 5\n"
                + "          ccd: DNR\n",
                1,
            )
        else:
            target_text = base_text
        target.write_text(target_text)
        manifest_files["conversion_target_yaml"] = {
            "phase1_path": None,
            "phase2_path": str(target.relative_to(PHASE2)),
            "sha256": sha256(target),
            "bytes": target.stat().st_size,
        }
        write_json(
            case / "case_manifest.json",
            {
                "schema_version": 1,
                "pdb_id": pdb_id,
                "phase1_status": "passed",
                "files": manifest_files,
            },
        )
    print(f"Prepared {len(config['pdb_ids'])} phase-2 cases under {PHASE2 / 'cases'}")


if __name__ == "__main__":
    main()
