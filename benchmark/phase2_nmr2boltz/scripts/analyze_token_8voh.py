#!/usr/bin/env python3
"""Analyze the matched 8VOH token-only attribution arm."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
PHASE2 = SCRIPT_DIR.parent
BENCHMARK = PHASE2.parent
CASE = PHASE2 / "cases" / "8voh"
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(BENCHMARK / "scripts"))

import analyze_phase2 as phase2  # noqa: E402
from structure_metrics import heavy_atom_coordinates  # noqa: E402


def load_json(path):
    with path.open("r") as handle:
        return json.load(handle)


def load_yaml(path):
    with path.open("r") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise RuntimeError("Expected a YAML mapping in {}".format(path))
    return value


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def token_contacts(document):
    output = []
    for wrapper in document.get("constraints") or []:
        if not isinstance(wrapper, dict) or "contact" not in wrapper:
            continue
        item = wrapper["contact"]
        output.append(
            {
                "token1": [str(item["token1"][0]), int(item["token1"][1])],
                "token2": [str(item["token2"][0]), int(item["token2"][1])],
                "max_distance": float(item["max_distance"]),
                "force": bool(item.get("force", False)),
            }
        )
    return output


def measure_token_contact(mapped, item):
    chain1, residue1 = item["token1"]
    chain2, residue2 = item["token2"]
    first = mapped.get(chain1, {}).get(residue1 - 1)
    second = mapped.get(chain2, {}).get(residue2 - 1)
    if first is None or second is None:
        return {
            **item,
            "resolved": False,
            "distance": None,
            "excess": None,
            "satisfied": None,
        }
    first_points = heavy_atom_coordinates(first)
    second_points = heavy_atom_coordinates(second)
    if not len(first_points) or not len(second_points):
        return {
            **item,
            "resolved": False,
            "distance": None,
            "excess": None,
            "satisfied": None,
        }
    differences = first_points[:, None, :] - second_points[None, :, :]
    distance = float(np.sqrt(np.min(np.sum(differences * differences, axis=2))))
    bound = float(item["max_distance"])
    return {
        **item,
        "resolved": True,
        "distance": distance,
        "excess": max(0.0, distance - bound),
        "satisfied": distance <= bound,
    }


def audit_mapped(mapped, constraints, model):
    measurements = [measure_token_contact(mapped, item) for item in constraints]
    resolved = [item for item in measurements if item["resolved"]]
    satisfied = [item for item in resolved if item["satisfied"]]
    return {
        "model": model,
        "total": len(measurements),
        "resolved": len(resolved),
        "satisfied": len(satisfied),
        "fraction_satisfied_resolved": (
            float(len(satisfied)) / len(resolved) if resolved else None
        ),
        "median_distance_angstrom": phase2.numeric_median(
            item["distance"] for item in resolved
        ),
        "median_excess_angstrom": phase2.numeric_median(
            item["excess"] for item in resolved
        ),
        "measurements": measurements,
    }


def aggregate_token_audits(audits, constraint_count):
    resolved = [
        item
        for audit in audits
        for item in audit["measurements"]
        if item["resolved"]
    ]
    per_constraint = []
    for index in range(constraint_count):
        measurements = [
            audit["measurements"][index]
            for audit in audits
            if audit["measurements"][index]["resolved"]
        ]
        satisfied = [item for item in measurements if item["satisfied"]]
        exemplar = audits[0]["measurements"][index] if audits else {}
        per_constraint.append(
            {
                "constraint_index": index + 1,
                "token1": exemplar.get("token1"),
                "token2": exemplar.get("token2"),
                "max_distance": exemplar.get("max_distance"),
                "resolved": len(measurements),
                "satisfied": len(satisfied),
                "fraction_satisfied": (
                    float(len(satisfied)) / len(measurements)
                    if measurements else None
                ),
                "median_distance_angstrom": phase2.numeric_median(
                    item["distance"] for item in measurements
                ),
            }
        )
    return {
        "models": len(audits),
        "constraints_per_model": constraint_count,
        "resolved_measurements": len(resolved),
        "satisfied_measurements": sum(item["satisfied"] for item in resolved),
        "overall_fraction_satisfied": (
            float(sum(item["satisfied"] for item in resolved)) / len(resolved)
            if resolved else None
        ),
        "median_model_fraction_satisfied": phase2.numeric_median(
            audit["fraction_satisfied_resolved"] for audit in audits
        ),
        "median_measurement_distance_angstrom": phase2.numeric_median(
            item["distance"] for item in resolved
        ),
        "median_measurement_excess_angstrom": phase2.numeric_median(
            item["excess"] for item in resolved
        ),
        "per_constraint": per_constraint,
    }


def audit_prediction_root(result_root, candidate, constraints):
    audits = []
    for predicted_path in phase2.predicted_pdb_files(str(result_root)):
        models = phase2.parse_pdb(predicted_path)
        if not models:
            continue
        mapped, _identities = phase2.map_model(models[0], candidate["chains"])
        audits.append(
            audit_mapped(mapped, constraints, phase2.model_index(predicted_path))
        )
    audits.sort(key=lambda item: item["model"])
    return {
        "summary": aggregate_token_audits(audits, len(constraints)),
        "models": audits,
    }


def metric_medians(analysis):
    stored = analysis.get("metric_medians") or {}
    return {
        metric: stored.get(metric)
        if stored.get(metric) is not None
        else phase2.numeric_median(
            item.get(metric) for item in analysis.get("model_summaries", [])
        )
        for metric in phase2.METRICS
    }


def arm_summary(analysis, token_audit):
    best = analysis.get("best_of_10_best_of_ensemble") or {}
    return {
        "prediction_models_compared": analysis.get("prediction_models_compared"),
        "reference_models_compared": analysis.get("reference_models_compared"),
        "capri_class_counts": analysis.get("capri_class_counts"),
        "best_of_10_best_of_ensemble": best,
        "metric_medians": metric_medians(analysis),
        "median_confidence": {
            key: phase2.numeric_median(
                item.get(key) for item in analysis.get("model_summaries", [])
            )
            for key in ("confidence_score", "ptm", "iptm", "complex_plddt")
        },
        "token_constraint_audit": token_audit["summary"],
    }


def main():
    candidate = load_json(CASE / "source" / "candidate.json")
    phase1_config = load_json(BENCHMARK / "config.json")
    token_input_path = CASE / "token" / "input" / "8voh_token.yaml"
    token_document = load_yaml(token_input_path)
    constraints = token_contacts(token_document)
    if len(constraints) != 9:
        raise RuntimeError("Expected 9 token contacts, found {}".format(len(constraints)))

    reference_models = phase2.parse_pdb(CASE / "source" / "8voh.pdb")
    usable = set(candidate["ensemble_profile"]["usable_model_numbers"])
    references = []
    reference_audits = []
    for number, model in enumerate(reference_models, start=1):
        if number not in usable:
            continue
        mapped, _identities = phase2.map_model(model, candidate["chains"])
        references.append((number, mapped))
        reference_audits.append(audit_mapped(mapped, constraints, number))

    token_analysis = phase2.analyze_prediction_root(
        CASE / "token" / "results",
        references,
        candidate,
        phase1_config,
        token_document,
    )
    if not token_analysis["technically_complete"]:
        raise RuntimeError(
            "Token arm is incomplete: {}/10 models".format(
                token_analysis["prediction_models_compared"]
            )
        )

    analysis_dir = CASE / "token" / "analysis"
    phase2.write_json(
        analysis_dir / "all_comparisons.json",
        token_analysis["all_comparisons"],
    )
    phase2.write_json(
        analysis_dir / "classification.json",
        phase2.compact_analysis(token_analysis),
    )

    analyses = {
        "unconstrained": load_json(CASE / "source" / "classification.json"),
        "exact": load_json(CASE / "exact" / "analysis" / "classification.json"),
        "union": load_json(CASE / "union" / "analysis" / "classification.json"),
        "combined": load_json(
            CASE / "combined" / "analysis" / "classification.json"
        ),
        "token": phase2.compact_analysis(token_analysis),
    }
    roots = {
        "unconstrained": BENCHMARK / "candidates" / "8voh-passed" / "results",
        "exact": CASE / "exact" / "results",
        "union": CASE / "union" / "results",
        "combined": CASE / "combined" / "results",
        "token": CASE / "token" / "results",
    }
    token_audits = {
        arm: audit_prediction_root(root, candidate, constraints)
        for arm, root in roots.items()
    }
    token_audits["reference"] = {
        "summary": aggregate_token_audits(reference_audits, len(constraints)),
        "models": reference_audits,
    }
    phase2.write_json(analysis_dir / "token_constraint_audits.json", token_audits)

    effects = {
        "token_vs_unconstrained": phase2.paired_effect(
            analyses["token"], analyses["unconstrained"]
        ),
        "exact_vs_unconstrained": phase2.paired_effect(
            analyses["exact"], analyses["unconstrained"]
        ),
        "union_vs_unconstrained": phase2.paired_effect(
            analyses["union"], analyses["unconstrained"]
        ),
        "combined_vs_unconstrained": phase2.paired_effect(
            analyses["combined"], analyses["unconstrained"]
        ),
        "combined_vs_token": phase2.paired_effect(
            analyses["combined"], analyses["token"]
        ),
        "combined_vs_exact": phase2.paired_effect(
            analyses["combined"], analyses["exact"]
        ),
        "combined_vs_union": phase2.paired_effect(
            analyses["combined"], analyses["union"]
        ),
        "token_vs_combined": phase2.paired_effect(
            analyses["token"], analyses["combined"]
        ),
        "exact_vs_token": phase2.paired_effect(
            analyses["exact"], analyses["token"]
        ),
    }
    phase2.write_json(analysis_dir / "paired_effect.json", effects)

    generated_constraints = CASE / "token" / "conversion" / "token_constraints.yaml"
    generated_document = load_yaml(generated_constraints)
    combined_document = load_yaml(CASE / "combined" / "input" / "8voh_combined.yaml")
    input_manifest = load_json(
        CASE
        / "token"
        / "results"
        / "boltz_results_8voh_token"
        / "processed"
        / "manifest.json"
    )
    inference_options = input_manifest["records"][0]["inference_options"]
    prediction_dir = (
        CASE
        / "token"
        / "results"
        / "boltz_results_8voh_token"
        / "predictions"
        / "8voh_token"
    )
    validation_checks = {
        "generated_constraints_match_prediction_input": (
            generated_document.get("constraints") == token_document.get("constraints")
        ),
        "sequence_and_msa_inputs_match_combined_arm": (
            token_document.get("sequences") == combined_document.get("sequences")
        ),
        "processed_token_contact_count_is_9": (
            len(inference_options.get("contact_constraints") or []) == 9
        ),
        "processed_exact_atom_contact_count_is_0": (
            len(inference_options.get("atom_contact_constraints") or []) == 0
        ),
        "processed_union_atom_contact_count_is_0": (
            len(inference_options.get("atom_contact_union_constraints") or []) == 0
        ),
        "prediction_pdb_count_is_10": len(list(prediction_dir.glob("*_model_*.pdb"))) == 10,
        "confidence_json_count_is_10": (
            len(list(prediction_dir.glob("confidence_*_model_*.json"))) == 10
        ),
        "pae_count_is_10": len(list(prediction_dir.glob("pae_*_model_*.npz"))) == 10,
        "pde_count_is_10": len(list(prediction_dir.glob("pde_*_model_*.npz"))) == 10,
        "plddt_count_is_10": len(list(prediction_dir.glob("plddt_*_model_*.npz"))) == 10,
        "prediction_analysis_complete": token_analysis["technically_complete"],
        "reference_conformer_count_is_10": len(references) == 10,
        "reference_satisfies_all_generated_token_contacts": (
            token_audits["reference"]["summary"]["overall_fraction_satisfied"] == 1.0
        ),
    }
    validation_report = {
        "pdb_id": "8VOH",
        "passed": all(validation_checks.values()),
        "checks": validation_checks,
    }
    phase2.write_json(analysis_dir / "validation_report.json", validation_report)
    if not validation_report["passed"]:
        failed = [name for name, passed in validation_checks.items() if not passed]
        raise RuntimeError("Validation failed: {}".format(", ".join(failed)))

    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pdb_id": "8VOH",
        "design": {
            "reference": "10 usable conformers from the deposited solution-NMR PDB ensemble",
            "prediction_samples_per_arm": 10,
            "seed": 1,
            "fixed_msa_sha256": [
                sha256(CASE / "source" / "msa" / "entity_0.csv"),
                sha256(CASE / "source" / "msa" / "entity_1.csv"),
            ],
            "token_contacts": 9,
            "token_contacts_from_exact_groups": 6,
            "token_contacts_from_collapsed_union_groups": 3,
            "combined_internal_binary_token_contacts": 6,
            "attribution_caveat": (
                "The generated token-only arm contains three collapsed-union token "
                "pairs that the combined atom arm intentionally does not add to binary "
                "token conditioning; therefore token-versus-combined is informative but "
                "not an exact component ablation."
            ),
        },
        "provenance": {
            "nmr2boltz_version": "0.1.0",
            "nmr2boltz_image_id": (
                "sha256:2e8fd2f26e7b6056ed1a04cf2029058837e1ef25f4c2cee89bfa2fb6d27bb40b"
            ),
            "boltz_version": "2.2.1",
            "boltzui_image_id": (
                "sha256:15cdcac8e17fe16abc9756b2ff8673d99c7436ebe32f3d70b9e120024c445d83"
            ),
            "generated_token_constraints_sha256": sha256(generated_constraints),
            "token_input_sha256": sha256(token_input_path),
            "processed_manifest": input_manifest,
            "runtime_seconds": 1061.5,
        },
        "arms": {
            arm: arm_summary(analysis, token_audits[arm])
            for arm, analysis in analyses.items()
        },
        "reference_token_constraint_audit": token_audits["reference"]["summary"],
        "comparisons": effects,
    }
    phase2.write_json(analysis_dir / "comparison_summary.json", report)
    print(json.dumps({
        "token_best": report["arms"]["token"]["best_of_10_best_of_ensemble"],
        "token_classes": report["arms"]["token"]["capri_class_counts"],
        "token_medians": report["arms"]["token"]["metric_medians"],
        "token_contact_audit": report["arms"]["token"]["token_constraint_audit"],
        "combined_vs_token": effects["combined_vs_token"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
