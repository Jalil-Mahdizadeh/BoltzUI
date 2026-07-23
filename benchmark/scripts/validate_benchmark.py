#!/usr/bin/env python3
"""Validate benchmark completeness, labels, inputs, and passed NMR downloads."""

from __future__ import print_function

import argparse
import glob
import hashlib
import json
import os


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BENCHMARK_DIR = os.path.dirname(SCRIPT_DIR)
CANDIDATES_DIR = os.path.join(BENCHMARK_DIR, "candidates")
SUMMARY_DIR = os.path.join(BENCHMARK_DIR, "summary")


def load_json(path):
    with open(path, "r") as handle:
        return json.load(handle)


def write_json(path, value):
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.rename(temporary, path)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def check_file(errors, path, label):
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        errors.append("missing_or_empty_{}:{}".format(label, path))
        return False
    return True


def validate_candidate(directory, config):
    errors = []
    candidate_path = os.path.join(directory, "candidate.json")
    if not check_file(errors, candidate_path, "candidate_json"):
        return errors, None
    candidate = load_json(candidate_path)
    pdb_id = candidate["pdb_id"]
    status = candidate.get("status")
    expected_name = pdb_id.lower() + "-" + str(status)
    if os.path.basename(directory) != expected_name:
        errors.append(
            "{}:directory_status_mismatch:{}:{}".format(
                pdb_id, os.path.basename(directory), expected_name
            )
        )
    if status not in ("passed", "skipped"):
        errors.append("{}:unclassified_status:{}".format(pdb_id, status))
        return errors, candidate

    input_path = os.path.join(directory, candidate["input_file"])
    if check_file(errors, input_path, "input_yaml"):
        with open(input_path, "r") as handle:
            input_text = handle.read().lower()
        forbidden = (
            "constraints:", "templates:", "ligands:", "pocket:",
            "contacts:", "bonds:"
        )
        for token in forbidden:
            if token in input_text:
                errors.append("{}:forbidden_input_token:{}".format(pdb_id, token))
    if candidate.get("constraints_present") is not False:
        errors.append("{}:constraints_present_not_false".format(pdb_id))

    command_path = os.path.join(directory, "command.json")
    if check_file(errors, command_path, "command_json"):
        command = load_json(command_path)
        arguments = command.get("arguments", [])
        expected_tail = config["runtime"]["prediction_arguments"]
        if not arguments or arguments[0] != "predict":
            errors.append("{}:command_does_not_start_with_predict".format(pdb_id))
        if (
            len(arguments) < len(expected_tail)
            or arguments[-len(expected_tail):] != expected_tail
        ):
            errors.append("{}:prediction_argument_vector_mismatch".format(pdb_id))
        if "--cache" not in arguments:
            errors.append("{}:command_missing_cache".format(pdb_id))
        else:
            cache_index = arguments.index("--cache")
            observed_cache = (
                arguments[cache_index + 1]
                if cache_index + 1 < len(arguments) else None
            )
            if observed_cache != config["runtime"]["cache"]:
                errors.append(
                    "{}:cache_mismatch:{}".format(pdb_id, observed_cache)
                )

    reference = os.path.join(directory, candidate["reference_file"])
    check_file(errors, reference, "reference")
    execution_path = os.path.join(directory, "logs", "execution_status.json")
    if check_file(errors, execution_path, "execution_status"):
        execution = load_json(execution_path)
        if execution.get("exit_code") != 0:
            errors.append(
                "{}:nonzero_execution_exit:{}".format(
                    pdb_id, execution.get("exit_code")
                )
            )

    classification_path = os.path.join(
        directory, "analysis", "classification.json"
    )
    if not check_file(errors, classification_path, "classification"):
        return errors, candidate
    classification = load_json(classification_path)
    if classification.get("status") != status:
        errors.append(
            "{}:classification_status_mismatch:{}:{}".format(
                pdb_id, classification.get("status"), status
            )
        )
    if classification.get("prediction_models_compared") != 10:
        errors.append(
            "{}:prediction_count:{}".format(
                pdb_id, classification.get("prediction_models_compared")
            )
        )
    if not classification.get("technically_complete"):
        errors.append("{}:classification_not_technically_complete".format(pdb_id))
    class_counts = classification.get("capri_class_counts", {})
    if sum(class_counts.get(name, 0) for name in (
            "incorrect", "acceptable", "medium", "high")) != 10:
        errors.append("{}:capri_counts_do_not_sum_to_10".format(pdb_id))
    if status == "passed" and class_counts.get("incorrect") != 10:
        errors.append("{}:passed_without_10_incorrect".format(pdb_id))
    if status == "skipped" and class_counts.get("incorrect") == 10:
        errors.append("{}:skipped_despite_10_incorrect".format(pdb_id))

    prediction_root = os.path.join(
        directory, candidate["prediction_result_root"]
    )
    prediction_pdbs = []
    for root, directories, files in os.walk(prediction_root):
        prediction_pdbs.extend(
            os.path.join(root, name) for name in files
            if name.endswith(".pdb") and "_model_" in name
        )
    if len(prediction_pdbs) != 10:
        errors.append(
            "{}:prediction_pdb_file_count:{}".format(
                pdb_id, len(prediction_pdbs)
            )
        )

    if status == "passed":
        downloads_path = os.path.join(
            directory, "nmr_data", "downloads.json"
        )
        if check_file(errors, downloads_path, "nmr_download_manifest"):
            downloads = load_json(downloads_path)
            if len(downloads) != 2:
                errors.append(
                    "{}:nmr_download_record_count:{}".format(
                        pdb_id, len(downloads)
                    )
                )
            formats = set(item.get("format") for item in downloads)
            if formats != set(("NEF", "NMR-STAR")):
                errors.append(
                    "{}:nmr_formats:{}".format(pdb_id, sorted(formats))
                )
            for item in downloads:
                for field, digest_field in (
                        ("file", "sha256"),
                        ("compressed_file", "compressed_sha256")):
                    path = os.path.join(directory, item[field])
                    if check_file(errors, path, field):
                        observed = sha256_file(path)
                        if observed != item[digest_field]:
                            errors.append(
                                "{}:checksum_mismatch:{}".format(pdb_id, path)
                            )
    return errors, candidate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-incomplete", action="store_true",
        help="Do not require the configured target number of passed entries."
    )
    args = parser.parse_args()
    config = load_json(os.path.join(BENCHMARK_DIR, "config.json"))
    errors = []
    candidates = []
    for directory in sorted(glob.glob(os.path.join(CANDIDATES_DIR, "*-*"))):
        if directory.endswith("-running"):
            errors.append("unclassified_directory:{}".format(directory))
            continue
        candidate_errors, candidate = validate_candidate(directory, config)
        errors.extend(candidate_errors)
        if candidate:
            candidates.append(candidate)
    passed = sum(1 for item in candidates if item.get("status") == "passed")
    skipped = sum(1 for item in candidates if item.get("status") == "skipped")
    target = int(config["target_passed_entries"])
    if not args.allow_incomplete and passed < target:
        errors.append(
            "passed_count_{}_below_target_{}".format(passed, target)
        )
    report = {
        "schema_version": 1,
        "valid": not errors,
        "target_passed_entries": target,
        "passed": passed,
        "skipped": skipped,
        "classified": passed + skipped,
        "errors": errors
    }
    if not os.path.isdir(SUMMARY_DIR):
        os.makedirs(SUMMARY_DIR)
    write_json(os.path.join(SUMMARY_DIR, "validation_report.json"), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
