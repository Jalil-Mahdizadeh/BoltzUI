#!/usr/bin/env python3
"""Compare all Boltz models to every NMR conformer and classify a candidate."""

from __future__ import print_function

import argparse
import datetime
import glob
import gzip
import hashlib
import json
import os
import re
import shutil
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from structure_metrics import (
    CAPRI_RANK,
    compare_models,
    map_model,
    parse_pdb,
    predicted_pdb_files
)


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BENCHMARK_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(BENCHMARK_DIR, "config.json")


def load_json(path):
    with open(path, "r") as handle:
        return json.load(handle)


def write_json(path, value):
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.rename(temporary, path)


def utc_now():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def finite_or_infinity(value):
    return value if value is not None else float("inf")


def comparison_key(value):
    return (
        -CAPRI_RANK[value["capri_class"]],
        -value["fnat"],
        finite_or_infinity(value["interface_backbone_rmsd"]),
        finite_or_infinity(value["ligand_rmsd"]),
        finite_or_infinity(value["global_backbone_rmsd"])
    )


def model_index(path):
    match = re.search(r"_model_(\d+)", os.path.basename(path))
    return int(match.group(1)) if match else None


def confidence_for(pdb_path):
    directory = os.path.dirname(pdb_path)
    index = model_index(pdb_path)
    patterns = [
        os.path.join(directory, "confidence_*_model_{}.json".format(index)),
        os.path.join(directory, "confidence_*.json")
    ]
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            return load_json(matches[0]), matches[0]
    return None, None


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def download(url, target, attempts=4):
    if os.path.isfile(target) and os.path.getsize(target) > 0:
        return
    last_error = None
    for attempt in range(attempts):
        try:
            request = Request(
                url,
                headers={"User-Agent": "BoltzUI-NMR-benchmark/1.0"}
            )
            with urlopen(request, timeout=120) as response:
                data = response.read()
            if not data:
                raise RuntimeError("empty response")
            temporary = target + ".tmp"
            with open(temporary, "wb") as handle:
                handle.write(data)
            os.rename(temporary, target)
            return
        except (HTTPError, URLError, RuntimeError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("Failed to download {}: {}".format(url, last_error))


def download_unified_nmr(candidate_dir, pdb_id):
    target_dir = os.path.join(candidate_dir, "nmr_data")
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir)
    lower = pdb_id.lower()
    middle = lower[1:3]
    base = (
        "https://files.rcsb.org/pub/pdb/data/structures/divided/"
        "nmr_data/{}/{}_nmr-data"
    ).format(middle, lower)
    records = []
    for extension, label in (("nef", "NEF"), ("str", "NMR-STAR")):
        compressed = os.path.join(
            target_dir, "{}_nmr-data.{}.gz".format(lower, extension)
        )
        plain = os.path.join(
            target_dir, "{}_nmr-data.{}".format(lower, extension)
        )
        url = "{}.{}.gz".format(base, extension)
        download(url, compressed)
        with gzip.open(compressed, "rb") as source:
            data = source.read()
        if not data:
            raise RuntimeError("{} archive is empty for {}".format(label, pdb_id))
        temporary = plain + ".tmp"
        with open(temporary, "wb") as handle:
            handle.write(data)
        os.rename(temporary, plain)
        records.append({
            "format": label,
            "source_url": url,
            "compressed_file": os.path.relpath(compressed, candidate_dir),
            "compressed_sha256": sha256_file(compressed),
            "file": os.path.relpath(plain, candidate_dir),
            "sha256": sha256_file(plain),
            "bytes": os.path.getsize(plain)
        })
    write_json(os.path.join(target_dir, "downloads.json"), records)
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_directory")
    args = parser.parse_args()
    candidate_dir = os.path.abspath(args.candidate_directory)
    config = load_json(CONFIG_PATH)
    candidate = load_json(os.path.join(candidate_dir, "candidate.json"))
    pdb_id = candidate["pdb_id"].upper()
    reference_path = os.path.join(candidate_dir, candidate["reference_file"])
    reference_models = parse_pdb(reference_path)
    usable_numbers = set(
        candidate["ensemble_profile"].get("usable_model_numbers", [])
    )
    references = []
    for number, model in enumerate(reference_models, start=1):
        if number not in usable_numbers:
            continue
        mapped, identity = map_model(model, candidate["chains"])
        references.append((number, mapped))

    result_root = os.path.join(candidate_dir, candidate["prediction_result_root"])
    predicted_files = predicted_pdb_files(result_root)
    expected_models = 10
    all_comparisons = []
    model_summaries = []

    for predicted_path in predicted_files:
        parsed = parse_pdb(predicted_path)
        if not parsed:
            continue
        predicted_mapped, predicted_identity = map_model(
            parsed[0], candidate["chains"]
        )
        per_reference = []
        for reference_number, reference_mapped in references:
            measured = compare_models(
                reference_mapped,
                predicted_mapped,
                candidate["chains"],
                float(config["selection"]["native_contact_cutoff_angstrom"]),
                config["classification"]
            )
            measured["reference_model"] = reference_number
            per_reference.append(measured)
        if not per_reference:
            continue
        best = min(per_reference, key=comparison_key)
        confidence, confidence_path = confidence_for(predicted_path)
        summary = dict(best)
        summary.update({
            "prediction_model": model_index(predicted_path),
            "prediction_file": os.path.relpath(predicted_path, candidate_dir),
            "prediction_sequence_identity": predicted_identity,
            "confidence_file": (
                os.path.relpath(confidence_path, candidate_dir)
                if confidence_path else None
            ),
            "confidence_score": (
                confidence.get("confidence_score") if confidence else None
            ),
            "ptm": confidence.get("ptm") if confidence else None,
            "iptm": confidence.get("iptm") if confidence else None,
            "complex_plddt": (
                confidence.get("complex_plddt") if confidence else None
            )
        })
        model_summaries.append(summary)
        all_comparisons.append({
            "prediction_model": model_index(predicted_path),
            "prediction_file": os.path.relpath(predicted_path, candidate_dir),
            "reference_comparisons": per_reference
        })

    model_summaries.sort(
        key=lambda item: (
            item["prediction_model"]
            if item["prediction_model"] is not None else 10 ** 9
        )
    )
    technically_complete = len(model_summaries) == expected_models
    all_incorrect = technically_complete and all(
        item["capri_class"] == "incorrect" for item in model_summaries
    )
    status = "passed" if all_incorrect else "skipped"
    reason = (
        "all_10_predictions_capri_incorrect"
        if all_incorrect
        else (
            "at_least_one_prediction_acceptable_or_better"
            if technically_complete else
            "technical_incomplete_prediction_count_{}_expected_{}".format(
                len(model_summaries), expected_models
            )
        )
    )
    best_model = (
        min(model_summaries, key=comparison_key) if model_summaries else None
    )
    class_counts = {
        tier: sum(1 for item in model_summaries if item["capri_class"] == tier)
        for tier in ("incorrect", "acceptable", "medium", "high")
    }
    report = {
        "schema_version": 1,
        "pdb_id": pdb_id,
        "classified_at": utc_now(),
        "status": status,
        "classification_reason": reason,
        "technically_complete": technically_complete,
        "expected_prediction_models": expected_models,
        "prediction_models_compared": len(model_summaries),
        "reference_models_compared": len(references),
        "best_of_10_best_of_ensemble": best_model,
        "capri_class_counts": class_counts,
        "model_summaries": model_summaries
    }
    write_json(os.path.join(candidate_dir, "analysis", "all_comparisons.json"), all_comparisons)
    write_json(os.path.join(candidate_dir, "analysis", "classification.json"), report)

    nmr_downloads = None
    if status == "passed":
        nmr_downloads = download_unified_nmr(candidate_dir, pdb_id)
        report["unified_nmr_downloads"] = nmr_downloads
        write_json(
            os.path.join(candidate_dir, "analysis", "classification.json"), report
        )

    candidate["status"] = status
    candidate["classification_reason"] = reason
    candidate["classified_at"] = report["classified_at"]
    parent = os.path.dirname(candidate_dir)
    final_dir = os.path.join(parent, pdb_id.lower() + "-" + status)
    candidate["candidate_directory"] = os.path.relpath(
        final_dir, BENCHMARK_DIR
    ).replace(os.sep, "/")
    write_json(os.path.join(candidate_dir, "candidate.json"), candidate)

    if final_dir != candidate_dir:
        if os.path.exists(final_dir):
            raise RuntimeError("Classification target already exists: {}".format(final_dir))
        os.rename(candidate_dir, final_dir)
    print(final_dir)
    print(json.dumps({
        "pdb_id": pdb_id,
        "status": status,
        "reason": reason,
        "capri_class_counts": class_counts,
        "best_model": best_model
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
