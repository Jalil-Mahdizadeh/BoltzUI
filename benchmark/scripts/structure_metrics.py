#!/usr/bin/env python3
"""PDB parsing, sequence mapping, symmetry handling, and CAPRI-like metrics."""

from __future__ import print_function

import itertools
import math
import os

import numpy as np


AMINO_ACIDS = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "MSE": "M", "SEC": "C", "PYL": "K"
}
RNA_RESIDUES = {
    "A": "A", "C": "C", "G": "G", "U": "U",
    "RA": "A", "RC": "C", "RG": "G", "RU": "U",
    "ADE": "A", "CYT": "C", "GUA": "G", "URA": "U"
}
DNA_RESIDUES = {
    "DA": "A", "DC": "C", "DG": "G", "DT": "T",
    "A": "A", "C": "C", "G": "G", "T": "T",
    "ADE": "A", "CYT": "C", "GUA": "G", "THY": "T"
}

CAPRI_RANK = {"incorrect": 0, "acceptable": 1, "medium": 2, "high": 3}


def normalize_atom_name(name):
    return str(name).strip().replace("*", "'")


def residue_letter(resname, polymer_type):
    name = str(resname).strip().upper()
    if polymer_type == "polypeptide(L)":
        return AMINO_ACIDS.get(name, "X")
    if polymer_type == "polyribonucleotide":
        return RNA_RESIDUES.get(name, "X")
    if polymer_type == "polydeoxyribonucleotide":
        return DNA_RESIDUES.get(name, "X")
    return "X"


def anchor_names(polymer_type):
    if polymer_type == "polypeptide(L)":
        return ("N", "CA", "C")
    return ("P", "C4'", "C1'")


def representative_names(polymer_type):
    if polymer_type == "polypeptide(L)":
        return ("CB", "CA")
    return ("C4'", "P", "C1'")


def parse_pdb(path):
    """Parse coordinate models while preserving chain/residue order."""
    models = []
    current = {}
    saw_model = False

    def finish_model():
        if current:
            models.append({
                chain_id: list(chain["residues"])
                for chain_id, chain in current.items()
            })

    with open(path, "r") as handle:
        for line in handle:
            record = line[0:6].strip()
            if record == "MODEL":
                if current:
                    finish_model()
                    current = {}
                saw_model = True
                continue
            if record == "ENDMDL":
                finish_model()
                current = {}
                continue
            if record not in ("ATOM", "HETATM"):
                continue

            atom_name = normalize_atom_name(line[12:16])
            alt = line[16:17].strip()
            if alt not in ("", "A", "1"):
                continue
            resname = line[17:20].strip().upper()
            chain_id = line[21:22].strip()
            resseq_text = line[22:26].strip()
            insertion = line[26:27].strip()
            try:
                resseq = int(resseq_text)
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except ValueError:
                continue
            if not chain_id or not atom_name:
                continue
            element = line[76:78].strip().upper()
            if not element:
                element = atom_name.lstrip("0123456789")[0:1].upper()

            if chain_id not in current:
                current[chain_id] = {"lookup": {}, "residues": []}
            chain = current[chain_id]
            key = (resseq, insertion)
            if key not in chain["lookup"]:
                residue = {
                    "resseq": resseq,
                    "insertion": insertion,
                    "resname": resname,
                    "atoms": {},
                    "elements": {}
                }
                chain["lookup"][key] = residue
                chain["residues"].append(residue)
            residue = chain["lookup"][key]
            if atom_name not in residue["atoms"] or alt in ("", "A", "1"):
                residue["atoms"][atom_name] = np.array([x, y, z], dtype=float)
                residue["elements"][atom_name] = element

    if current:
        finish_model()
    if not models and not saw_model:
        return []
    return models


def align_observed_to_reference(observed, reference):
    """Needleman-Wunsch mapping from each observed residue to a reference index."""
    n = len(observed)
    m = len(reference)
    match_score = 2
    mismatch_score = -1
    gap_score = -2
    scores = np.zeros((n + 1, m + 1), dtype=np.int32)
    trace = np.zeros((n + 1, m + 1), dtype=np.int8)
    for i in range(1, n + 1):
        scores[i, 0] = i * gap_score
        trace[i, 0] = 1
    for j in range(1, m + 1):
        scores[0, j] = j * gap_score
        trace[0, j] = 2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diagonal = scores[i - 1, j - 1] + (
                match_score if observed[i - 1] == reference[j - 1] else mismatch_score
            )
            up = scores[i - 1, j] + gap_score
            left = scores[i, j - 1] + gap_score
            best = max(diagonal, up, left)
            scores[i, j] = best
            trace[i, j] = 0 if diagonal == best else (1 if up == best else 2)

    mapping = [None] * n
    matches = 0
    aligned = 0
    i = n
    j = m
    while i > 0 or j > 0:
        direction = trace[i, j]
        if i > 0 and j > 0 and direction == 0:
            mapping[i - 1] = j - 1
            aligned += 1
            if observed[i - 1] == reference[j - 1]:
                matches += 1
            i -= 1
            j -= 1
        elif i > 0 and (j == 0 or direction == 1):
            i -= 1
        else:
            j -= 1
    identity = float(matches) / aligned if aligned else 0.0
    return mapping, identity


def map_model(model, chain_specs):
    """Map observed residues in a model onto zero-based full-sequence positions."""
    mapped = {}
    identities = {}
    for spec in chain_specs:
        chain_id = spec["auth_asym_id"]
        residues = model.get(chain_id, [])
        observed = "".join(
            residue_letter(residue["resname"], spec["polymer_type"])
            for residue in residues
        )
        indices, identity = align_observed_to_reference(observed, spec["sequence"])
        mapped_chain = {}
        for residue, index in zip(residues, indices):
            if index is not None and index not in mapped_chain:
                mapped_chain[index] = residue
        mapped[chain_id] = mapped_chain
        identities[chain_id] = identity
    return mapped, identities


def residue_has_anchor(residue, polymer_type):
    return any(name in residue["atoms"] for name in anchor_names(polymer_type))


def mapped_anchor_coverage(mapped, chain_specs):
    output = {}
    for spec in chain_specs:
        chain_id = spec["auth_asym_id"]
        count = sum(
            1 for residue in mapped.get(chain_id, {}).values()
            if residue_has_anchor(residue, spec["polymer_type"])
        )
        output[chain_id] = (
            float(count) / len(spec["sequence"]) if spec["sequence"] else 0.0
        )
    return output


def symmetry_assignments(chain_specs):
    """Return canonical-chain -> observed-chain assignments."""
    chain_ids = [spec["auth_asym_id"] for spec in chain_specs]
    signatures = {
        spec["auth_asym_id"]: (spec["polymer_type"], spec["sequence"])
        for spec in chain_specs
    }
    assignments = []
    for permutation in itertools.permutations(chain_ids):
        assignment = dict(zip(chain_ids, permutation))
        if all(
            signatures[canonical] == signatures[observed]
            for canonical, observed in assignment.items()
        ):
            assignments.append(assignment)
    return assignments or [{chain_id: chain_id for chain_id in chain_ids}]


def collect_anchor_pairs(
    reference_mapped,
    mobile_mapped,
    chain_specs,
    assignment,
    selected_positions=None
):
    reference_points = []
    mobile_points = []
    labels = []
    for spec in chain_specs:
        canonical = spec["auth_asym_id"]
        observed = assignment[canonical]
        reference_chain = reference_mapped.get(canonical, {})
        mobile_chain = mobile_mapped.get(observed, {})
        common = sorted(set(reference_chain) & set(mobile_chain))
        if selected_positions is not None:
            common = [
                index for index in common
                if index in selected_positions.get(canonical, set())
            ]
        for index in common:
            reference_residue = reference_chain[index]
            mobile_residue = mobile_chain[index]
            for atom_name in anchor_names(spec["polymer_type"]):
                if (
                    atom_name in reference_residue["atoms"]
                    and atom_name in mobile_residue["atoms"]
                ):
                    reference_points.append(reference_residue["atoms"][atom_name])
                    mobile_points.append(mobile_residue["atoms"][atom_name])
                    labels.append((canonical, index, atom_name))
    if not reference_points:
        return np.empty((0, 3)), np.empty((0, 3)), []
    return (
        np.asarray(reference_points, dtype=float),
        np.asarray(mobile_points, dtype=float),
        labels
    )


def fit_transform(mobile, reference):
    if len(mobile) != len(reference) or len(mobile) < 3:
        return None
    mobile_center = mobile.mean(axis=0)
    reference_center = reference.mean(axis=0)
    mobile_zero = mobile - mobile_center
    reference_zero = reference - reference_center
    covariance = np.dot(mobile_zero.T, reference_zero)
    left, singular, right_t = np.linalg.svd(covariance)
    rotation = np.dot(left, right_t)
    if np.linalg.det(rotation) < 0:
        left[:, -1] *= -1
        rotation = np.dot(left, right_t)
    return {
        "rotation": rotation,
        "mobile_center": mobile_center,
        "reference_center": reference_center,
        "singular_values": singular
    }


def apply_transform(points, transform):
    return np.dot(points - transform["mobile_center"], transform["rotation"]) + (
        transform["reference_center"]
    )


def point_rmsd(first, second):
    if len(first) != len(second) or len(first) == 0:
        return None
    return float(np.sqrt(np.mean(np.sum((first - second) ** 2, axis=1))))


def fitted_rmsd(reference, mobile):
    transform = fit_transform(mobile, reference)
    if transform is None:
        return None
    return point_rmsd(reference, apply_transform(mobile, transform))


def heavy_atom_coordinates(residue):
    points = []
    for atom_name, coordinate in residue["atoms"].items():
        element = residue.get("elements", {}).get(atom_name, "")
        if element == "H" or atom_name.upper().startswith("H"):
            continue
        points.append(coordinate)
    return np.asarray(points, dtype=float) if points else np.empty((0, 3))


def contact_set(mapped, chain_specs, assignment, cutoff):
    if len(chain_specs) != 2:
        raise ValueError("CAPRI-like contact metrics require exactly two chains.")
    first_spec, second_spec = chain_specs
    first_canonical = first_spec["auth_asym_id"]
    second_canonical = second_spec["auth_asym_id"]
    first_chain = mapped.get(assignment[first_canonical], {})
    second_chain = mapped.get(assignment[second_canonical], {})
    contacts = set()
    cutoff_squared = float(cutoff) ** 2
    for first_index, first_residue in first_chain.items():
        first_points = heavy_atom_coordinates(first_residue)
        if not len(first_points):
            continue
        for second_index, second_residue in second_chain.items():
            second_points = heavy_atom_coordinates(second_residue)
            if not len(second_points):
                continue
            differences = first_points[:, None, :] - second_points[None, :, :]
            if np.any(np.sum(differences * differences, axis=2) <= cutoff_squared):
                contacts.add((first_index, second_index))
    return contacts


def interface_positions(native_contacts, chain_specs):
    first = chain_specs[0]["auth_asym_id"]
    second = chain_specs[1]["auth_asym_id"]
    return {
        first: set(item[0] for item in native_contacts),
        second: set(item[1] for item in native_contacts)
    }


def capri_class(fnat, lrmsd, irmsd, classification):
    for tier in ("high", "medium", "acceptable"):
        settings = classification[tier]
        if (
            fnat >= float(settings["minimum_fnat"])
            and (
                (lrmsd is not None and lrmsd <= float(settings["maximum_lrmsd_angstrom"]))
                or (
                    irmsd is not None
                    and irmsd <= float(settings["maximum_irmsd_angstrom"])
                )
            )
        ):
            return tier
    return "incorrect"


def compare_models(
    reference_mapped,
    mobile_mapped,
    chain_specs,
    cutoff,
    classification
):
    best = None
    identity = {spec["auth_asym_id"]: spec["auth_asym_id"] for spec in chain_specs}
    native_contacts = contact_set(reference_mapped, chain_specs, identity, cutoff)
    selected = interface_positions(native_contacts, chain_specs)
    if len(chain_specs[0]["sequence"]) >= len(chain_specs[1]["sequence"]):
        receptor_spec, ligand_spec = chain_specs[0], chain_specs[1]
    else:
        receptor_spec, ligand_spec = chain_specs[1], chain_specs[0]
    receptor_id = receptor_spec["auth_asym_id"]
    ligand_id = ligand_spec["auth_asym_id"]

    for assignment in symmetry_assignments(chain_specs):
        predicted_contacts = contact_set(
            mobile_mapped, chain_specs, assignment, cutoff
        )
        recovered = len(native_contacts & predicted_contacts)
        fnat = float(recovered) / len(native_contacts) if native_contacts else 0.0
        precision = (
            float(recovered) / len(predicted_contacts) if predicted_contacts else 0.0
        )
        contact_f1 = (
            2.0 * fnat * precision / (fnat + precision)
            if fnat + precision else 0.0
        )

        reference_global, mobile_global, labels = collect_anchor_pairs(
            reference_mapped, mobile_mapped, chain_specs, assignment
        )
        global_rmsd = fitted_rmsd(reference_global, mobile_global)

        reference_interface, mobile_interface, interface_labels = collect_anchor_pairs(
            reference_mapped,
            mobile_mapped,
            chain_specs,
            assignment,
            selected_positions=selected
        )
        irmsd = fitted_rmsd(reference_interface, mobile_interface)

        receptor_positions = {
            spec["auth_asym_id"]: (
                set(reference_mapped.get(spec["auth_asym_id"], {}))
                if spec["auth_asym_id"] == receptor_id else set()
            )
            for spec in chain_specs
        }
        ligand_positions = {
            spec["auth_asym_id"]: (
                set(reference_mapped.get(spec["auth_asym_id"], {}))
                if spec["auth_asym_id"] == ligand_id else set()
            )
            for spec in chain_specs
        }
        reference_receptor, mobile_receptor, receptor_labels = collect_anchor_pairs(
            reference_mapped,
            mobile_mapped,
            chain_specs,
            assignment,
            selected_positions=receptor_positions
        )
        reference_ligand, mobile_ligand, ligand_labels = collect_anchor_pairs(
            reference_mapped,
            mobile_mapped,
            chain_specs,
            assignment,
            selected_positions=ligand_positions
        )
        receptor_transform = fit_transform(mobile_receptor, reference_receptor)
        lrmsd = (
            point_rmsd(
                reference_ligand,
                apply_transform(mobile_ligand, receptor_transform)
            )
            if receptor_transform is not None and len(mobile_ligand) else None
        )

        chain_rmsds = {}
        for spec in chain_specs:
            canonical = spec["auth_asym_id"]
            positions = {
                item["auth_asym_id"]: (
                    set(reference_mapped.get(canonical, {}))
                    if item["auth_asym_id"] == canonical else set()
                )
                for item in chain_specs
            }
            ref_chain, mob_chain, chain_labels = collect_anchor_pairs(
                reference_mapped,
                mobile_mapped,
                chain_specs,
                assignment,
                selected_positions=positions
            )
            chain_rmsds[canonical] = fitted_rmsd(ref_chain, mob_chain)

        tier = capri_class(fnat, lrmsd, irmsd, classification)
        result = {
            "capri_class": tier,
            "capri_rank": CAPRI_RANK[tier],
            "fnat": fnat,
            "contact_precision": precision,
            "contact_f1": contact_f1,
            "native_contact_count": len(native_contacts),
            "predicted_contact_count": len(predicted_contacts),
            "recovered_native_contacts": recovered,
            "global_backbone_rmsd": global_rmsd,
            "interface_backbone_rmsd": irmsd,
            "ligand_rmsd": lrmsd,
            "chain_backbone_rmsd": chain_rmsds,
            "global_anchor_count": len(labels),
            "interface_anchor_count": len(interface_labels),
            "receptor_anchor_count": len(receptor_labels),
            "ligand_anchor_count": len(ligand_labels),
            "receptor_chain": receptor_id,
            "ligand_chain": ligand_id,
            "assignment": assignment
        }
        score = (
            -result["capri_rank"],
            -(result["fnat"]),
            result["interface_backbone_rmsd"]
            if result["interface_backbone_rmsd"] is not None else float("inf"),
            result["ligand_rmsd"]
            if result["ligand_rmsd"] is not None else float("inf"),
            result["global_backbone_rmsd"]
            if result["global_backbone_rmsd"] is not None else float("inf")
        )
        if best is None or score < best[0]:
            best = (score, result)
    return best[1] if best else None


def ensemble_profile(models, chain_specs, cutoff):
    mapped_models = []
    model_records = []
    for model_index, model in enumerate(models, start=1):
        mapped, identities = map_model(model, chain_specs)
        coverage = mapped_anchor_coverage(mapped, chain_specs)
        record = {
            "model": model_index,
            "sequence_identity": identities,
            "anchor_coverage": coverage,
            "usable": all(
                identities.get(spec["auth_asym_id"], 0.0) >= 0.90
                and coverage.get(spec["auth_asym_id"], 0.0) >= 0.90
                for spec in chain_specs
            )
        }
        model_records.append(record)
        if record["usable"]:
            mapped_models.append((model_index, mapped))

    if len(mapped_models) < 2:
        return {
            "models_total": len(models),
            "models_usable": len(mapped_models),
            "model_records": model_records,
            "error": "fewer_than_two_usable_models"
        }

    assignments = symmetry_assignments(chain_specs)
    count = len(mapped_models)
    distances = np.zeros((count, count), dtype=float)
    distances.fill(np.nan)
    for first_index in range(count):
        distances[first_index, first_index] = 0.0
        for second_index in range(first_index + 1, count):
            reference = mapped_models[first_index][1]
            mobile = mapped_models[second_index][1]
            values = []
            for assignment in assignments:
                reference_points, mobile_points, labels = collect_anchor_pairs(
                    reference, mobile, chain_specs, assignment
                )
                value = fitted_rmsd(reference_points, mobile_points)
                if value is not None:
                    values.append(value)
            distance = min(values) if values else float("nan")
            distances[first_index, second_index] = distance
            distances[second_index, first_index] = distance

    median_by_model = []
    for row in distances:
        finite = row[np.isfinite(row)]
        median_by_model.append(float(np.median(finite)) if len(finite) else float("inf"))
    medoid_index = int(np.argmin(median_by_model))
    medoid_model = mapped_models[medoid_index][0]
    medoid_distances = distances[medoid_index]
    finite_medoid = medoid_distances[np.isfinite(medoid_distances)]

    identity = {spec["auth_asym_id"]: spec["auth_asym_id"] for spec in chain_specs}
    contact_counts = [
        len(contact_set(mapped, chain_specs, identity, cutoff))
        for model_index, mapped in mapped_models
    ]
    return {
        "models_total": len(models),
        "models_usable": len(mapped_models),
        "model_records": model_records,
        "usable_model_numbers": [item[0] for item in mapped_models],
        "medoid_model": medoid_model,
        "medoid_backbone_rmsd_mean": float(np.mean(finite_medoid)),
        "medoid_backbone_rmsd_median": float(np.median(finite_medoid)),
        "medoid_backbone_rmsd_p90": float(np.percentile(finite_medoid, 90)),
        "medoid_backbone_rmsd_maximum": float(np.max(finite_medoid)),
        "native_contact_count_minimum": int(min(contact_counts)),
        "native_contact_count_median": float(np.median(contact_counts)),
        "native_contact_count_maximum": int(max(contact_counts)),
        "mapped_models": mapped_models
    }


def serializable_ensemble_profile(profile):
    return {
        key: value for key, value in profile.items()
        if key != "mapped_models"
    }


def predicted_pdb_files(result_directory):
    output = []
    for root, directories, files in os.walk(result_directory):
        for name in files:
            if name.lower().endswith(".pdb") and "_model_" in name:
                output.append(os.path.join(root, name))
    return sorted(output)
