#!/usr/bin/env python3
"""Analyze the matched 8VOH token force:false/true attribution arms."""

from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PHASE2 = SCRIPT_DIR.parent
BENCHMARK = PHASE2.parent
CASE = PHASE2 / "cases" / "8voh"
sys.path.insert(0, str(SCRIPT_DIR))

import analyze_phase2 as phase2  # noqa: E402
import analyze_token_8voh as token  # noqa: E402


def strip_force(document):
    value = copy.deepcopy(document)
    for wrapper in value.get("constraints") or []:
        if isinstance(wrapper, dict) and isinstance(wrapper.get("contact"), dict):
            wrapper["contact"].pop("force", None)
    return value


def confidence_selected(analysis):
    candidates = [
        item
        for item in analysis.get("model_summaries", [])
        if item.get("confidence_score") is not None
    ]
    if not candidates:
        return None
    selected = max(candidates, key=lambda item: item["confidence_score"])
    return {
        key: selected.get(key)
        for key in (
            "prediction_model",
            "reference_model",
            "capri_class",
            "confidence_score",
            "iptm",
            "fnat",
            "contact_f1",
            "interface_backbone_rmsd",
            "ligand_rmsd",
            "global_backbone_rmsd",
            "prediction_file",
        )
    }


def main():
    candidate = token.load_json(CASE / "source" / "candidate.json")
    phase1_config = token.load_json(BENCHMARK / "config.json")
    false_input_path = CASE / "token" / "input" / "8voh_token.yaml"
    true_input_path = (
        CASE / "token_force_true" / "input" / "8voh_token_force_true.yaml"
    )
    false_document = token.load_yaml(false_input_path)
    true_document = token.load_yaml(true_input_path)
    constraints = token.token_contacts(true_document)
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
        reference_audits.append(token.audit_mapped(mapped, constraints, number))

    true_root = CASE / "token_force_true" / "results"
    true_analysis = phase2.analyze_prediction_root(
        true_root, references, candidate, phase1_config, true_document
    )
    if not true_analysis["technically_complete"]:
        raise RuntimeError(
            "Forced-token arm is incomplete: {}/10 models".format(
                true_analysis["prediction_models_compared"]
            )
        )

    analysis_dir = CASE / "token_force_true" / "analysis"
    phase2.write_json(
        analysis_dir / "all_comparisons.json", true_analysis["all_comparisons"]
    )
    true_compact = phase2.compact_analysis(true_analysis)
    phase2.write_json(analysis_dir / "classification.json", true_compact)

    analyses = {
        "unconstrained": token.load_json(CASE / "source" / "classification.json"),
        "exact": token.load_json(CASE / "exact" / "analysis" / "classification.json"),
        "union": token.load_json(CASE / "union" / "analysis" / "classification.json"),
        "combined": token.load_json(
            CASE / "combined" / "analysis" / "classification.json"
        ),
        "token_force_false": token.load_json(
            CASE / "token" / "analysis" / "classification.json"
        ),
        "token_force_true": true_compact,
    }
    roots = {
        "unconstrained": BENCHMARK / "candidates" / "8voh-passed" / "results",
        "exact": CASE / "exact" / "results",
        "union": CASE / "union" / "results",
        "combined": CASE / "combined" / "results",
        "token_force_false": CASE / "token" / "results",
        "token_force_true": true_root,
    }
    token_audits = {
        arm: token.audit_prediction_root(root, candidate, constraints)
        for arm, root in roots.items()
    }
    token_audits["reference"] = {
        "summary": token.aggregate_token_audits(reference_audits, len(constraints)),
        "models": reference_audits,
    }
    phase2.write_json(analysis_dir / "token_constraint_audits.json", token_audits)

    effects = {
        "token_force_true_vs_false": phase2.paired_effect(
            analyses["token_force_true"], analyses["token_force_false"]
        ),
        "token_force_true_vs_unconstrained": phase2.paired_effect(
            analyses["token_force_true"], analyses["unconstrained"]
        ),
        "combined_vs_token_force_true": phase2.paired_effect(
            analyses["combined"], analyses["token_force_true"]
        ),
        "exact_vs_token_force_true": phase2.paired_effect(
            analyses["exact"], analyses["token_force_true"]
        ),
        "token_force_true_vs_combined": phase2.paired_effect(
            analyses["token_force_true"], analyses["combined"]
        ),
    }
    phase2.write_json(analysis_dir / "paired_effect.json", effects)

    processed_root = (
        true_root
        / "boltz_results_8voh_token_force_true"
        / "processed"
    )
    manifest = token.load_json(processed_root / "manifest.json")
    inference = manifest["records"][0]["inference_options"]
    processed_contacts = inference.get("contact_constraints") or []
    prediction_dir = (
        true_root
        / "boltz_results_8voh_token_force_true"
        / "predictions"
        / "8voh_token_force_true"
    )
    false_contacts = token.token_contacts(false_document)
    validation_checks = {
        "inputs_differ_only_in_force": strip_force(false_document)
        == strip_force(true_document),
        "force_false_input_has_9_false_contacts": len(false_contacts) == 9
        and all(item["force"] is False for item in false_contacts),
        "force_true_input_has_9_true_contacts": len(constraints) == 9
        and all(item["force"] is True for item in constraints),
        "processed_token_contact_count_is_9": len(processed_contacts) == 9,
        "processed_token_contacts_are_all_forced": all(
            item[3] is True for item in processed_contacts
        ),
        "processed_exact_atom_contact_count_is_0": len(
            inference.get("atom_contact_constraints") or []
        )
        == 0,
        "processed_union_atom_contact_count_is_0": len(
            inference.get("atom_contact_union_constraints") or []
        )
        == 0,
        "prediction_pdb_count_is_10": len(
            list(prediction_dir.glob("*_model_*.pdb"))
        )
        == 10,
        "confidence_json_count_is_10": len(
            list(prediction_dir.glob("confidence_*_model_*.json"))
        )
        == 10,
        "pae_count_is_10": len(list(prediction_dir.glob("pae_*_model_*.npz")))
        == 10,
        "pde_count_is_10": len(list(prediction_dir.glob("pde_*_model_*.npz")))
        == 10,
        "plddt_count_is_10": len(list(prediction_dir.glob("plddt_*_model_*.npz")))
        == 10,
        "prediction_analysis_complete": true_analysis["technically_complete"],
        "reference_conformer_count_is_10": len(references) == 10,
        "reference_satisfies_all_generated_token_contacts": token_audits[
            "reference"
        ]["summary"]["overall_fraction_satisfied"]
        == 1.0,
    }
    validation = {
        "pdb_id": "8VOH",
        "passed": all(validation_checks.values()),
        "checks": validation_checks,
    }
    phase2.write_json(analysis_dir / "validation_report.json", validation)
    if not validation["passed"]:
        failed = [name for name, passed in validation_checks.items() if not passed]
        raise RuntimeError("Validation failed: {}".format(", ".join(failed)))

    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pdb_id": "8VOH",
        "interpretation": {
            "force_false": (
                "Token contact conditioning is active, but the coordinate potential "
                "is omitted."
            ),
            "force_true": (
                "The same token conditioning is active and a minimum-heavy-atom "
                "coordinate potential is added for each residue pair."
            ),
        },
        "design": {
            "reference_conformers": len(references),
            "prediction_samples_per_arm": 10,
            "seed": 1,
            "only_changed_field": "constraints[*].contact.force",
            "token_contacts": 9,
            "token_contacts_from_exact_groups": 6,
            "token_contacts_from_collapsed_union_groups": 3,
            "combined_internal_binary_token_contacts": 6,
            "attribution_caveat": (
                "The generated token arm includes three residue pairs collapsed from "
                "union groups. The combined atom arm supplies only the six exact groups "
                "to binary token conditioning; its union groups remain alternative atom "
                "potentials. Therefore this is a biologically matched comparison, not a "
                "strict component ablation with equal potential groups."
            ),
            "runtime_seconds": 916.1,
            "fixed_msa_sha256": [
                token.sha256(CASE / "source" / "msa" / "entity_0.csv"),
                token.sha256(CASE / "source" / "msa" / "entity_1.csv"),
            ],
        },
        "provenance": {
            "boltz_version": "2.2.1",
            "boltzui_image_id": (
                "sha256:15cdcac8e17fe16abc9756b2ff8673d99c7436ebe32f3d70b9e120024c445d83"
            ),
            "force_false_input_sha256": token.sha256(false_input_path),
            "force_true_input_sha256": token.sha256(true_input_path),
            "processed_manifest": manifest,
        },
        "arms": {},
        "reference_token_constraint_audit": token_audits["reference"]["summary"],
        "comparisons": effects,
    }
    for arm, analysis in analyses.items():
        report["arms"][arm] = token.arm_summary(analysis, token_audits[arm])
        report["arms"][arm]["confidence_selected"] = confidence_selected(analysis)
    phase2.write_json(analysis_dir / "comparison_summary.json", report)
    print(
        json.dumps(
            {
                "validation": validation,
                "force_true": report["arms"]["token_force_true"],
                "force_true_vs_false": effects["token_force_true_vs_false"],
                "combined_vs_force_true": effects["combined_vs_token_force_true"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
