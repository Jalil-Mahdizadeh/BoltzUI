#!/usr/bin/env python3
"""Build machine-readable and manuscript-oriented benchmark summaries."""

from __future__ import print_function

import csv
import datetime
import glob
import hashlib
import json
import os


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BENCHMARK_DIR = os.path.dirname(SCRIPT_DIR)
CANDIDATES_DIR = os.path.join(BENCHMARK_DIR, "candidates")
SCREENING_DIR = os.path.join(BENCHMARK_DIR, "screening")
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


def write_text(path, value):
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        handle.write(value)
    os.rename(temporary, path)


def utc_now():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def scalar(value):
    return "" if value is None else value


def candidate_rows():
    rows = []
    for directory in sorted(glob.glob(os.path.join(CANDIDATES_DIR, "*-*"))):
        candidate_path = os.path.join(directory, "candidate.json")
        classification_path = os.path.join(
            directory, "analysis", "classification.json"
        )
        if not os.path.isfile(candidate_path):
            continue
        candidate = load_json(candidate_path)
        classification = (
            load_json(classification_path)
            if os.path.isfile(classification_path) else {}
        )
        best = classification.get("best_of_10_best_of_ensemble") or {}
        execution_path = os.path.join(
            directory, "logs", "execution_status.json"
        )
        execution = (
            load_json(execution_path) if os.path.isfile(execution_path) else {}
        )
        chains = candidate.get("chains", [])
        sequence_payload = "\n".join(sorted(
            "{}:{}".format(
                chain.get("polymer_type", ""), chain.get("sequence", "")
            )
            for chain in chains
        ))
        sequence_cluster = hashlib.sha256(
            sequence_payload.encode("utf-8")
        ).hexdigest()[0:12]
        total_residues = sum(
            len(chain.get("sequence", "")) for chain in chains
        )
        ensemble_p90 = candidate.get("ensemble_profile", {}).get(
            "medoid_backbone_rmsd_p90"
        )
        if ensemble_p90 is not None and ensemble_p90 > 4.0:
            selection_stage = "compactness_sensitivity_p90_5"
        elif 40 <= total_residues <= 350:
            selection_stage = "size_stage_1_40_350"
        elif 20 <= total_residues <= 500:
            selection_stage = "size_stage_2_20_500"
        else:
            selection_stage = "size_stage_3_10_1000"
        row = {
            "pdb_id": candidate["pdb_id"],
            "status": candidate.get("status"),
            "directory": os.path.relpath(directory, BENCHMARK_DIR).replace(
                os.sep, "/"
            ),
            "sequence_input_cluster": sequence_cluster,
            "selection_stage": selection_stage,
            "release_date": candidate.get("release_date"),
            "title": candidate.get("title"),
            "polymer_types": "+".join(
                sorted(set(chain.get("polymer_type", "") for chain in chains))
            ),
            "chain_lengths": "+".join(
                str(len(chain.get("sequence", ""))) for chain in chains
            ),
            "total_residues": total_residues,
            "nmr_models_total": (
                candidate.get("ensemble_profile", {}).get("models_total")
            ),
            "nmr_models_compared": classification.get(
                "reference_models_compared"
            ),
            "ensemble_p90_rmsd_angstrom": ensemble_p90,
            "ensemble_median_contacts": (
                candidate.get("ensemble_profile", {}).get(
                    "native_contact_count_median"
                )
            ),
            "predictions_compared": classification.get(
                "prediction_models_compared"
            ),
            "incorrect_models": (
                classification.get("capri_class_counts", {}).get("incorrect")
            ),
            "acceptable_models": (
                classification.get("capri_class_counts", {}).get("acceptable")
            ),
            "medium_models": (
                classification.get("capri_class_counts", {}).get("medium")
            ),
            "high_models": (
                classification.get("capri_class_counts", {}).get("high")
            ),
            "best_capri_class": best.get("capri_class"),
            "best_prediction_model": best.get("prediction_model"),
            "best_reference_model": best.get("reference_model"),
            "best_fnat": best.get("fnat"),
            "best_irmsd_angstrom": best.get("interface_backbone_rmsd"),
            "best_lrmsd_angstrom": best.get("ligand_rmsd"),
            "best_global_rmsd_angstrom": best.get("global_backbone_rmsd"),
            "best_iptm": best.get("iptm"),
            "best_confidence_score": best.get("confidence_score"),
            "execution_started_at": execution.get("started_at"),
            "execution_ended_at": execution.get("ended_at"),
            "gpu_index": execution.get("gpu_index"),
            "exit_code": execution.get("exit_code"),
            "classification_reason": classification.get(
                "classification_reason"
            ),
            "nef_downloaded": os.path.isfile(
                os.path.join(directory, "nmr_data",
                             candidate["pdb_id"].lower() + "_nmr-data.nef")
            ),
            "nmr_star_downloaded": os.path.isfile(
                os.path.join(directory, "nmr_data",
                             candidate["pdb_id"].lower() + "_nmr-data.str")
            )
        }
        rows.append(row)
    cluster_members = {}
    for row in rows:
        cluster_members.setdefault(row["sequence_input_cluster"], []).append(
            row["pdb_id"]
        )
    for row in rows:
        members = sorted(cluster_members[row["sequence_input_cluster"]])
        row["sequence_input_cluster_size"] = len(members)
        row["sequence_input_cluster_members"] = ",".join(members)
    rows.sort(key=lambda item: (item["release_date"] or "", item["pdb_id"]),
              reverse=True)
    return rows


def manuscript_methods(rows, config, screening):
    passed = [row for row in rows if row["status"] == "passed"]
    skipped = [row for row in rows if row["status"] == "skipped"]
    running = [row for row in rows if row["status"] == "running"]
    passed_clusters = set(
        row["sequence_input_cluster"] for row in passed
    )
    selection = config["selection"]
    classification = config["classification"]
    prediction = " ".join(config["runtime"]["prediction_arguments"])
    return """# Manuscript methods and benchmark accounting

## Study design

We constructed a deliberately failure-enriched challenge set for unconstrained
Boltz 2.2.1 prediction of multichain structures determined by solution NMR. This
design identifies well-defined failure examples; it does not estimate population
accuracy. RCSB PDB entries released after {cutoff} were searched for solution-NMR
structures containing exactly two polymer chain instances and both combined NEF
and NMR-STAR depositions. Protein, RNA, and DNA chains were eligible. Entries
containing non-polymer entities or unsupported polymer chemistry were excluded.
Eligible complexes contained {min_total}-{max_total} total residues, at least
{min_chain} residues per chain, at least {min_models} NMR conformers, and at least
{coverage:.0%} modeled polymer residues.

Screening was performed in three documented size stages. Stage 1 used 40-350 total
residues. Once the retained stage-1 outcomes meant that all remaining entries
would have to fail to reach the requested set size, stage 2 prospectively
expanded only the size window to 20-500 residues. When that pool could no longer
yield ten failures, stage 3 expanded only the size window to 10-1000 residues.
All other criteria and all classification thresholds remained fixed, and the
complete earlier-stage queries and tables were retained.

To minimize ambiguity from experimental disorder, coordinate ensembles were
required to have at least {contacts} median inter-chain residue contacts at a
{cutoff_contact:.1f} A heavy-atom cutoff and a medoid-centered 90th-percentile
backbone RMSD no greater than {ensemble:.1f} A. At least 90% sequence identity
and anchor coverage per chain and conformer were required for coordinate mapping.
The strict size-stage pool used p90 <= 4.0 A and yielded nine qualifying
failures. After that pool was exhausted, a labeled compactness-sensitivity stage
admitted only near-threshold ensembles with 4.0 < p90 <= 5.0 A; all individual
p90 values were retained.

## Prediction

Each input contained polymer sequences only, with no experimental contacts,
templates, covalent constraints, pockets, or restraints. Ten structures were
sampled with seed 1, three recycling steps, 400 sampling steps, physical
potentials, and ColabFold-server MSAs. The full fixed Boltz argument vector was:

`{prediction}`

Method conditioning was set to `x-ray diffraction` to reproduce the supplied
benchmark command, although all reference entries were determined by solution
NMR.

## Evaluation

Every predicted model was compared with every usable experimental conformer.
Equivalent homomer chains were exhaustively permuted. Native inter-chain residue
contacts used a {cutoff_contact:.1f} A heavy-atom cutoff. CAPRI-like classes used
Fnat together with interface RMSD (iRMSD) and ligand RMSD (LRMSD): high quality,
Fnat >= {h_fnat} and (LRMSD <= {h_l} A or iRMSD <= {h_i} A); medium quality,
Fnat >= {m_fnat} and (LRMSD <= {m_l} A or iRMSD <= {m_i} A); acceptable quality,
Fnat >= {a_fnat} and (LRMSD <= {a_l} A or iRMSD <= {a_i} A); incorrect otherwise.
An entry was called passed only if all ten predictions were incorrect against
every NMR conformer. If any prediction was acceptable or better, the entry was
called skipped. All screened and executed files were retained.

## Accounting

- Initial RCSB search hits: {search_hits}
- Metadata-eligible entries: {metadata_eligible}
- Coordinate-screened queue: {queue}
- Stage-1 search/metadata/coordinate counts: {stage1_search}/{stage1_metadata}/{stage1_queue}
- Stage-2 search/metadata/coordinate counts: {stage2_search}/{stage2_metadata}/{stage2_queue}
- Stage-3 strict-p90 search/metadata/coordinate counts: {stage3_search}/{stage3_metadata}/{stage3_queue}
- Final p90<=5 A coordinate-screened queue: {sensitivity_queue}
- Entries executed: {executed}
- Passed failure cases: {passed}
- Unique sequence-input clusters among passed cases: {passed_clusters}
- Skipped entries: {skipped}
- Running/unclassified entries: {running}

Because sampling continued until the target number of failures was reached, the
passed set must be described as a challenge set, not as a denominator-based
accuracy estimate. Distinct PDB depositions with the same unordered polymer
sequence input are reported as separate experimental states but grouped by
`sequence_input_cluster`; they must not be treated as independent sequence-level
replicates.
""".format(
        cutoff=selection["minimum_release_date_exclusive"],
        min_total=selection["minimum_total_polymer_residues"],
        max_total=selection["maximum_total_polymer_residues"],
        min_chain=selection["minimum_chain_residues"],
        min_models=selection["minimum_nmr_models"],
        coverage=selection["minimum_modeled_polymer_fraction"],
        contacts=selection["minimum_native_interchain_contacts"],
        cutoff_contact=selection["native_contact_cutoff_angstrom"],
        ensemble=selection["maximum_ensemble_p90_backbone_rmsd_angstrom"],
        prediction=prediction,
        h_fnat=classification["high"]["minimum_fnat"],
        h_l=classification["high"]["maximum_lrmsd_angstrom"],
        h_i=classification["high"]["maximum_irmsd_angstrom"],
        m_fnat=classification["medium"]["minimum_fnat"],
        m_l=classification["medium"]["maximum_lrmsd_angstrom"],
        m_i=classification["medium"]["maximum_irmsd_angstrom"],
        a_fnat=classification["acceptable"]["minimum_fnat"],
        a_l=classification["acceptable"]["maximum_lrmsd_angstrom"],
        a_i=classification["acceptable"]["maximum_irmsd_angstrom"],
        search_hits=screening.get("initial_search_hits"),
        metadata_eligible=screening.get("metadata_eligible"),
        queue=screening.get("coordinate_queue"),
        stage1_search=screening.get("stage_1", {}).get("initial_search_hits"),
        stage1_metadata=screening.get("stage_1", {}).get("metadata_eligible"),
        stage1_queue=screening.get("stage_1", {}).get("coordinate_queue"),
        stage2_search=screening.get("stage_2", {}).get("initial_search_hits"),
        stage2_metadata=screening.get("stage_2", {}).get("metadata_eligible"),
        stage2_queue=screening.get("stage_2", {}).get("coordinate_queue"),
        stage3_search=screening.get("stage_3_strict_p90", {}).get(
            "initial_search_hits"
        ),
        stage3_metadata=screening.get("stage_3_strict_p90", {}).get(
            "metadata_eligible"
        ),
        stage3_queue=screening.get("stage_3_strict_p90", {}).get(
            "coordinate_queue"
        ),
        sensitivity_queue=screening.get("coordinate_queue"),
        executed=len(passed) + len(skipped),
        passed=len(passed),
        passed_clusters=len(passed_clusters),
        skipped=len(skipped),
        running=len(running)
    )


def display_number(value, digits=2):
    if value is None or value == "":
        return ""
    return ("{:.%df}" % digits).format(float(value))


def manuscript_results(rows, config, screening):
    passed = [row for row in rows if row["status"] == "passed"]
    skipped = [row for row in rows if row["status"] == "skipped"]
    clusters = set(row["sequence_input_cluster"] for row in passed)
    strict = [
        row for row in passed
        if row["selection_stage"] != "compactness_sensitivity_p90_5"
    ]
    sensitivity = [
        row for row in passed
        if row["selection_stage"] == "compactness_sensitivity_p90_5"
    ]
    lines = [
        "# Manuscript results",
        "",
        "The staged search yielded {} passed failure PDBs and {} skipped PDBs "
        "after {} entries were executed. The passed set represents {} unique "
        "unordered sequence-input clusters. {} passed entries came from the "
        "strict p90 <= 4.0 A pool and {} from the labeled 4.0-5.0 A "
        "compactness-sensitivity stage.".format(
            len(passed), len(skipped), len(passed) + len(skipped),
            len(clusters), len(strict), len(sensitivity)
        ),
        "",
        "Every passed entry had 10/10 CAPRI-incorrect predictions under the "
        "best-of-NMR-ensemble and symmetry-aware rule. Values below describe "
        "the best (least wrong) prediction for each passed entry.",
        "",
        "| PDB | Polymer(s) | Lengths | Selection stage | p90 RMSD (A) | "
        "Best Fnat | Best iRMSD (A) | Best LRMSD (A) | Best ipTM |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|"
    ]
    for row in passed:
        lines.append(
            "| {pdb} | {types} | {lengths} | {stage} | {p90} | {fnat} | "
            "{irmsd} | {lrmsd} | {iptm} |".format(
                pdb=row["pdb_id"],
                types=row["polymer_types"],
                lengths=row["chain_lengths"],
                stage=row["selection_stage"],
                p90=display_number(row["ensemble_p90_rmsd_angstrom"]),
                fnat=display_number(row["best_fnat"], 3),
                irmsd=display_number(row["best_irmsd_angstrom"]),
                lrmsd=display_number(row["best_lrmsd_angstrom"]),
                iptm=display_number(row["best_iptm"], 3)
            )
        )
    lines.extend([
        "",
        "Skipped entries (at least one acceptable-or-better model): " +
        ", ".join(row["pdb_id"] for row in skipped) + ".",
        "",
        "This is a deliberately failure-enriched challenge set: search and "
        "execution continued until the requested target was reached. These "
        "counts must not be interpreted as an unbiased Boltz accuracy estimate. "
        "Distinct PDB experimental states sharing a sequence input are clustered "
        "in the TSV/JSON outputs and are not independent sequence-level "
        "replicates.",
        ""
    ])
    return "\n".join(lines)


def screening_counts():
    query_path = os.path.join(
        BENCHMARK_DIR, "screening", "rcsb_search_response.json"
    )
    eligible_path = os.path.join(
        BENCHMARK_DIR, "screening", "eligible_candidates.json"
    )
    queue_path = os.path.join(
        BENCHMARK_DIR, "screening", "candidate_queue.json"
    )
    query = load_json(query_path)
    eligible = load_json(eligible_path)
    queue = load_json(queue_path)
    result = {
        "initial_search_hits": query.get("total_count", len(query.get("result_set", []))),
        "metadata_eligible": len(eligible),
        "coordinate_queue": len(queue)
    }
    stage_1_dir = os.path.join(SCREENING_DIR, "stage1_40_350")
    stage_1_query_path = os.path.join(stage_1_dir, "rcsb_search_response.json")
    stage_1_eligible_path = os.path.join(stage_1_dir, "eligible_candidates.json")
    stage_1_queue_path = os.path.join(stage_1_dir, "candidate_queue.json")
    if all(os.path.isfile(path) for path in (
            stage_1_query_path, stage_1_eligible_path, stage_1_queue_path)):
        stage_1_query = load_json(stage_1_query_path)
        result["stage_1"] = {
            "minimum_total_polymer_residues": 40,
            "maximum_total_polymer_residues": 350,
            "initial_search_hits": stage_1_query.get(
                "total_count", len(stage_1_query.get("result_set", []))
            ),
            "metadata_eligible": len(load_json(stage_1_eligible_path)),
            "coordinate_queue": len(load_json(stage_1_queue_path))
        }
    stage_2_dir = os.path.join(SCREENING_DIR, "stage2_20_500")
    stage_2_query_path = os.path.join(stage_2_dir, "rcsb_search_response.json")
    stage_2_eligible_path = os.path.join(stage_2_dir, "eligible_candidates.json")
    stage_2_queue_path = os.path.join(stage_2_dir, "candidate_queue.json")
    if all(os.path.isfile(path) for path in (
            stage_2_query_path, stage_2_eligible_path, stage_2_queue_path)):
        stage_2_query = load_json(stage_2_query_path)
        result["stage_2"] = {
            "minimum_total_polymer_residues": 20,
            "maximum_total_polymer_residues": 500,
            "initial_search_hits": stage_2_query.get(
                "total_count", len(stage_2_query.get("result_set", []))
            ),
            "metadata_eligible": len(load_json(stage_2_eligible_path)),
            "coordinate_queue": len(load_json(stage_2_queue_path))
        }
    stage_3_dir = os.path.join(SCREENING_DIR, "stage3_10_1000_p90_4")
    stage_3_query_path = os.path.join(stage_3_dir, "rcsb_search_response.json")
    stage_3_eligible_path = os.path.join(stage_3_dir, "eligible_candidates.json")
    stage_3_queue_path = os.path.join(stage_3_dir, "candidate_queue.json")
    if all(os.path.isfile(path) for path in (
            stage_3_query_path, stage_3_eligible_path, stage_3_queue_path)):
        stage_3_query = load_json(stage_3_query_path)
        result["stage_3_strict_p90"] = {
            "minimum_total_polymer_residues": 10,
            "maximum_total_polymer_residues": 1000,
            "maximum_ensemble_p90_backbone_rmsd_angstrom": 4.0,
            "initial_search_hits": stage_3_query.get(
                "total_count", len(stage_3_query.get("result_set", []))
            ),
            "metadata_eligible": len(load_json(stage_3_eligible_path)),
            "coordinate_queue": len(load_json(stage_3_queue_path))
        }
    return result


def main():
    if not os.path.isdir(SUMMARY_DIR):
        os.makedirs(SUMMARY_DIR)
    config = load_json(os.path.join(BENCHMARK_DIR, "config.json"))
    rows = candidate_rows()
    screening = screening_counts()
    status_counts = {
        status: sum(1 for row in rows if row["status"] == status)
        for status in ("passed", "skipped", "running")
    }
    summary = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "benchmark_name": config["benchmark_name"],
        "target_passed_entries": config["target_passed_entries"],
        "screening": screening,
        "status_counts": status_counts,
        "entries": rows
    }
    write_json(os.path.join(SUMMARY_DIR, "benchmark_results.json"), summary)

    fieldnames = list(rows[0].keys()) if rows else ["pdb_id", "status"]
    tsv_path = os.path.join(SUMMARY_DIR, "benchmark_results.tsv")
    temporary = tsv_path + ".tmp"
    with open(temporary, "w") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, delimiter="\t",
            extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: scalar(value) for key, value in row.items()})
    os.rename(temporary, tsv_path)

    write_text(
        os.path.join(SUMMARY_DIR, "MANUSCRIPT_METHODS.md"),
        manuscript_methods(rows, config, screening)
    )
    write_text(
        os.path.join(SUMMARY_DIR, "MANUSCRIPT_RESULTS.md"),
        manuscript_results(rows, config, screening)
    )
    manifests = {}
    summary_names = [
        "benchmark_results.json", "benchmark_results.tsv",
        "MANUSCRIPT_METHODS.md", "MANUSCRIPT_RESULTS.md"
    ]
    for optional_name in (
            "validation_report.json", "environment.txt",
            "environment.txt.sha256"):
        if os.path.isfile(os.path.join(SUMMARY_DIR, optional_name)):
            summary_names.append(optional_name)
    for name in summary_names:
        path = os.path.join(SUMMARY_DIR, name)
        manifests[name] = {
            "sha256": sha256_file(path),
            "bytes": os.path.getsize(path)
        }
    write_json(os.path.join(SUMMARY_DIR, "summary_checksums.json"), manifests)
    print(json.dumps({
        "summary_directory": SUMMARY_DIR,
        "screening": screening,
        "status_counts": status_counts
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
