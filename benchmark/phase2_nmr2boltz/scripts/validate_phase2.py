#!/usr/bin/env python3
"""Fail-closed validation of the complete phase-2 benchmark."""

import hashlib
import json
from pathlib import Path
import re
import sys

import yaml


PHASE2 = Path(__file__).resolve().parents[1]
BENCHMARK = PHASE2.parent
SUMMARY = PHASE2 / "summary"


def load_json(path):
    with path.open("r") as handle:
        return json.load(handle)


def load_yaml(path):
    with path.open("r") as handle:
        value = yaml.safe_load(handle)
    return value if isinstance(value, dict) else {}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def constraint_counts(document):
    exact = 0
    union = 0
    for item in document.get("constraints") or []:
        if "atom_contact" in item:
            exact += 1
        elif "atom_contact_union" in item:
            union += 1
    return exact, union


def model_indices(result_directory):
    indices = []
    for path in result_directory.rglob("*_model_*.pdb"):
        match = re.search(r"_model_(\d+)", path.name)
        if match:
            indices.append(int(match.group(1)))
    return sorted(indices)


def main():
    errors = []
    warnings = []
    checks = []

    def check(condition, name, detail=None):
        checks.append(
            {
                "name": name,
                "passed": bool(condition),
                "detail": detail,
            }
        )
        if not condition:
            errors.append("{}{}".format(name, ": {}".format(detail) if detail else ""))

    config = load_json(PHASE2 / "config.json")
    phase1 = load_json(BENCHMARK / "config.json")
    check(
        config["prediction"]["arguments"]
        == phase1["runtime"]["prediction_arguments"],
        "prediction_arguments_match_phase1_exactly",
    )
    check(len(config["pdb_ids"]) == 10, "ten_prespecified_entries")

    nmr_sif = Path(config["conversion"]["nmr2boltz_sif"])
    boltz_sif = Path(config["prediction"]["boltz_sif"])
    check(nmr_sif.is_file(), "nmr2boltz_sif_present")
    check(boltz_sif.is_file(), "boltz_sif_present")
    if nmr_sif.is_file():
        check(
            sha256(nmr_sif) == config["conversion"]["nmr2boltz_sif_sha256"],
            "nmr2boltz_sif_digest",
        )
    if boltz_sif.is_file():
        check(
            sha256(boltz_sif) == config["prediction"]["boltz_sif_sha256"],
            "boltz_sif_digest",
        )

    command_count = 0
    constrained_run_count = 0
    for pdb_upper in config["pdb_ids"]:
        pdb_id = pdb_upper.lower()
        case = PHASE2 / "cases" / pdb_id
        check(case.is_dir(), "{}_case_present".format(pdb_upper))
        manifest = load_json(case / "case_manifest.json")
        check(
            manifest["pdb_id"] == pdb_upper,
            "{}_case_manifest_id".format(pdb_upper),
        )
        for label, record in manifest["files"].items():
            path = PHASE2 / record["phase2_path"]
            check(path.is_file(), "{}_{}_present".format(pdb_upper, label))
            if path.is_file():
                check(
                    sha256(path) == record["sha256"],
                    "{}_{}_digest".format(pdb_upper, label),
                )

        for source_format in ("nef", "nmr_star"):
            conversion = case / "conversion" / source_format
            required = (
                "atom_constraints_exact.yaml",
                "atom_constraints_union.yaml",
                "conversion_report.json",
                "sequence_map.tsv",
                "rejections.tsv",
                "summary.txt",
            )
            for name in required:
                check(
                    (conversion / name).is_file(),
                    "{}_{}_{}".format(pdb_upper, source_format, name),
                )
            report = load_json(conversion / "conversion_report.json")
            target = report.get("target_validation") or {}
            check(
                target.get("error_count") == 0,
                "{}_{}_target_validation".format(pdb_upper, source_format),
                target,
            )
            check(
                report["statistics"].get("emitted_atom_topology_violations") == 0,
                "{}_{}_topology_invariant".format(pdb_upper, source_format),
            )

        build = load_json(case / "build_summary.json")
        check(
            build["exact_constraint_count"] > 0,
            "{}_nonempty_exact_set".format(pdb_upper),
        )
        if pdb_upper == "9KAD":
            check(
                build["union_group_count"] == 0,
                "9KAD_union_absence_audited",
            )
        else:
            check(
                build["union_group_count"] > 0,
                "{}_nonempty_union_set".format(pdb_upper),
            )

        for arm in config["prediction"]["arms"]:
            arm_dir = case / arm
            arm_manifest = load_json(arm_dir / "arm_manifest.json")
            input_path = PHASE2 / arm_manifest["input_file"]
            check(input_path.is_file(), "{}_{}_input".format(pdb_upper, arm))
            exact, union = constraint_counts(load_yaml(input_path))
            check(
                exact == arm_manifest["exact_constraints"],
                "{}_{}_exact_count".format(pdb_upper, arm),
            )
            check(
                union == arm_manifest["union_groups"],
                "{}_{}_union_count".format(pdb_upper, arm),
            )
            if not arm_manifest["applicable"]:
                check(
                    not (arm_dir / "command.json").exists(),
                    "{}_{}_nonapplicable_no_command".format(pdb_upper, arm),
                )
                continue

            command_count += 1
            constrained_run_count += 1
            command = load_json(arm_dir / "command.json")
            args = command["arguments"]
            check(
                args[0] == "predict"
                and args[2] == "--out_dir"
                and args[4:6] == ["--cache", "/opt/boltz-cache"]
                and args[6:] == config["prediction"]["arguments"],
                "{}_{}_command_arguments".format(pdb_upper, arm),
            )
            status_path = arm_dir / "logs" / "execution_status.json"
            check(
                status_path.is_file(),
                "{}_{}_execution_status".format(pdb_upper, arm),
            )
            if status_path.is_file():
                status = load_json(status_path)
                check(
                    status.get("exit_code") == 0,
                    "{}_{}_exit_zero".format(pdb_upper, arm),
                    status,
                )
                check(
                    status.get("restraint_audit_exit_code") == 0,
                    "{}_{}_audit_exit_zero".format(pdb_upper, arm),
                    status,
                )
            result = (
                arm_dir
                / "results"
                / "boltz_results_{}_{}".format(pdb_id, arm)
            )
            check(
                model_indices(result) == list(range(10)),
                "{}_{}_ten_models".format(pdb_upper, arm),
                model_indices(result),
            )
            audit_path = result / "atom_contact_restraints.json"
            check(
                audit_path.is_file(),
                "{}_{}_restraint_audit".format(pdb_upper, arm),
            )
            if audit_path.is_file():
                audit = load_json(audit_path)
                check(
                    audit.get("schema_version") == 3
                    and len(audit.get("model_summaries", [])) == 10,
                    "{}_{}_restraint_audit_schema".format(pdb_upper, arm),
                )
                check(
                    len(audit.get("restraints", [])) == exact
                    and len(audit.get("union_groups", [])) == union,
                    "{}_{}_restraint_audit_counts".format(pdb_upper, arm),
                )
            analysis = arm_dir / "analysis" / "classification.json"
            check(
                analysis.is_file(),
                "{}_{}_structural_analysis".format(pdb_upper, arm),
            )
            if analysis.is_file():
                value = load_json(analysis)
                check(
                    value.get("technically_complete")
                    and value.get("prediction_models_compared") == 10,
                    "{}_{}_analysis_complete".format(pdb_upper, arm),
                )

        if pdb_upper == "8Q5Q":
            control = case / "modified_unconstrained"
            command_count += 1
            input_doc = load_yaml(
                control / "input" / "8q5q_modified_unconstrained.yaml"
            )
            check(
                constraint_counts(input_doc) == (0, 0),
                "8Q5Q_modified_control_unconstrained",
            )
            dna = input_doc["sequences"][0]["dna"]
            check(
                dna.get("modifications")
                == [{"ccd": "DNR", "position": 5}],
                "8Q5Q_DNR_declared",
                dna.get("modifications"),
            )
            ccd = case / "source" / "DNR.cif"
            check(ccd.is_file(), "8Q5Q_DNR_CCD_present")
            status = load_json(control / "logs" / "execution_status.json")
            check(status.get("exit_code") == 0, "8Q5Q_modified_control_exit_zero")
            result = (
                control
                / "results"
                / "boltz_results_8q5q_modified_unconstrained"
            )
            check(
                model_indices(result) == list(range(10)),
                "8Q5Q_modified_control_ten_models",
            )
            check(
                (control / "analysis" / "classification.json").is_file(),
                "8Q5Q_modified_control_analysis",
            )

    check(command_count == 30, "thirty_executed_commands", command_count)
    check(
        constrained_run_count == 29,
        "twenty_nine_applicable_constrained_runs",
        constrained_run_count,
    )
    for name in ("phase2_results.json", "phase2_results.tsv", "CONCISE_REPORT.md"):
        check((SUMMARY / name).is_file(), "summary_{}_present".format(name))
    if (SUMMARY / "phase2_results.json").is_file():
        results = load_json(SUMMARY / "phase2_results.json")
        check(len(results.get("cases", [])) == 10, "summary_has_ten_cases")
        check(
            set(results.get("aggregate", {})) == {"exact", "union", "combined"},
            "summary_has_three_arms",
        )

    report = {
        "schema_version": 1,
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "counts": {
            "entries": len(config["pdb_ids"]),
            "commands": command_count,
            "applicable_constrained_runs": constrained_run_count,
        },
    }
    write_json(SUMMARY / "validation_report.json", report)
    print(json.dumps(report["counts"], sort_keys=True))
    print("VALID" if report["valid"] else "INVALID: {} errors".format(len(errors)))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
