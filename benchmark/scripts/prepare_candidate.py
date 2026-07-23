#!/usr/bin/env python3
"""Create a self-contained candidate directory and unconstrained Boltz YAML."""

from __future__ import print_function

import argparse
import datetime
import glob
import json
import os
import shutil


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BENCHMARK_DIR = os.path.dirname(SCRIPT_DIR)
REPO_DIR = os.path.dirname(BENCHMARK_DIR)
QUEUE_PATH = os.path.join(BENCHMARK_DIR, "screening", "candidate_queue.json")
CONFIG_PATH = os.path.join(BENCHMARK_DIR, "config.json")
CANDIDATES_DIR = os.path.join(BENCHMARK_DIR, "candidates")


def load_json(path):
    with open(path, "r") as handle:
        return json.load(handle)


def write_json(path, value):
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.rename(temporary, path)


def utc_now():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def yaml_type(polymer_type):
    values = {
        "polypeptide(L)": "protein",
        "polyribonucleotide": "rna",
        "polydeoxyribonucleotide": "dna"
    }
    if polymer_type not in values:
        raise ValueError("Unsupported Boltz polymer type: {}".format(polymer_type))
    return values[polymer_type]


def generate_yaml(candidate):
    grouped = []
    by_entity = {}
    for chain in candidate["chains"]:
        entity_id = chain["entity_id"]
        if entity_id not in by_entity:
            record = {
                "entity_id": entity_id,
                "polymer_type": chain["polymer_type"],
                "sequence": chain["sequence"],
                "ids": []
            }
            by_entity[entity_id] = record
            grouped.append(record)
        by_entity[entity_id]["ids"].append(chain["auth_asym_id"])

    lines = [
        "# Unconstrained sequence-only input for PDB {}".format(candidate["pdb_id"]),
        "# Generated reproducibly by benchmark/scripts/prepare_candidate.py",
        "version: 1",
        "sequences:"
    ]
    for record in grouped:
        kind = yaml_type(record["polymer_type"])
        ids = record["ids"]
        id_value = ids[0] if len(ids) == 1 else "[{}]".format(", ".join(ids))
        lines.extend([
            "  - {}:".format(kind),
            "      id: {}".format(id_value),
            "      sequence: {}".format(record["sequence"])
        ])
    return "\n".join(lines) + "\n"


def existing_candidate_directory(pdb_id):
    matches = sorted(glob.glob(os.path.join(CANDIDATES_DIR, pdb_id.lower() + "-*")))
    return matches[0] if matches else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdb_id", help="PDB accession in candidate_queue.json")
    args = parser.parse_args()
    pdb_id = args.pdb_id.upper()
    config = load_json(CONFIG_PATH)
    queue = load_json(QUEUE_PATH)
    candidate = next(
        (item for item in queue if item["pdb_id"].upper() == pdb_id), None
    )
    if candidate is None:
        raise SystemExit("{} is not in the coordinate-screened queue.".format(pdb_id))

    existing = existing_candidate_directory(pdb_id)
    if existing:
        print(existing)
        return

    target = os.path.join(CANDIDATES_DIR, pdb_id.lower() + "-running")
    for name in ("input", "reference", "metadata", "results", "logs", "analysis"):
        os.makedirs(os.path.join(target, name))

    reference_source = os.path.join(BENCHMARK_DIR, candidate["coordinate_file"])
    reference_target = os.path.join(
        target, "reference", "{}.pdb".format(pdb_id.lower())
    )
    shutil.copy2(reference_source, reference_target)

    metadata_source = os.path.join(
        BENCHMARK_DIR, candidate["metadata_directory"]
    )
    for source in glob.glob(os.path.join(metadata_source, "*.json")):
        shutil.copy2(source, os.path.join(target, "metadata", os.path.basename(source)))

    input_name = "{}_unconstrained.yaml".format(pdb_id.lower())
    input_path = os.path.join(target, "input", input_name)
    with open(input_path, "w") as handle:
        handle.write(generate_yaml(candidate))

    relative_target = os.path.relpath(target, REPO_DIR).replace(os.sep, "/")
    container_root = "/workspace/BoltzUI/{}".format(relative_target)
    command_arguments = [
        "predict",
        "{}/input/{}".format(container_root, input_name),
        "--out_dir",
        "{}/results".format(container_root),
        "--cache",
        config["runtime"]["cache"]
    ] + list(config["runtime"]["prediction_arguments"])
    command = {
        "executable": "boltz",
        "arguments": command_arguments,
        "display": "boltz " + " ".join(
            '"{}"'.format(value) if " " in value else value
            for value in command_arguments
        )
    }
    write_json(os.path.join(target, "command.json"), command)
    with open(os.path.join(target, "command.txt"), "w") as handle:
        handle.write(command["display"] + "\n")

    packaged = dict(candidate)
    packaged.update({
        "benchmark_schema_version": config["schema_version"],
        "prepared_at": utc_now(),
        "status": "running",
        "candidate_directory": os.path.relpath(target, BENCHMARK_DIR).replace(
            os.sep, "/"
        ),
        "input_file": "input/{}".format(input_name),
        "reference_file": "reference/{}".format(os.path.basename(reference_target)),
        "prediction_result_root": "results",
        "constraints_present": false_value()
    })
    write_json(os.path.join(target, "candidate.json"), packaged)
    print(target)


def false_value():
    """Make the absence of constraints explicit without relying on YAML parsing."""
    return False


if __name__ == "__main__":
    main()
