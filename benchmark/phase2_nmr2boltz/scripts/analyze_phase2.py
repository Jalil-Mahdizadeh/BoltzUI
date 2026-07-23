#!/usr/bin/env python3
"""Compare every constrained model with every usable NMR conformer."""

import csv
import glob
import json
import math
import re
import statistics
import sys
from pathlib import Path

import numpy as np
import yaml


PHASE2 = Path(__file__).resolve().parents[1]
BENCHMARK = PHASE2.parent
sys.path.insert(0, str(BENCHMARK / "scripts"))

from structure_metrics import (  # noqa: E402
    CAPRI_RANK,
    compare_models,
    map_model,
    normalize_atom_name,
    parse_pdb,
    predicted_pdb_files,
)


TIERS = ("incorrect", "acceptable", "medium", "high")
METRICS = (
    "fnat",
    "interface_backbone_rmsd",
    "ligand_rmsd",
    "global_backbone_rmsd",
    "contact_f1",
)


def load_json(path):
    with path.open("r") as handle:
        return json.load(handle)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def load_yaml(path):
    with path.open("r") as handle:
        value = yaml.safe_load(handle)
    return value if isinstance(value, dict) else {}


def finite_or_infinity(value):
    return value if value is not None else float("inf")


def comparison_key(value):
    return (
        -CAPRI_RANK[value["capri_class"]],
        -value["fnat"],
        finite_or_infinity(value["interface_backbone_rmsd"]),
        finite_or_infinity(value["ligand_rmsd"]),
        finite_or_infinity(value["global_backbone_rmsd"]),
    )


def model_index(path):
    match = re.search(r"_model_(\d+)", Path(path).name)
    return int(match.group(1)) if match else None


def confidence_for(pdb_path):
    index = model_index(pdb_path)
    directory = Path(pdb_path).parent
    matches = sorted(directory.glob("confidence_*_model_{}.json".format(index)))
    if not matches:
        return None, None
    return load_json(matches[0]), matches[0]


def numeric_median(values):
    finite = [
        float(value)
        for value in values
        if value is not None and math.isfinite(float(value))
    ]
    return statistics.median(finite) if finite else None


def delta(current, baseline, metric):
    first = current.get(metric)
    second = baseline.get(metric)
    if first is None or second is None:
        return None
    return float(first) - float(second)


def endpoint_key(endpoint):
    return (str(endpoint[0]), int(endpoint[1]), normalize_atom_name(endpoint[2]))


def canonical_pair(first, second, bound):
    endpoints = tuple(sorted((endpoint_key(first), endpoint_key(second))))
    return endpoints + (round(float(bound), 6),)


def normalized_constraint_sets(document):
    exact = set()
    unions = set()
    for wrapper in document.get("constraints") or []:
        if "atom_contact" in wrapper:
            item = wrapper["atom_contact"]
            exact.add(
                canonical_pair(
                    item["atom1"], item["atom2"], item["max_distance"]
                )
            )
        elif "atom_contact_union" in wrapper:
            alternatives = frozenset(
                canonical_pair(
                    item["atom1"], item["atom2"], item["max_distance"]
                )
                for item in wrapper["atom_contact_union"]["alternatives"]
            )
            unions.add(alternatives)
    return exact, unions


def set_parity(first, second):
    union = first | second
    intersection = first & second
    return {
        "first_count": len(first),
        "second_count": len(second),
        "intersection_count": len(intersection),
        "first_only_count": len(first - second),
        "second_only_count": len(second - first),
        "jaccard": float(len(intersection)) / len(union) if union else 1.0,
        "identical": first == second,
    }


def constraint_scope(document):
    output = {
        "exact_total": 0,
        "exact_interchain": 0,
        "exact_intrachain": 0,
        "union_total": 0,
        "union_interchain_only": 0,
        "union_intrachain_only": 0,
        "union_mixed": 0,
        "union_alternatives": 0,
    }
    for wrapper in document.get("constraints") or []:
        if "atom_contact" in wrapper:
            item = wrapper["atom_contact"]
            output["exact_total"] += 1
            if str(item["atom1"][0]) == str(item["atom2"][0]):
                output["exact_intrachain"] += 1
            else:
                output["exact_interchain"] += 1
        elif "atom_contact_union" in wrapper:
            alternatives = wrapper["atom_contact_union"]["alternatives"]
            scopes = {
                str(item["atom1"][0]) != str(item["atom2"][0])
                for item in alternatives
            }
            output["union_total"] += 1
            output["union_alternatives"] += len(alternatives)
            if scopes == {True}:
                output["union_interchain_only"] += 1
            elif scopes == {False}:
                output["union_intrachain_only"] += 1
            else:
                output["union_mixed"] += 1
    return output


def coordinate(mapped, endpoint):
    chain, residue_index, atom_name = endpoint_key(endpoint)
    residue = mapped.get(chain, {}).get(residue_index - 1)
    if residue is None:
        return None
    return residue["atoms"].get(atom_name)


def measure_pair(mapped, item):
    first = coordinate(mapped, item["atom1"])
    second = coordinate(mapped, item["atom2"])
    if first is None or second is None:
        return {
            "resolved": False,
            "satisfied": None,
            "distance": None,
            "excess": None,
        }
    distance = float(np.linalg.norm(first - second))
    bound = float(item["max_distance"])
    return {
        "resolved": True,
        "satisfied": distance <= bound,
        "distance": distance,
        "excess": max(0.0, distance - bound),
    }


def restraint_audit(mapped, document, model):
    exact = {"total": 0, "resolved": 0, "satisfied": 0, "violated": 0}
    union = {
        "total": 0,
        "satisfied": 0,
        "violated": 0,
        "indeterminate": 0,
    }
    exact_excesses = []
    union_excesses = []
    for wrapper in document.get("constraints") or []:
        if "atom_contact" in wrapper:
            exact["total"] += 1
            measured = measure_pair(mapped, wrapper["atom_contact"])
            if not measured["resolved"]:
                continue
            exact["resolved"] += 1
            if measured["satisfied"]:
                exact["satisfied"] += 1
            else:
                exact["violated"] += 1
            exact_excesses.append(measured["excess"])
        elif "atom_contact_union" in wrapper:
            union["total"] += 1
            measurements = [
                measure_pair(mapped, alternative)
                for alternative in wrapper["atom_contact_union"]["alternatives"]
            ]
            resolved = [item for item in measurements if item["resolved"]]
            satisfied = [item for item in resolved if item["satisfied"]]
            if satisfied:
                union["satisfied"] += 1
                union_excesses.append(0.0)
            elif len(resolved) == len(measurements):
                union["violated"] += 1
                union_excesses.append(
                    min(item["excess"] for item in resolved)
                )
            else:
                union["indeterminate"] += 1
    exact["fraction_satisfied_resolved"] = (
        float(exact["satisfied"]) / exact["resolved"]
        if exact["resolved"] else None
    )
    exact["median_excess_angstrom"] = numeric_median(exact_excesses)
    union_determinate = union["satisfied"] + union["violated"]
    union["fraction_satisfied_determinate"] = (
        float(union["satisfied"]) / union_determinate
        if union_determinate else None
    )
    union["median_minimum_excess_angstrom"] = numeric_median(union_excesses)
    return {"model": model, "exact": exact, "union": union}


def aggregate_audits(audits):
    return {
        "models": len(audits),
        "median_exact_fraction_satisfied_resolved": numeric_median(
            item["exact"]["fraction_satisfied_resolved"] for item in audits
        ),
        "median_union_fraction_satisfied_determinate": numeric_median(
            item["union"]["fraction_satisfied_determinate"] for item in audits
        ),
        "exact_unresolved_total": sum(
            item["exact"]["total"] - item["exact"]["resolved"] for item in audits
        ),
        "union_indeterminate_total": sum(
            item["union"]["indeterminate"] for item in audits
        ),
    }


def analyze_prediction_root(result_root, references, candidate, config, document):
    all_comparisons = []
    summaries = []
    audits = []
    predicted_files = predicted_pdb_files(str(result_root))
    for predicted_path in predicted_files:
        parsed = parse_pdb(predicted_path)
        if not parsed:
            continue
        mapped, identities = map_model(parsed[0], candidate["chains"])
        per_reference = []
        for reference_number, reference_mapped in references:
            measured = compare_models(
                reference_mapped,
                mapped,
                candidate["chains"],
                float(config["selection"]["native_contact_cutoff_angstrom"]),
                config["classification"],
            )
            measured["reference_model"] = reference_number
            per_reference.append(measured)
        if not per_reference:
            continue
        best = min(per_reference, key=comparison_key)
        index = model_index(predicted_path)
        confidence, confidence_path = confidence_for(predicted_path)
        summary = dict(best)
        summary.update(
            {
                "prediction_model": index,
                "prediction_file": str(
                    Path(predicted_path).resolve().relative_to(PHASE2)
                ),
                "prediction_sequence_identity": identities,
                "confidence_file": (
                    str(confidence_path.resolve().relative_to(PHASE2))
                    if confidence_path else None
                ),
                "confidence_score": (
                    confidence.get("confidence_score") if confidence else None
                ),
                "ptm": confidence.get("ptm") if confidence else None,
                "iptm": confidence.get("iptm") if confidence else None,
                "complex_plddt": (
                    confidence.get("complex_plddt") if confidence else None
                ),
            }
        )
        summaries.append(summary)
        audits.append(restraint_audit(mapped, document, index))
        all_comparisons.append(
            {
                "prediction_model": index,
                "prediction_file": summary["prediction_file"],
                "reference_comparisons": per_reference,
            }
        )
    summaries.sort(key=lambda item: item["prediction_model"])
    audits.sort(key=lambda item: item["model"])
    counts = {
        tier: sum(1 for item in summaries if item["capri_class"] == tier)
        for tier in TIERS
    }
    return {
        "technically_complete": len(summaries) == 10,
        "prediction_models_compared": len(summaries),
        "reference_models_compared": len(references),
        "capri_class_counts": counts,
        "best_of_10_best_of_ensemble": (
            min(summaries, key=comparison_key) if summaries else None
        ),
        "metric_medians": {
            metric: numeric_median(item.get(metric) for item in summaries)
            for metric in METRICS
        },
        "model_summaries": summaries,
        "restraint_audits": audits,
        "restraint_audit_summary": aggregate_audits(audits),
        "all_comparisons": all_comparisons,
    }


def paired_effect(analysis, baseline):
    baseline_models = {
        item["prediction_model"]: item
        for item in baseline.get("model_summaries", [])
    }
    pairs = []
    for current in analysis.get("model_summaries", []):
        base = baseline_models.get(current["prediction_model"])
        if base is None:
            continue
        record = {
            "prediction_model": current["prediction_model"],
            "baseline_capri_class": base["capri_class"],
            "current_capri_class": current["capri_class"],
            "capri_rank_delta": (
                CAPRI_RANK[current["capri_class"]]
                - CAPRI_RANK[base["capri_class"]]
            ),
        }
        for metric in METRICS:
            record["{}_delta".format(metric)] = delta(current, base, metric)
        pairs.append(record)
    best = analysis.get("best_of_10_best_of_ensemble")
    baseline_best = baseline.get("best_of_10_best_of_ensemble")
    best_deltas = {}
    if best and baseline_best:
        best_deltas["capri_rank"] = (
            CAPRI_RANK[best["capri_class"]]
            - CAPRI_RANK[baseline_best["capri_class"]]
        )
        for metric in METRICS:
            best_deltas[metric] = delta(best, baseline_best, metric)
    return {
        "paired_models": len(pairs),
        "models_with_capri_rank_improvement": sum(
            item["capri_rank_delta"] > 0 for item in pairs
        ),
        "models_with_capri_rank_worsening": sum(
            item["capri_rank_delta"] < 0 for item in pairs
        ),
        "median_model_deltas": {
            "capri_rank": numeric_median(
                item["capri_rank_delta"] for item in pairs
            ),
            **{
                metric: numeric_median(
                    item["{}_delta".format(metric)] for item in pairs
                )
                for metric in METRICS
            },
        },
        "best_of_10_deltas": best_deltas,
        "model_pairs": pairs,
    }


def compact_analysis(analysis):
    return {
        key: value
        for key, value in analysis.items()
        if key not in ("all_comparisons",)
    }


def format_value(value, digits=2):
    if value is None:
        return "NA"
    return ("{:.%df}" % digits).format(float(value))


def arm_aggregate(cases, arm):
    applicable = [
        case["arms"][arm]
        for case in cases
        if arm in case["arms"] and case["arms"][arm]["applicable"]
    ]
    best = [
        item["analysis"]["best_of_10_best_of_ensemble"]
        for item in applicable
    ]
    best = [item for item in best if item]
    class_counts = {
        tier: sum(
            item["analysis"]["capri_class_counts"].get(tier, 0)
            for item in applicable
        )
        for tier in TIERS
    }
    return {
        "entries_applicable": len(applicable),
        "entries_rescued_acceptable_or_better": sum(
            CAPRI_RANK[item["capri_class"]] >= 1 for item in best
        ),
        "entry_best_class_counts": {
            tier: sum(item["capri_class"] == tier for item in best)
            for tier in TIERS
        },
        "prediction_class_counts": class_counts,
        "median_entry_best_deltas": {
            "capri_rank": numeric_median(
                item["effect"]["best_of_10_deltas"].get("capri_rank")
                for item in applicable
            ),
            **{
                metric: numeric_median(
                    item["effect"]["best_of_10_deltas"].get(metric)
                    for item in applicable
                )
                for metric in METRICS
            },
        },
        "median_model_deltas": {
            "capri_rank": numeric_median(
                pair["capri_rank_delta"]
                for item in applicable
                for pair in item["effect"]["model_pairs"]
            ),
            **{
                metric: numeric_median(
                    pair["{}_delta".format(metric)]
                    for item in applicable
                    for pair in item["effect"]["model_pairs"]
                )
                for metric in METRICS
            },
        },
        "median_restraint_satisfaction_by_entry": {
            "exact": numeric_median(
                item["analysis"]["restraint_audit_summary"][
                    "median_exact_fraction_satisfied_resolved"
                ]
                for item in applicable
            ),
            "union": numeric_median(
                item["analysis"]["restraint_audit_summary"][
                    "median_union_fraction_satisfied_determinate"
                ]
                for item in applicable
            ),
        },
    }


def make_report(summary):
    aggregate = summary["aggregate"]
    combined = aggregate["combined"]
    exact = aggregate["exact"]
    union = aggregate["union"]

    def successful_models(arm):
        counts = arm["prediction_class_counts"]
        return sum(counts.get(label, 0) for label in ("acceptable", "medium", "high"))

    def total_models(arm):
        return sum(arm["prediction_class_counts"].values())

    lines = [
        "# Concise phase-2 report",
        "",
        "## Outcome",
        "",
        (
            "The primary exact+union treatment rescued **{}/10** phase-1 "
            "failures to CAPRI acceptable-or-better in the best of 10 samples. "
            "Exact-only rescued **{}/10** applicable entries and union-only "
            "rescued **{}/9** (9KAD had no union groups)."
        ).format(
            combined["entries_rescued_acceptable_or_better"],
            exact["entries_rescued_acceptable_or_better"],
            union["entries_rescued_acceptable_or_better"],
        ),
        "",
        (
            "At the individual-sample level, exact+union produced "
            "**{}/{}** acceptable-or-better models, versus **0/100** in the "
            "matched unconstrained controls; exact-only produced **{}/{}** "
            "and union-only **{}/{}**."
        ).format(
            successful_models(combined),
            total_models(combined),
            successful_models(exact),
            total_models(exact),
            successful_models(union),
            total_models(union),
        ),
        "",
        (
            "Across entries, the combined arm changed best-of-10 Fnat by a "
            "median **{}**, interface RMSD by **{} Å**, ligand RMSD by **{} Å**, "
            "and global backbone RMSD by **{} Å** relative to the matched "
            "unconstrained control (negative RMSD changes are improvements)."
        ).format(
            format_value(combined["median_entry_best_deltas"]["fnat"], 3),
            format_value(
                combined["median_entry_best_deltas"][
                    "interface_backbone_rmsd"
                ],
                2,
            ),
            format_value(
                combined["median_entry_best_deltas"]["ligand_rmsd"], 2
            ),
            format_value(
                combined["median_entry_best_deltas"]["global_backbone_rmsd"],
                2,
            ),
        ),
        "",
        "## Per-entry best-of-10 results",
        "",
        (
            "| PDB | exact / union (inter-chain) | matched baseline | exact | "
            "union | exact+union | ΔFnat | ΔiRMSD Å | median exact / union "
            "satisfaction |"
        ),
        "|---|---:|---|---|---|---|---:|---:|---:|",
    ]
    for case in summary["cases"]:
        scope = case["conversion"]["constraint_scope"]
        baseline = case["matched_baseline"]["best_of_10_best_of_ensemble"]

        def best_label(arm):
            item = case["arms"].get(arm)
            if not item or not item["applicable"]:
                return "NA"
            best = item["analysis"]["best_of_10_best_of_ensemble"]
            return "{} (Fnat {})".format(
                best["capri_class"], format_value(best["fnat"], 2)
            )

        primary = case["arms"]["combined"]
        effect = primary["effect"]["best_of_10_deltas"]
        audit = primary["analysis"]["restraint_audit_summary"]
        lines.append(
            "| {pdb} | {exact}/{union} ({iexact}/{iunion}) | {base} "
            "(Fnat {base_fnat}) | {exact_label} | {union_label} | "
            "{combined_label} | {dfnat} | {dirmsd} | {esat}/{usat} |".format(
                pdb=case["pdb_id"],
                exact=scope["exact_total"],
                union=scope["union_total"],
                iexact=scope["exact_interchain"],
                iunion=scope["union_interchain_only"],
                base=baseline["capri_class"],
                base_fnat=format_value(baseline["fnat"], 2),
                exact_label=best_label("exact"),
                union_label=best_label("union"),
                combined_label=best_label("combined"),
                dfnat=format_value(effect.get("fnat"), 3),
                dirmsd=format_value(
                    effect.get("interface_backbone_rmsd"), 2
                ),
                esat=format_value(
                    audit["median_exact_fraction_satisfied_resolved"], 2
                ),
                usat=format_value(
                    audit["median_union_fraction_satisfied_determinate"], 2
                ),
            )
        )
    parity = summary["format_parity"]
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            (
                "Median model-level exact and union satisfaction in the "
                "combined arm was **{}** and **{}**, respectively. These are "
                "soft guidance potentials, so satisfaction was evaluated from "
                "the final coordinates rather than assumed."
            ).format(
                format_value(
                    combined["median_restraint_satisfaction_by_entry"]["exact"],
                    2,
                ),
                format_value(
                    combined["median_restraint_satisfaction_by_entry"]["union"],
                    2,
                ),
            ),
            "",
            (
                "NEF and NMR-STAR produced identical executable exact sets for "
                "**{}/10** entries and identical union sets for **{}/10**. The "
                "NEF conversion was therefore prespecified as the sole "
                "prediction source; NMR-STAR was retained as an independent "
                "format-parity audit, not added as duplicate evidence."
            ).format(
                parity["entries_exact_identical"],
                parity["entries_union_identical"],
            ),
            "",
            "The 8Q5Q deposition contains protonated deoxycytidine DNR at "
            "position 5 in both chains. Because phase 1 used its canonical "
            "parent C, phase 2 reran a DNR-matched unconstrained control; this "
            "prevents the modification correction from being credited to the "
            "restraints.",
            "",
            "This is a restraint-assisted reconstruction benchmark, not an "
            "independent de novo validation: the restraints and reference "
            "ensemble come from the same deposition. The set was deliberately "
            "selected for baseline failures (n=10), and exact-only versus "
            "union-only arms contain unequal amounts of experimental "
            "information. Conclusions should therefore be stated as effect "
            "sizes on this challenge set, not as population-wide accuracy.",
            "",
            "Machine-readable results: `phase2_results.json` and "
            "`phase2_results.tsv`. Validation: `validation_report.json`.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    config = load_json(PHASE2 / "config.json")
    phase1_config = load_json(BENCHMARK / "config.json")
    cases = []
    format_records = []

    for pdb_upper in config["pdb_ids"]:
        pdb_id = pdb_upper.lower()
        case_dir = PHASE2 / "cases" / pdb_id
        candidate = load_json(case_dir / "source" / "candidate.json")
        reference_models = parse_pdb(case_dir / "source" / "{}.pdb".format(pdb_id))
        usable = set(candidate["ensemble_profile"]["usable_model_numbers"])
        references = []
        reference_mapped_models = []
        for number, model in enumerate(reference_models, start=1):
            if number not in usable:
                continue
            mapped, identities = map_model(model, candidate["chains"])
            references.append((number, mapped))
            reference_mapped_models.append((number, mapped))

        nef_exact = load_yaml(
            case_dir / "conversion" / "nef" / "atom_constraints_exact.yaml"
        )
        nef_union = load_yaml(
            case_dir / "conversion" / "nef" / "atom_constraints_union.yaml"
        )
        star_exact = load_yaml(
            case_dir / "conversion" / "nmr_star" / "atom_constraints_exact.yaml"
        )
        star_union = load_yaml(
            case_dir / "conversion" / "nmr_star" / "atom_constraints_union.yaml"
        )
        nef_combined = {
            "constraints": (nef_exact.get("constraints") or [])
            + (nef_union.get("constraints") or [])
        }
        nef_sets = normalized_constraint_sets(nef_combined)
        star_sets = normalized_constraint_sets(
            {
                "constraints": (star_exact.get("constraints") or [])
                + (star_union.get("constraints") or [])
            }
        )
        parity = {
            "pdb_id": pdb_upper,
            "exact": set_parity(nef_sets[0], star_sets[0]),
            "union": set_parity(nef_sets[1], star_sets[1]),
        }
        format_records.append(parity)
        nef_report = load_json(
            case_dir / "conversion" / "nef" / "conversion_report.json"
        )
        star_report = load_json(
            case_dir / "conversion" / "nmr_star" / "conversion_report.json"
        )
        reference_audits = [
            restraint_audit(mapped, nef_combined, number)
            for number, mapped in reference_mapped_models
        ]

        original_baseline = load_json(
            case_dir / "source" / "classification.json"
        )
        baseline_name = "phase1_unconstrained"
        matched_baseline = original_baseline
        modified_control_analysis = None
        if pdb_upper == "8Q5Q":
            baseline_name = "modified_unconstrained"
            control_analysis_path = (
                case_dir
                / "modified_unconstrained"
                / "analysis"
                / "classification.json"
            )
            if control_analysis_path.is_file():
                cached_control = load_json(control_analysis_path)
            else:
                cached_control = {}
            if (
                cached_control.get("technically_complete")
                and cached_control.get("prediction_models_compared") == 10
            ):
                matched_baseline = cached_control
            else:
                control_input = load_yaml(
                    case_dir
                    / "modified_unconstrained"
                    / "input"
                    / "8q5q_modified_unconstrained.yaml"
                )
                modified_control_analysis = analyze_prediction_root(
                    case_dir / "modified_unconstrained" / "results",
                    references,
                    candidate,
                    phase1_config,
                    control_input,
                )
                if not modified_control_analysis["technically_complete"]:
                    raise RuntimeError("8Q5Q modified control is incomplete")
                matched_baseline = compact_analysis(modified_control_analysis)
                write_json(
                    case_dir
                    / "modified_unconstrained"
                    / "analysis"
                    / "all_comparisons.json",
                    modified_control_analysis["all_comparisons"],
                )
                write_json(control_analysis_path, matched_baseline)

        arms = {}
        for arm in config["prediction"]["arms"]:
            manifest = load_json(case_dir / arm / "arm_manifest.json")
            arm_record = {
                "applicable": bool(manifest["applicable"]),
                "manifest": manifest,
            }
            if manifest["applicable"]:
                analysis_path = case_dir / arm / "analysis" / "classification.json"
                effect_path = case_dir / arm / "analysis" / "paired_effect.json"
                if analysis_path.is_file():
                    cached_analysis = load_json(analysis_path)
                else:
                    cached_analysis = {}
                if (
                    cached_analysis.get("technically_complete")
                    and cached_analysis.get("prediction_models_compared") == 10
                    and effect_path.is_file()
                ):
                    arm_record["analysis"] = cached_analysis
                    arm_record["effect"] = load_json(effect_path)
                else:
                    document = load_yaml(
                        case_dir
                        / arm
                        / "input"
                        / "{}_{}.yaml".format(pdb_id, arm)
                    )
                    analysis = analyze_prediction_root(
                        case_dir / arm / "results",
                        references,
                        candidate,
                        phase1_config,
                        document,
                    )
                    if not analysis["technically_complete"]:
                        raise RuntimeError(
                            "{} {} is incomplete: {}/10 models".format(
                                pdb_upper,
                                arm,
                                analysis["prediction_models_compared"],
                            )
                        )
                    effect = paired_effect(analysis, matched_baseline)
                    arm_record["analysis"] = compact_analysis(analysis)
                    arm_record["effect"] = effect
                    write_json(
                        case_dir / arm / "analysis" / "all_comparisons.json",
                        analysis["all_comparisons"],
                    )
                    write_json(analysis_path, compact_analysis(analysis))
                    write_json(effect_path, effect)
            arms[arm] = arm_record

        case_record = {
            "pdb_id": pdb_upper,
            "baseline_control": baseline_name,
            "original_phase1_baseline": original_baseline,
            "matched_baseline": matched_baseline,
            "conversion": {
                "nef_statistics": nef_report["statistics"],
                "nmr_star_statistics": star_report["statistics"],
                "constraint_scope": constraint_scope(nef_combined),
                "format_parity": parity,
                "reference_restraint_audit": {
                    "models": reference_audits,
                    "summary": aggregate_audits(reference_audits),
                },
            },
            "arms": arms,
        }
        write_json(case_dir / "analysis_summary.json", case_record)
        cases.append(case_record)
        print("Analyzed {}".format(pdb_upper))

    aggregate = {
        arm: arm_aggregate(cases, arm)
        for arm in config["prediction"]["arms"]
    }
    summary = {
        "schema_version": 1,
        "benchmark_name": config["benchmark_name"],
        "cases": cases,
        "aggregate": aggregate,
        "format_parity": {
            "entries_exact_identical": sum(
                item["exact"]["identical"] for item in format_records
            ),
            "entries_union_identical": sum(
                item["union"]["identical"] for item in format_records
            ),
            "entries": format_records,
        },
    }
    output_dir = PHASE2 / "summary"
    write_json(output_dir / "phase2_results.json", summary)

    columns = [
        "pdb_id",
        "baseline_control",
        "exact_constraints",
        "exact_interchain",
        "union_groups",
        "union_interchain_only",
        "baseline_best_class",
        "baseline_best_fnat",
        "exact_best_class",
        "exact_best_fnat",
        "union_best_class",
        "union_best_fnat",
        "combined_best_class",
        "combined_best_fnat",
        "combined_best_irmsd",
        "combined_best_lrmsd",
        "combined_best_global_rmsd",
        "combined_delta_fnat",
        "combined_delta_irmsd",
        "combined_delta_lrmsd",
        "combined_delta_global_rmsd",
        "combined_exact_satisfaction_median",
        "combined_union_satisfaction_median",
        "reference_exact_satisfaction_median",
        "reference_union_satisfaction_median",
        "nef_star_exact_identical",
        "nef_star_union_identical",
    ]
    rows = []
    for case in cases:
        scope = case["conversion"]["constraint_scope"]
        baseline = case["matched_baseline"]["best_of_10_best_of_ensemble"]

        def arm_best(arm):
            record = case["arms"][arm]
            if not record["applicable"]:
                return {}
            return record["analysis"]["best_of_10_best_of_ensemble"] or {}

        exact_best = arm_best("exact")
        union_best = arm_best("union")
        combined_best = arm_best("combined")
        effect = case["arms"]["combined"]["effect"]["best_of_10_deltas"]
        predicted_audit = case["arms"]["combined"]["analysis"][
            "restraint_audit_summary"
        ]
        reference_audit = case["conversion"]["reference_restraint_audit"][
            "summary"
        ]
        parity = case["conversion"]["format_parity"]
        rows.append(
            {
                "pdb_id": case["pdb_id"],
                "baseline_control": case["baseline_control"],
                "exact_constraints": scope["exact_total"],
                "exact_interchain": scope["exact_interchain"],
                "union_groups": scope["union_total"],
                "union_interchain_only": scope["union_interchain_only"],
                "baseline_best_class": baseline["capri_class"],
                "baseline_best_fnat": baseline["fnat"],
                "exact_best_class": exact_best.get("capri_class"),
                "exact_best_fnat": exact_best.get("fnat"),
                "union_best_class": union_best.get("capri_class"),
                "union_best_fnat": union_best.get("fnat"),
                "combined_best_class": combined_best.get("capri_class"),
                "combined_best_fnat": combined_best.get("fnat"),
                "combined_best_irmsd": combined_best.get(
                    "interface_backbone_rmsd"
                ),
                "combined_best_lrmsd": combined_best.get("ligand_rmsd"),
                "combined_best_global_rmsd": combined_best.get(
                    "global_backbone_rmsd"
                ),
                "combined_delta_fnat": effect.get("fnat"),
                "combined_delta_irmsd": effect.get(
                    "interface_backbone_rmsd"
                ),
                "combined_delta_lrmsd": effect.get("ligand_rmsd"),
                "combined_delta_global_rmsd": effect.get(
                    "global_backbone_rmsd"
                ),
                "combined_exact_satisfaction_median": predicted_audit[
                    "median_exact_fraction_satisfied_resolved"
                ],
                "combined_union_satisfaction_median": predicted_audit[
                    "median_union_fraction_satisfied_determinate"
                ],
                "reference_exact_satisfaction_median": reference_audit[
                    "median_exact_fraction_satisfied_resolved"
                ],
                "reference_union_satisfaction_median": reference_audit[
                    "median_union_fraction_satisfied_determinate"
                ],
                "nef_star_exact_identical": parity["exact"]["identical"],
                "nef_star_union_identical": parity["union"]["identical"],
            }
        )
    tsv_path = output_dir / "phase2_results.tsv"
    with tsv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    (output_dir / "CONCISE_REPORT.md").write_text(make_report(summary))
    print("Wrote {}".format(output_dir / "CONCISE_REPORT.md"))


if __name__ == "__main__":
    main()
