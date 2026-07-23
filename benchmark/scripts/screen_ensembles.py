#!/usr/bin/env python3
"""Download experimental ensembles and apply coordinate-level quality screens."""

from __future__ import print_function

import concurrent.futures
import csv
import hashlib
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from structure_metrics import ensemble_profile, parse_pdb, serializable_ensemble_profile


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BENCHMARK_DIR = os.path.dirname(SCRIPT_DIR)
SCREENING_DIR = os.path.join(BENCHMARK_DIR, "screening")
STRUCTURE_DIR = os.path.join(SCREENING_DIR, "structures")
CONFIG_PATH = os.path.join(BENCHMARK_DIR, "config.json")
ELIGIBLE_PATH = os.path.join(SCREENING_DIR, "eligible_candidates.json")
PDB_URL = "https://files.rcsb.org/download/{}.pdb"


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


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def download_file(url, target, attempts=4):
    if os.path.isfile(target) and os.path.getsize(target) > 0:
        return
    last_error = None
    for attempt in range(attempts):
        try:
            request = Request(
                url,
                headers={"User-Agent": "BoltzUI-NMR-benchmark/1.0"}
            )
            with urlopen(request, timeout=90) as response:
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


def screen_candidate(candidate, config):
    pdb_id = candidate["pdb_id"].upper()
    path = os.path.join(STRUCTURE_DIR, "{}.pdb".format(pdb_id.lower()))
    download_file(PDB_URL.format(pdb_id), path)
    models = parse_pdb(path)
    selection = config["selection"]
    reasons = []
    if len(models) < int(selection["minimum_nmr_models"]):
        reasons.append(
            "coordinate_models_{}_below_{}".format(
                len(models), selection["minimum_nmr_models"]
            )
        )

    profile = ensemble_profile(
        models,
        candidate["chains"],
        float(selection["native_contact_cutoff_angstrom"])
    )
    if profile.get("error"):
        reasons.append(profile["error"])
    if profile.get("models_usable", 0) < int(selection["minimum_nmr_models"]):
        reasons.append(
            "usable_models_{}_below_{}".format(
                profile.get("models_usable", 0),
                selection["minimum_nmr_models"]
            )
        )
    if (
        profile.get("native_contact_count_median", 0)
        < int(selection["minimum_native_interchain_contacts"])
    ):
        reasons.append(
            "median_contacts_{}_below_{}".format(
                profile.get("native_contact_count_median", 0),
                selection["minimum_native_interchain_contacts"]
            )
        )
    if (
        profile.get("medoid_backbone_rmsd_p90", float("inf"))
        > float(selection["maximum_ensemble_p90_backbone_rmsd_angstrom"])
    ):
        reasons.append(
            "ensemble_p90_rmsd_{:.3f}_above_{:.3f}".format(
                profile.get("medoid_backbone_rmsd_p90", float("inf")),
                float(selection["maximum_ensemble_p90_backbone_rmsd_angstrom"])
            )
        )

    result = dict(candidate)
    result.update({
        "coordinate_file": os.path.relpath(path, BENCHMARK_DIR),
        "coordinate_sha256": sha256_file(path),
        "coordinate_screen_status": "eligible_run" if not reasons else "screened_out",
        "coordinate_screen_reasons": sorted(set(reasons)),
        "ensemble_profile": serializable_ensemble_profile(profile)
    })
    return result


def main():
    config = load_json(CONFIG_PATH)
    candidates = load_json(ELIGIBLE_PATH)
    if not os.path.isdir(STRUCTURE_DIR):
        os.makedirs(STRUCTURE_DIR)

    results_by_id = {}
    failures = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_id = {
            executor.submit(screen_candidate, candidate, config): candidate["pdb_id"]
            for candidate in candidates
        }
        for future in concurrent.futures.as_completed(future_to_id):
            pdb_id = future_to_id[future]
            try:
                result = future.result()
                results_by_id[pdb_id] = result
                print(
                    "{} {} contacts={} p90={}".format(
                        pdb_id,
                        result["coordinate_screen_status"],
                        result["ensemble_profile"].get(
                            "native_contact_count_median"
                        ),
                        result["ensemble_profile"].get(
                            "medoid_backbone_rmsd_p90"
                        )
                    ),
                    flush=True
                )
            except Exception as error:
                failures[pdb_id] = str(error)
                print("{} ERROR {}".format(pdb_id, error), file=sys.stderr, flush=True)

    ordered = [
        results_by_id[item["pdb_id"]]
        for item in candidates if item["pdb_id"] in results_by_id
    ]
    queue = [
        item for item in ordered
        if item["coordinate_screen_status"] == "eligible_run"
    ]
    write_json(os.path.join(SCREENING_DIR, "ensemble_screen.json"), ordered)
    write_json(os.path.join(SCREENING_DIR, "candidate_queue.json"), queue)
    write_json(os.path.join(SCREENING_DIR, "ensemble_screen_failures.json"), failures)

    table_path = os.path.join(SCREENING_DIR, "ensemble_screen.tsv")
    fields = [
        "pdb_id",
        "coordinate_screen_status",
        "models_total",
        "models_usable",
        "medoid_model",
        "ensemble_p90_backbone_rmsd",
        "median_native_contacts",
        "coordinate_screen_reasons"
    ]
    with open(table_path + ".tmp", "w") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for item in ordered:
            profile = item["ensemble_profile"]
            writer.writerow({
                "pdb_id": item["pdb_id"],
                "coordinate_screen_status": item["coordinate_screen_status"],
                "models_total": profile.get("models_total", ""),
                "models_usable": profile.get("models_usable", ""),
                "medoid_model": profile.get("medoid_model", ""),
                "ensemble_p90_backbone_rmsd": profile.get(
                    "medoid_backbone_rmsd_p90", ""
                ),
                "median_native_contacts": profile.get(
                    "native_contact_count_median", ""
                ),
                "coordinate_screen_reasons": ";".join(
                    item["coordinate_screen_reasons"]
                )
            })
    os.rename(table_path + ".tmp", table_path)

    print(
        "Metadata eligible: {}; coordinate eligible: {}; screened out: {}; errors: {}".format(
            len(candidates),
            len(queue),
            len(ordered) - len(queue),
            len(failures)
        )
    )


if __name__ == "__main__":
    main()
