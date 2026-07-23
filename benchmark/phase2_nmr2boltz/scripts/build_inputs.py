#!/usr/bin/env python3
"""Build matched Boltz inputs, commands, and per-arm provenance."""

import hashlib
import json
from pathlib import Path
import shlex
import shutil

import yaml


PHASE2 = Path(__file__).resolve().parents[1]
BENCHMARK = PHASE2.parent
REPO = BENCHMARK.parent


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def load_yaml(path):
    with path.open("r") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise RuntimeError("Expected YAML mapping in {}".format(path))
    return value


def dump_yaml(path, value, header):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(value, default_flow_style=False)
    path.write_text("# {}\n{}".format(header, body))


def container_path(path):
    return "/workspace/BoltzUI/{}".format(path.resolve().relative_to(REPO))


def attach_fixed_msas(document, case, pdb_id):
    """Use the exact phase-1 raw MSAs to isolate the constraint treatment."""
    phase1_msa = (
        BENCHMARK
        / "candidates"
        / "{}-passed".format(pdb_id)
        / "results"
        / "boltz_results_{}_unconstrained".format(pdb_id)
        / "msa"
    )
    csv_files = sorted(phase1_msa.glob("*_*.csv"))
    protein_entries = [
        item["protein"]
        for item in document.get("sequences", [])
        if isinstance(item, dict) and isinstance(item.get("protein"), dict)
    ]
    if len(csv_files) != len(protein_entries):
        if protein_entries:
            raise RuntimeError(
                "{} has {} protein entities but {} baseline MSAs".format(
                    pdb_id, len(protein_entries), len(csv_files)
                )
            )
        return []
    destination_dir = case / "source" / "msa"
    destination_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for index, (entry, source) in enumerate(zip(protein_entries, csv_files)):
        destination = destination_dir / "entity_{}.csv".format(index)
        shutil.copy2(str(source), str(destination))
        entry["msa"] = container_path(destination)
        records.append(
            {
                "entity_index": index,
                "source": str(source.relative_to(BENCHMARK)),
                "file": str(destination.relative_to(PHASE2)),
                "sha256": sha256(destination),
                "bytes": destination.stat().st_size,
            }
        )
    return records


def main():
    config = json.loads((PHASE2 / "config.json").read_text())
    arguments = config["prediction"]["arguments"]
    arms = config["prediction"]["arms"]

    for pdb_upper in config["pdb_ids"]:
        pdb_id = pdb_upper.lower()
        case = PHASE2 / "cases" / pdb_id
        target = load_yaml(case / "source" / "{}_target.yaml".format(pdb_id))
        msa_records = attach_fixed_msas(target, case, pdb_id)
        exact = load_yaml(case / "conversion" / "nef" / "atom_constraints_exact.yaml")
        union = load_yaml(case / "conversion" / "nef" / "atom_constraints_union.yaml")
        exact_constraints = exact.get("constraints") or []
        union_constraints = union.get("constraints") or []
        arm_constraints = {
            "exact": exact_constraints,
            "union": union_constraints,
            "combined": exact_constraints + union_constraints,
        }

        build_summary = {
            "schema_version": 1,
            "pdb_id": pdb_upper,
            "fixed_phase1_msas": msa_records,
            "exact_constraint_count": len(exact_constraints),
            "union_group_count": len(union_constraints),
            "arms": {},
        }

        for arm in arms:
            arm_dir = case / arm
            input_path = arm_dir / "input" / "{}_{}.yaml".format(pdb_id, arm)
            document = dict(target)
            document["constraints"] = arm_constraints[arm]
            dump_yaml(
                input_path,
                document,
                "{} {} constraints generated from deposited NEF by nmr2boltz".format(
                    pdb_upper, arm
                ),
            )
            applicable = bool(arm_constraints[arm])
            result_base = arm_dir / "results"
            command = [
                "boltz",
                "predict",
                container_path(input_path),
                "--out_dir",
                container_path(result_base),
                "--cache",
                "/opt/boltz-cache",
            ] + arguments
            command_record = {
                "executable": command[0],
                "arguments": command[1:],
                "display": " ".join(shlex.quote(value) for value in command),
            }
            if applicable:
                write_json(arm_dir / "command.json", command_record)
                (arm_dir / "command.txt").write_text(command_record["display"] + "\n")
            write_json(
                arm_dir / "arm_manifest.json",
                {
                    "schema_version": 1,
                    "pdb_id": pdb_upper,
                    "arm": arm,
                    "applicable": applicable,
                    "input_file": str(input_path.relative_to(PHASE2)),
                    "input_sha256": sha256(input_path),
                    "exact_constraints": (
                        len(exact_constraints) if arm in ("exact", "combined") else 0
                    ),
                    "union_groups": (
                        len(union_constraints) if arm in ("union", "combined") else 0
                    ),
                    "fixed_phase1_msas": msa_records,
                    "command": command_record if applicable else None,
                },
            )
            build_summary["arms"][arm] = {
                "applicable": applicable,
                "input": str(input_path.relative_to(PHASE2)),
                "exact_constraints": (
                    len(exact_constraints) if arm in ("exact", "combined") else 0
                ),
                "union_groups": (
                    len(union_constraints) if arm in ("union", "combined") else 0
                ),
            }

        if pdb_upper == "8Q5Q":
            arm = "modified_unconstrained"
            arm_dir = case / arm
            input_path = arm_dir / "input" / "{}_{}.yaml".format(pdb_id, arm)
            document = dict(target)
            document.pop("constraints", None)
            dump_yaml(
                input_path,
                document,
                "8Q5Q DNR-matched unconstrained control",
            )
            result_base = arm_dir / "results"
            command = [
                "boltz",
                "predict",
                container_path(input_path),
                "--out_dir",
                container_path(result_base),
                "--cache",
                "/opt/boltz-cache",
            ] + arguments
            command_record = {
                "executable": command[0],
                "arguments": command[1:],
                "display": " ".join(shlex.quote(value) for value in command),
            }
            write_json(arm_dir / "command.json", command_record)
            (arm_dir / "command.txt").write_text(command_record["display"] + "\n")
            write_json(
                arm_dir / "arm_manifest.json",
                {
                    "schema_version": 1,
                    "pdb_id": pdb_upper,
                    "arm": arm,
                    "applicable": True,
                    "input_file": str(input_path.relative_to(PHASE2)),
                    "input_sha256": sha256(input_path),
                    "exact_constraints": 0,
                    "union_groups": 0,
                    "fixed_phase1_msas": [],
                    "command": command_record,
                    "reason": "Matched control for the DNR modification required by target validation.",
                },
            )
            build_summary["arms"][arm] = {
                "applicable": True,
                "input": str(input_path.relative_to(PHASE2)),
                "exact_constraints": 0,
                "union_groups": 0,
            }
        write_json(case / "build_summary.json", build_summary)

    print("Built matched inputs and commands for {} cases".format(len(config["pdb_ids"])))


if __name__ == "__main__":
    main()
