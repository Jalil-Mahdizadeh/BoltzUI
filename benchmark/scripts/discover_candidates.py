#!/usr/bin/env python3
"""Fetch and prefilter multichain solution-NMR candidates from RCSB."""

from __future__ import print_function

import concurrent.futures
import csv
import json
import os
import sys
import time
try:
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover - Python 2 is not supported, kept explicit.
    raise


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BENCHMARK_DIR = os.path.dirname(SCRIPT_DIR)
SCREENING_DIR = os.path.join(BENCHMARK_DIR, "screening")
METADATA_DIR = os.path.join(SCREENING_DIR, "metadata")
CONFIG_PATH = os.path.join(BENCHMARK_DIR, "config.json")
SEARCH_RESPONSE_PATH = os.path.join(SCREENING_DIR, "rcsb_search_response.json")
DATA_API = "https://data.rcsb.org/rest/v1/core"


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


def fetch_json(url, attempts=4):
    last_error = None
    for attempt in range(attempts):
        try:
            request = Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "BoltzUI-NMR-benchmark/1.0"
                }
            )
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, ValueError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("Failed to fetch {}: {}".format(url, last_error))


def normalized_sequence(entity):
    value = entity.get("entity_poly", {}).get("pdbx_seq_one_letter_code_can", "")
    return "".join(str(value).split()).upper()


def supported_alphabet(polymer_type):
    if polymer_type == "polypeptide(L)":
        return set("ACDEFGHIKLMNPQRSTVWY")
    if polymer_type == "polyribonucleotide":
        return set("ACGU")
    if polymer_type == "polydeoxyribonucleotide":
        return set("ACGT")
    return set()


def bmrb_ids(entry):
    values = []
    for item in entry.get("database_2", []):
        if str(item.get("database_id", "")).upper() == "BMRB":
            value = str(item.get("database_code", "")).strip()
            if value:
                values.append(value)
    return sorted(set(values))


def inspect_candidate(pdb_id, config):
    target = os.path.join(METADATA_DIR, pdb_id.lower())
    if not os.path.isdir(target):
        os.makedirs(target)

    entry_path = os.path.join(target, "entry.json")
    if os.path.isfile(entry_path):
        entry = load_json(entry_path)
    else:
        entry = fetch_json("{}/entry/{}".format(DATA_API, pdb_id))
        write_json(entry_path, entry)

    entity_ids = entry.get("rcsb_entry_container_identifiers", {}).get(
        "polymer_entity_ids", []
    )
    entities = []
    for entity_id in entity_ids:
        entity_path = os.path.join(target, "polymer_entity_{}.json".format(entity_id))
        if os.path.isfile(entity_path):
            entity = load_json(entity_path)
        else:
            entity = fetch_json(
                "{}/polymer_entity/{}/{}".format(DATA_API, pdb_id, entity_id)
            )
            write_json(entity_path, entity)
        entities.append(entity)

    selection = config["selection"]
    info = entry.get("rcsb_entry_info", {})
    deposited = int(info.get("deposited_polymer_monomer_count") or 0)
    modeled = int(info.get("deposited_modeled_polymer_monomer_count") or 0)
    modeled_fraction = float(modeled) / deposited if deposited else 0.0
    reasons = []

    if modeled_fraction < float(selection["minimum_modeled_polymer_fraction"]):
        reasons.append(
            "modeled_fraction_{:.4f}_below_{:.4f}".format(
                modeled_fraction,
                float(selection["minimum_modeled_polymer_fraction"])
            )
        )

    nonpolymer_count = int(info.get("nonpolymer_entity_count") or 0)
    if nonpolymer_count > int(selection["maximum_nonpolymer_entity_count"]):
        reasons.append(
            "nonpolymer_entity_count_{}_above_{}".format(
                nonpolymer_count,
                selection["maximum_nonpolymer_entity_count"]
            )
        )

    supported_types = set(selection["supported_polymer_types"])
    chains = []
    for entity in entities:
        polymer_type = entity.get("entity_poly", {}).get("type", "")
        sequence = normalized_sequence(entity)
        identifiers = entity.get(
            "rcsb_polymer_entity_container_identifiers", {}
        )
        auth_ids = [str(value) for value in identifiers.get("auth_asym_ids", [])]
        entity_id = str(identifiers.get("entity_id", ""))
        if polymer_type not in supported_types:
            reasons.append(
                "unsupported_polymer_type_{}_entity_{}".format(
                    polymer_type or "missing", entity_id
                )
            )
        alphabet = supported_alphabet(polymer_type)
        invalid = sorted(set(sequence) - alphabet) if alphabet else []
        if invalid:
            reasons.append(
                "noncanonical_sequence_entity_{}_{}".format(
                    entity_id, "".join(invalid)
                )
            )
        if not auth_ids:
            reasons.append("missing_author_chain_ids_entity_{}".format(entity_id))
        for chain_id in auth_ids:
            if (
                selection.get("require_single_character_author_chain_ids")
                and len(chain_id) != 1
            ):
                reasons.append("multicharacter_author_chain_id_{}".format(chain_id))
            if len(sequence) < int(selection["minimum_chain_residues"]):
                reasons.append(
                    "chain_{}_length_{}_below_{}".format(
                        chain_id,
                        len(sequence),
                        selection["minimum_chain_residues"]
                    )
                )
            chains.append({
                "auth_asym_id": chain_id,
                "entity_id": entity_id,
                "polymer_type": polymer_type,
                "sequence": sequence,
                "length": len(sequence)
            })

    expected_chains = int(selection["polymer_chain_instances"])
    if len(chains) != expected_chains:
        reasons.append(
            "resolved_chain_count_{}_not_{}".format(len(chains), expected_chains)
        )
    if len(set(chain["auth_asym_id"] for chain in chains)) != len(chains):
        reasons.append("duplicate_author_chain_ids")

    result = {
        "pdb_id": pdb_id.upper(),
        "title": entry.get("struct", {}).get("title"),
        "release_date": entry.get("rcsb_accession_info", {}).get(
            "initial_release_date"
        ),
        "experimental_method": (
            entry.get("exptl", [{}])[0].get("method")
            if entry.get("exptl") else None
        ),
        "polymer_composition": info.get("polymer_composition"),
        "deposited_polymer_residues": deposited,
        "modeled_polymer_residues": modeled,
        "modeled_polymer_fraction": modeled_fraction,
        "deposited_model_count": int(info.get("deposited_model_count") or 0),
        "nonpolymer_entity_count": nonpolymer_count,
        "bmrb_ids": bmrb_ids(entry),
        "chains": chains,
        "prefilter_status": "eligible" if not reasons else "screened_out",
        "prefilter_reasons": sorted(set(reasons)),
        "metadata_directory": os.path.relpath(target, BENCHMARK_DIR)
    }
    return result


def main():
    config = load_json(CONFIG_PATH)
    response = load_json(SEARCH_RESPONSE_PATH)
    identifiers = [
        item["identifier"].upper() for item in response.get("result_set", [])
    ]
    if not identifiers:
        raise RuntimeError("The saved RCSB search response contains no candidates.")

    if not os.path.isdir(METADATA_DIR):
        os.makedirs(METADATA_DIR)

    results_by_id = {}
    failures = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_id = {
            executor.submit(inspect_candidate, pdb_id, config): pdb_id
            for pdb_id in identifiers
        }
        for future in concurrent.futures.as_completed(future_to_id):
            pdb_id = future_to_id[future]
            try:
                results_by_id[pdb_id] = future.result()
                print(
                    "{} {}".format(
                        pdb_id, results_by_id[pdb_id]["prefilter_status"]
                    ),
                    flush=True
                )
            except Exception as error:
                failures[pdb_id] = str(error)
                print("{} ERROR {}".format(pdb_id, error), file=sys.stderr, flush=True)

    ordered = [results_by_id[pdb_id] for pdb_id in identifiers if pdb_id in results_by_id]
    eligible = [item for item in ordered if item["prefilter_status"] == "eligible"]
    write_json(os.path.join(SCREENING_DIR, "candidate_metadata.json"), ordered)
    write_json(os.path.join(SCREENING_DIR, "eligible_candidates.json"), eligible)
    write_json(os.path.join(SCREENING_DIR, "metadata_fetch_failures.json"), failures)

    table_path = os.path.join(SCREENING_DIR, "candidate_prefilter.tsv")
    fields = [
        "pdb_id",
        "prefilter_status",
        "release_date",
        "title",
        "polymer_composition",
        "deposited_model_count",
        "deposited_polymer_residues",
        "nonpolymer_entity_count",
        "modeled_polymer_residues",
        "modeled_polymer_fraction",
        "chain_ids",
        "chain_types",
        "chain_lengths",
        "bmrb_ids",
        "prefilter_reasons"
    ]
    with open(table_path + ".tmp", "w") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for item in ordered:
            writer.writerow({
                "pdb_id": item["pdb_id"],
                "prefilter_status": item["prefilter_status"],
                "release_date": item["release_date"] or "",
                "title": item["title"] or "",
                "polymer_composition": item["polymer_composition"] or "",
                "deposited_model_count": item["deposited_model_count"],
                "deposited_polymer_residues": item["deposited_polymer_residues"],
                "nonpolymer_entity_count": item["nonpolymer_entity_count"],
                "modeled_polymer_residues": item["modeled_polymer_residues"],
                "modeled_polymer_fraction": "{:.6f}".format(
                    item["modeled_polymer_fraction"]
                ),
                "chain_ids": ",".join(
                    chain["auth_asym_id"] for chain in item["chains"]
                ),
                "chain_types": ",".join(
                    chain["polymer_type"] for chain in item["chains"]
                ),
                "chain_lengths": ",".join(
                    str(chain["length"]) for chain in item["chains"]
                ),
                "bmrb_ids": ",".join(item["bmrb_ids"]),
                "prefilter_reasons": ";".join(item["prefilter_reasons"])
            })
    os.rename(table_path + ".tmp", table_path)

    print(
        "RCSB search: {}; metadata eligible: {}; screened out: {}; errors: {}".format(
            len(identifiers),
            len(eligible),
            len(ordered) - len(eligible),
            len(failures)
        )
    )


if __name__ == "__main__":
    main()
