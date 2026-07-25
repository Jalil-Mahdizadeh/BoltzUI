#!/usr/bin/env python3
"""Patch Boltz 2.2.1 atom/interface contacts and diffusion sample chunking."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import py_compile
from pathlib import Path

import boltz
import boltz.data.feature.featurizerv2 as featurizerv2
import boltz.data.module.inferencev2 as inferencev2
import boltz.data.parse.schema as schema
import boltz.data.types as types
import boltz.model.modules.diffusionv2 as diffusionv2
import boltz.model.potentials.potentials as potentials


EXPECTED_BOLTZ_VERSION = "2.2.1"
EXPECTED_SOURCE_SHA256 = {
    "schema.py": "c0dae4c89c4c4a22175a433b5a0c68860329d2a292c76224328bdde19b73b743",
    "types.py": "e7e5ede40e0c208bcb966acd04caebb3b017e8a50b85b1aa3cae4cdf83b71707",
    "inferencev2.py": "675235dff103d698dc65f2ebaca85a62b664ab28cd09f4b1c0166e6e56b47db4",
    "featurizerv2.py": "af1f9e6ec0c3d7289eb1f7503c3c1c3ee0d9f03436778dd4a7d412b8f7bd9f94",
    "diffusionv2.py": "9eacc8cf7daeb62dffa81a09a1f93d2e268a4b7b68b5b88c2058c5ebf5ca4057",
    "potentials.py": "1e4a79f1454e5a71ca5a3eb82fca5451a7dc2bed8a45df9f0a814f62a6219f38",
}
PATCH_MARKERS = {
    "schema.py": (
        "atom_contact_constraints",
        "atom_contact_union_constraints",
        "def atom_contact_spec_to_ids",
    ),
    "types.py": ("atom_contact_constraints", "atom_contact_union_constraints"),
    "inferencev2.py": ("atom_contact_constraints", "atom_contact_union_constraints"),
    "featurizerv2.py": (
        "inference_atom_contact_constraints",
        "inference_atom_contact_union_constraints",
    ),
    "diffusionv2.py": ("sample_ids.split(max_parallel_samples)",),
    "potentials.py": (
        "def hard_union_reduction",
        "class InterfaceContactPotentital",
    ),
}
INTERFACE_PATCH_MARKERS = {
    "schema.py": (
        "interface_contact_constraints",
        "def interface_patch_to_ids",
    ),
    "types.py": ("interface_contact_constraints",),
    "inferencev2.py": ("interface_contact_constraints",),
    "featurizerv2.py": (
        "inference_interface_contact_constraints",
        "def apply_interface_contact_potentials",
    ),
}
INTERFACE_FEATURES_V2_MARKER = '"interface_contact_pair_weights"'
INTERFACE_FEATURES_CYCLIC_MARKER = "cyclic_period_by_chain"
INTERFACE_FEATURES_CROP_MARKER = "lost forced active residue(s) during cropping"
INTERFACE_FEATURES_AIR_MARKER = "literal_threshold = float(max_distance)"
INTERFACE_POTENTIALS_V2_MARKER = "class InterfaceClashPotentital"
INTERFACE_POTENTIALS_RESAMPLING_MARKER = (
    "# Reciprocal per-active-residue AIR energy participates in particle resampling."
)
INTERFACE_POTENTIALS_AIR_MARKER = (
    'parameters.get("gradient_strength", 4.0)'
)
INTERFACE_POTENTIALS_AIR_REGISTRATION_MARKER = '"huber_delta": 2.0'
INTERFACE_SCHEMA_V2_MARKER = "seen_interface_contacts = {}"
INTERFACE_SCHEMA_NEIGHBOR_MARKER = (
    "patch1_without_target = ["
)
INTERFACE_FAILURE_PROPAGATION_MARKER = (
    "if interface_contact_constraints:\n                raise"
)


def source_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_compatibility(paths: dict[str, Path]) -> None:
    version = getattr(boltz, "__version__", "unknown")
    if version != EXPECTED_BOLTZ_VERSION:
        raise RuntimeError(
            f"Expected Boltz {EXPECTED_BOLTZ_VERSION}, found {version}. "
            "Refusing to apply the atom_contact patch."
        )
    for label, path in paths.items():
        text = path.read_text(encoding="utf-8")
        if all(marker in text for marker in PATCH_MARKERS[label]):
            print(f"{label}: compatibility check passed (already patched)")
            continue
        actual = source_sha256(path)
        expected = EXPECTED_SOURCE_SHA256[label]
        if actual != expected:
            raise RuntimeError(
                f"{label} source hash mismatch for Boltz {version}: "
                f"expected {expected}, found {actual}."
            )
        print(f"{label}: compatibility check passed ({actual})")


def verify_applied_patch(paths: dict[str, Path]) -> None:
    """Fail unless the complete interface-v2 and atom-contact patch is installed."""
    for label, markers in PATCH_MARKERS.items():
        text = paths[label].read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise RuntimeError(
                f"{label} is missing applied patch marker(s): {missing}"
            )
    for label, markers in INTERFACE_PATCH_MARKERS.items():
        text = paths[label].read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise RuntimeError(
                f"{label} is missing interface patch marker(s): {missing}"
            )
    feature_text = paths["featurizerv2.py"].read_text(encoding="utf-8")
    potential_text = paths["potentials.py"].read_text(encoding="utf-8")
    schema_text = paths["schema.py"].read_text(encoding="utf-8")
    if INTERFACE_SCHEMA_V2_MARKER not in schema_text:
        raise RuntimeError("schema.py is missing interface-v2 duplicate validation.")
    if INTERFACE_SCHEMA_NEIGHBOR_MARKER not in schema_text:
        raise RuntimeError(
            "schema.py is missing same-chain interface-neighbor validation."
        )
    inference_text = paths["inferencev2.py"].read_text(encoding="utf-8")
    if INTERFACE_FAILURE_PROPAGATION_MARKER not in inference_text:
        raise RuntimeError(
            "inferencev2.py is missing interface feature-error propagation."
        )
    if INTERFACE_FEATURES_V2_MARKER not in feature_text:
        raise RuntimeError("featurizerv2.py is missing interface-v2 feature tensors.")
    if INTERFACE_FEATURES_CYCLIC_MARKER not in feature_text:
        raise RuntimeError(
            "featurizerv2.py is missing cyclic interface-neighbor protection."
        )
    if INTERFACE_FEATURES_CROP_MARKER not in feature_text:
        raise RuntimeError(
            "featurizerv2.py is missing cropped-interface handling."
        )
    if INTERFACE_FEATURES_AIR_MARKER not in feature_text:
        raise RuntimeError(
            "featurizerv2.py is missing literal-bound reciprocal AIR groups."
        )
    if (
        INTERFACE_POTENTIALS_V2_MARKER not in potential_text
        or potential_text.count("InterfaceClashPotentital(") < 2
    ):
        raise RuntimeError("potentials.py is missing interface-v2 clash guidance.")
    if INTERFACE_POTENTIALS_RESAMPLING_MARKER not in potential_text:
        raise RuntimeError(
            "potentials.py is missing interface AIR particle resampling."
        )
    if INTERFACE_POTENTIALS_AIR_MARKER not in potential_text:
        raise RuntimeError(
            "potentials.py is missing per-active-residue AIR reduction."
        )
    if INTERFACE_POTENTIALS_AIR_REGISTRATION_MARKER not in potential_text:
        raise RuntimeError(
            "potentials.py is missing interface AIR guidance parameters."
        )
    print("Boltz atom_contact/interface-v2 applied-state verification passed.")


def replace_once(text: str, anchor: str, replacement: str, description: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise RuntimeError(
            f"Expected one anchor for {description}, found {count}. "
            "The installed Boltz source does not match the patch target."
        )
    return text.replace(anchor, replacement, 1)


def write_if_changed(path: Path, text: str) -> bool:
    original = path.read_text(encoding="utf-8")
    if original == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def patch_schema(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if all(marker in text for marker in PATCH_MARKERS["schema.py"]):
        return False

    token_anchor = '''def token_spec_to_ids(
    chain_name, residue_index_or_atom_name, chain_to_idx, atom_idx_map, chains
):
    if chains[chain_name].type == const.chain_type_ids["NONPOLYMER"]:
        # Non-polymer chains are indexed by atom name
        _, _, atom_idx = atom_idx_map[(chain_name, 0, residue_index_or_atom_name)]
        return (chain_to_idx[chain_name], atom_idx)
    else:
        # Polymer chains are indexed by residue index
        return chain_to_idx[chain_name], residue_index_or_atom_name - 1
'''
    token_replacement = token_anchor + '''

def atom_contact_spec_to_ids(atom_spec, chain_to_idx, atom_idx_map, label):
    """Resolve an atom_contact endpoint to (asym_id, res_idx, atom_idx)."""
    try:
        parts = list(atom_spec)
    except TypeError as exc:
        msg = f"{label} must be [CHAIN_ID, RES_IDX, ATOM_NAME]."
        raise ValueError(msg) from exc

    if len(parts) != 3:
        msg = f"{label} must have exactly three fields: [CHAIN_ID, RES_IDX, ATOM_NAME]."
        raise ValueError(msg)

    chain_name, residue_index, atom_name = parts
    endpoint = f"{chain_name}:{residue_index}:{atom_name}"
    if chain_name not in chain_to_idx:
        msg = f"Unable to resolve atom-contact endpoint {endpoint}: chain does not exist."
        raise ValueError(msg)

    try:
        residue_index = int(residue_index)
    except (TypeError, ValueError) as exc:
        msg = f"Unable to resolve atom-contact endpoint {endpoint}: residue index must be an integer."
        raise ValueError(msg) from exc

    if residue_index < 1:
        msg = f"Unable to resolve atom-contact endpoint {endpoint}: residue index must be 1 or greater."
        raise ValueError(msg)

    atom_name = str(atom_name)
    try:
        return atom_idx_map[(chain_name, residue_index - 1, atom_name)]
    except KeyError as exc:
        endpoint = f"{chain_name}:{residue_index}:{atom_name}"
        msg = f"Unable to resolve atom-contact endpoint {endpoint}"
        raise ValueError(msg) from exc
'''
    text = replace_once(text, token_anchor, token_replacement, "schema atom_contact resolver")

    lists_anchor = '''    pocket_constraints = []
    contact_constraints = []
'''
    lists_replacement = '''    pocket_constraints = []
    contact_constraints = []
    atom_contact_constraints = []
    atom_contact_union_constraints = []
    seen_atom_contact_pairs = {}
'''
    text = replace_once(text, lists_anchor, lists_replacement, "schema atom_contact list")

    branch_anchor = '''            c1, r1, a1 = atom_idx_map[(c1, r1 - 1, a1)]  # 1-indexed
            c2, r2, a2 = atom_idx_map[(c2, r2 - 1, a2)]  # 1-indexed
            connections.append((c1, c2, r1, r2, a1, a2))
        elif "pocket" in constraint:
'''
    branch_replacement = '''            c1, r1, a1 = atom_idx_map[(c1, r1 - 1, a1)]  # 1-indexed
            c2, r2, a2 = atom_idx_map[(c2, r2 - 1, a2)]  # 1-indexed
            connections.append((c1, c2, r1, r2, a1, a2))
        elif "atom_contact" in constraint:
            if not boltz_2:
                msg = "atom_contact constraint is not supported in Boltz-1!"
                raise ValueError(msg)

            atom_contact = constraint["atom_contact"]
            if (
                "atom1" not in atom_contact
                or "atom2" not in atom_contact
                or "max_distance" not in atom_contact
            ):
                msg = (
                    "atom_contact constraint was not properly specified; expected "
                    "atom1, atom2, max_distance, and force: true."
                )
                raise ValueError(msg)

            force = atom_contact.get("force", False)
            if force is not True:
                msg = (
                    "atom_contact requires force: true because specific atom-pair "
                    "distance guidance is implemented through an inference-time contact potential."
                )
                raise ValueError(msg)

            try:
                max_distance = float(atom_contact["max_distance"])
            except (TypeError, ValueError) as exc:
                msg = "atom_contact max_distance must be a finite number."
                raise ValueError(msg) from exc
            if not np.isfinite(max_distance) or not (2.0 <= max_distance <= 20.0):
                msg = "atom_contact max_distance must satisfy 2.0 <= max_distance <= 20.0 Angstrom."
                raise ValueError(msg)

            atom1 = atom_contact_spec_to_ids(
                atom_contact["atom1"], chain_to_idx, atom_idx_map, "atom_contact atom1"
            )
            atom2 = atom_contact_spec_to_ids(
                atom_contact["atom2"], chain_to_idx, atom_idx_map, "atom_contact atom2"
            )
            if atom1[2] == atom2[2]:
                endpoint1 = ":".join(str(value) for value in atom_contact["atom1"])
                endpoint2 = ":".join(str(value) for value in atom_contact["atom2"])
                msg = (
                    f"atom_contact endpoints {endpoint1} and {endpoint2} resolve to "
                    f"the same exact atom (global atom index {atom1[2]})."
                )
                raise ValueError(msg)
            pair = tuple(sorted((atom1[2], atom2[2])))
            if pair in seen_atom_contact_pairs:
                previous_distance = seen_atom_contact_pairs[pair]
                duplicate_kind = (
                    "duplicate"
                    if previous_distance == max_distance
                    else "conflicting duplicate"
                )
                msg = (
                    f"atom_contact is a {duplicate_kind} exact atom pair "
                    f"({pair[0]} <-> {pair[1]}): max_distance "
                    f"{previous_distance} versus {max_distance}."
                )
                raise ValueError(msg)
            seen_atom_contact_pairs[pair] = max_distance
            atom_contact_constraints.append((atom1, atom2, max_distance, force))
        elif "atom_contact_union" in constraint:
            if not boltz_2:
                msg = "atom_contact_union constraint is not supported in Boltz-1!"
                raise ValueError(msg)

            union_number = len(atom_contact_union_constraints) + 1
            atom_contact_union = constraint["atom_contact_union"]
            if not isinstance(atom_contact_union, dict):
                msg = f"atom_contact_union {union_number} must be a mapping."
                raise ValueError(msg)
            if atom_contact_union.get("force", False) is not True:
                msg = (
                    f"atom_contact_union {union_number} requires force: true because "
                    "its OR group is implemented through an inference-time contact potential."
                )
                raise ValueError(msg)
            alternatives = atom_contact_union.get("alternatives")
            if not isinstance(alternatives, list) or len(alternatives) < 2:
                msg = (
                    f"atom_contact_union {union_number} alternatives must contain "
                    "at least two atom-contact alternatives."
                )
                raise ValueError(msg)

            resolved_alternatives = []
            seen_pairs = set()
            for alternative_number, alternative in enumerate(alternatives, start=1):
                label = (
                    f"atom_contact_union {union_number} alternative "
                    f"{alternative_number}"
                )
                if not isinstance(alternative, dict) or (
                    "atom1" not in alternative
                    or "atom2" not in alternative
                    or "max_distance" not in alternative
                ):
                    msg = (
                        f"{label} was not properly specified; expected "
                        "atom1, atom2, and max_distance."
                    )
                    raise ValueError(msg)
                try:
                    max_distance = float(alternative["max_distance"])
                except (TypeError, ValueError) as exc:
                    msg = f"{label} max_distance must be a finite number."
                    raise ValueError(msg) from exc
                if not np.isfinite(max_distance) or not (
                    2.0 <= max_distance <= 20.0
                ):
                    msg = (
                        f"{label} max_distance must satisfy "
                        "2.0 <= max_distance <= 20.0 Angstrom."
                    )
                    raise ValueError(msg)

                atom1 = atom_contact_spec_to_ids(
                    alternative["atom1"],
                    chain_to_idx,
                    atom_idx_map,
                    f"{label} atom1",
                )
                atom2 = atom_contact_spec_to_ids(
                    alternative["atom2"],
                    chain_to_idx,
                    atom_idx_map,
                    f"{label} atom2",
                )
                if atom1[2] == atom2[2]:
                    endpoint1 = ":".join(
                        str(value) for value in alternative["atom1"]
                    )
                    endpoint2 = ":".join(
                        str(value) for value in alternative["atom2"]
                    )
                    msg = (
                        f"{label} endpoints {endpoint1} and {endpoint2} resolve "
                        f"to the same exact atom (global atom index {atom1[2]})."
                    )
                    raise ValueError(msg)
                pair = tuple(sorted((atom1[2], atom2[2])))
                if pair in seen_pairs:
                    msg = (
                        f"{label} duplicates another alternative after exact "
                        f"atom-pair canonicalization ({pair[0]} <-> {pair[1]})."
                    )
                    raise ValueError(msg)
                seen_pairs.add(pair)
                resolved_alternatives.append(
                    (atom1, atom2, max_distance, True)
                )
            atom_contact_union_constraints.append(resolved_alternatives)
        elif "pocket" in constraint:
'''
    text = replace_once(text, branch_anchor, branch_replacement, "schema atom_contact branch")

    options_anchor = '''    options = InferenceOptions(
        pocket_constraints=pocket_constraints, contact_constraints=contact_constraints
    )
'''
    options_replacement = '''    options = InferenceOptions(
        pocket_constraints=pocket_constraints,
        contact_constraints=contact_constraints,
        atom_contact_constraints=atom_contact_constraints,
        atom_contact_union_constraints=atom_contact_union_constraints,
    )
'''
    text = replace_once(text, options_anchor, options_replacement, "schema InferenceOptions")

    return write_if_changed(path, text)


def patch_exact_atom_validation(path: Path) -> bool:
    """Add duplicate-pair validation to an older installed atom-contact patch."""
    text = path.read_text(encoding="utf-8")
    marker = "seen_atom_contact_pairs = {}"
    if marker in text:
        return False

    list_anchor = '''    atom_contact_constraints = []
    atom_contact_union_constraints = []
'''
    list_replacement = '''    atom_contact_constraints = []
    atom_contact_union_constraints = []
    seen_atom_contact_pairs = {}
'''
    text = replace_once(
        text,
        list_anchor,
        list_replacement,
        "exact atom_contact duplicate tracker",
    )

    append_anchor = '''            atom_contact_constraints.append((atom1, atom2, max_distance, force))
        elif "atom_contact_union" in constraint:
'''
    append_replacement = '''            pair = tuple(sorted((atom1[2], atom2[2])))
            if pair in seen_atom_contact_pairs:
                previous_distance = seen_atom_contact_pairs[pair]
                duplicate_kind = (
                    "duplicate"
                    if previous_distance == max_distance
                    else "conflicting duplicate"
                )
                msg = (
                    f"atom_contact is a {duplicate_kind} exact atom pair "
                    f"({pair[0]} <-> {pair[1]}): max_distance "
                    f"{previous_distance} versus {max_distance}."
                )
                raise ValueError(msg)
            seen_atom_contact_pairs[pair] = max_distance
            atom_contact_constraints.append((atom1, atom2, max_distance, force))
        elif "atom_contact_union" in constraint:
'''
    text = replace_once(
        text,
        append_anchor,
        append_replacement,
        "exact atom_contact duplicate validation",
    )
    text = text.replace(
        "distance guidance is implemented through a soft inference-time potential.",
        "distance guidance is implemented through an inference-time contact potential.",
    ).replace(
        "its OR group is implemented through a soft inference-time potential.",
        "its OR group is implemented through an inference-time contact potential.",
    )
    return write_if_changed(path, text)


def patch_types(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if all(marker in text for marker in PATCH_MARKERS["types.py"]):
        return False

    anchor = '''    contact_constraints: Optional[
        list[tuple[tuple[int, int], tuple[int, int], float, bool]]
    ] = None
'''
    replacement = anchor + '''    atom_contact_constraints: Optional[
        list[tuple[tuple[int, int, int], tuple[int, int, int], float, bool]]
    ] = None
    atom_contact_union_constraints: Optional[
        list[
            list[
                tuple[
                    tuple[int, int, int],
                    tuple[int, int, int],
                    float,
                    bool,
                ]
            ]
        ]
    ] = None
'''
    text = replace_once(text, anchor, replacement, "types atom_contact field")
    return write_if_changed(path, text)


def patch_inferencev2(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if all(marker in text for marker in PATCH_MARKERS["inferencev2.py"]):
        return False

    options_anchor = '''        if options is None:
            pocket_constraints, contact_constraints = None, None
        else:
            pocket_constraints, contact_constraints = (
                options.pocket_constraints,
                options.contact_constraints,
            )
'''
    options_replacement = '''        if options is None:
            pocket_constraints = None
            contact_constraints = None
            atom_contact_constraints = None
            atom_contact_union_constraints = None
        else:
            pocket_constraints = options.pocket_constraints
            contact_constraints = options.contact_constraints
            atom_contact_constraints = options.atom_contact_constraints
            atom_contact_union_constraints = options.atom_contact_union_constraints
'''
    text = replace_once(text, options_anchor, options_replacement, "inference atom_contact options")

    call_anchor = '''                inference_pocket_constraints=pocket_constraints,
                inference_contact_constraints=contact_constraints,
                compute_constraint_features=True,
'''
    call_replacement = '''                inference_pocket_constraints=pocket_constraints,
                inference_contact_constraints=contact_constraints,
                inference_atom_contact_constraints=atom_contact_constraints,
                inference_atom_contact_union_constraints=atom_contact_union_constraints,
                compute_constraint_features=True,
'''
    text = replace_once(text, call_anchor, call_replacement, "inference featurizer call")
    return write_if_changed(path, text)


def patch_featurizerv2(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if all(marker in text for marker in PATCH_MARKERS["featurizerv2.py"]):
        return False

    token_sig_anchor = '''    inference_contact_constraints: Optional[
        list[tuple[tuple[int, int], tuple[int, int], float]]
    ] = False,
'''
    token_sig_replacement = token_sig_anchor + '''    inference_atom_contact_constraints: Optional[
        list[tuple[tuple[int, int, int], tuple[int, int, int], float, bool]]
    ] = None,
'''
    text = replace_once(text, token_sig_anchor, token_sig_replacement, "token feature signature")

    token_function_anchor = '''def process_token_features(  # noqa: C901, PLR0915, PLR0912
'''
    token_function_replacement = '''def apply_atom_contact_token_conditioning(
    contact_conditioning,
    contact_threshold,
    token_data,
    inference_atom_contact_constraints,
):
    """Apply deterministic token conditioning for atom-contact restraints."""
    for atom1, atom2, max_distance, _force in inference_atom_contact_constraints:
        atom_idx1 = atom1[2]
        atom_idx2 = atom2[2]
        idx1 = None
        idx2 = None
        for idx, token in enumerate(token_data):
            if token["atom_idx"] <= atom_idx1 < token["atom_idx"] + token["atom_num"]:
                idx1 = idx
            if token["atom_idx"] <= atom_idx2 < token["atom_idx"] + token["atom_num"]:
                idx2 = idx
        if idx1 is None or idx2 is None:
            continue
        if idx1 == idx2:
            continue

        contact_conditioning[idx1, idx2] = const.contact_conditioning_info["CONTACT"]
        contact_conditioning[idx2, idx1] = const.contact_conditioning_info["CONTACT"]
        current_threshold = contact_threshold[idx1, idx2]
        threshold = (
            max_distance
            if current_threshold <= 0
            else min(float(current_threshold), max_distance)
        )
        contact_threshold[idx1, idx2] = threshold
        contact_threshold[idx2, idx1] = threshold


def process_token_features(  # noqa: C901, PLR0915, PLR0912
'''
    text = replace_once(
        text,
        token_function_anchor,
        token_function_replacement,
        "atom_contact token conditioning helper",
    )

    token_block_anchor = '''                            break
                    break

    if binder_pocket_conditioned_prop > 0.0:
'''
    token_block_replacement = '''                            break
                    break

    if inference_atom_contact_constraints is not None:
        apply_atom_contact_token_conditioning(
            contact_conditioning,
            contact_threshold,
            token_data,
            inference_atom_contact_constraints,
        )

    if binder_pocket_conditioned_prop > 0.0:
'''
    text = replace_once(text, token_block_anchor, token_block_replacement, "token atom_contact conditioning")

    contact_sig_anchor = '''def process_contact_feature_constraints(
    data: Tokenized,
    inference_pocket_constraints: list[tuple[int, list[tuple[int, int]], float]],
    inference_contact_constraints: list[tuple[tuple[int, int], tuple[int, int], float]],
):
'''
    contact_sig_replacement = '''def process_contact_feature_constraints(
    data: Tokenized,
    inference_pocket_constraints: list[tuple[int, list[tuple[int, int]], float]],
    inference_contact_constraints: list[tuple[tuple[int, int], tuple[int, int], float]],
    inference_atom_contact_constraints: list[
        tuple[tuple[int, int, int], tuple[int, int, int], float, bool]
    ],
    inference_atom_contact_union_constraints: Optional[list[
        list[
            tuple[
                tuple[int, int, int],
                tuple[int, int, int],
                float,
                bool,
            ]
        ]
    ]] = None,
):
'''
    text = replace_once(text, contact_sig_anchor, contact_sig_replacement, "contact feature signature")

    exact_block_anchor = '''
    if len(pair_index) > 0:
'''
    exact_block_replacement = '''    for atom1, atom2, max_distance, force in inference_atom_contact_constraints:
        if not force:
            continue

        atom_idx_pairs = torch.tensor([[atom1[2]], [atom2[2]]], dtype=torch.long)
        pair_index.append(atom_idx_pairs)
        union_index.append(torch.full((atom_idx_pairs.shape[1],), union_idx))
        negation_mask.append(torch.ones((atom_idx_pairs.shape[1],), dtype=torch.bool))
        thresholds.append(torch.full((atom_idx_pairs.shape[1],), max_distance))
        union_idx += 1

    for alternatives in inference_atom_contact_union_constraints or []:
        atom_idx_pairs = torch.tensor(
            [
                [alternative[0][2] for alternative in alternatives],
                [alternative[1][2] for alternative in alternatives],
            ],
            dtype=torch.long,
        )
        pair_index.append(atom_idx_pairs)
        union_index.append(torch.full((atom_idx_pairs.shape[1],), union_idx))
        negation_mask.append(
            torch.ones((atom_idx_pairs.shape[1],), dtype=torch.bool)
        )
        thresholds.append(
            torch.tensor(
                [alternative[2] for alternative in alternatives],
                dtype=torch.float,
            )
        )
        union_idx += 1

    if len(pair_index) > 0:
'''
    text = replace_once(text, exact_block_anchor, exact_block_replacement, "exact atom_contact potential pairs")

    process_sig_anchor = '''        inference_contact_constraints: Optional[
            list[tuple[tuple[int, int], tuple[int, int], float]]
        ] = None,
        compute_affinity: bool = False,
'''
    process_sig_replacement = '''        inference_contact_constraints: Optional[
            list[tuple[tuple[int, int], tuple[int, int], float]]
        ] = None,
        inference_atom_contact_constraints: Optional[
            list[tuple[tuple[int, int, int], tuple[int, int, int], float, bool]]
        ] = None,
        inference_atom_contact_union_constraints: Optional[
            list[
                list[
                    tuple[
                        tuple[int, int, int],
                        tuple[int, int, int],
                        float,
                        bool,
                    ]
                ]
            ]
        ] = None,
        compute_affinity: bool = False,
'''
    text = replace_once(text, process_sig_anchor, process_sig_replacement, "featurizer process signature")

    token_call_anchor = '''            inference_pocket_constraints=inference_pocket_constraints,
            inference_contact_constraints=inference_contact_constraints,
        )
'''
    token_call_replacement = '''            inference_pocket_constraints=inference_pocket_constraints,
            inference_contact_constraints=inference_contact_constraints,
            inference_atom_contact_constraints=inference_atom_contact_constraints,
        )
'''
    text = replace_once(text, token_call_anchor, token_call_replacement, "token feature call")

    contact_call_anchor = '''                inference_pocket_constraints=inference_pocket_constraints if inference_pocket_constraints else [],
                inference_contact_constraints=inference_contact_constraints if inference_contact_constraints else [],
            )
'''
    contact_call_replacement = '''                inference_pocket_constraints=inference_pocket_constraints if inference_pocket_constraints else [],
                inference_contact_constraints=inference_contact_constraints if inference_contact_constraints else [],
                inference_atom_contact_constraints=inference_atom_contact_constraints if inference_atom_contact_constraints else [],
                inference_atom_contact_union_constraints=inference_atom_contact_union_constraints if inference_atom_contact_union_constraints else [],
            )
'''
    text = replace_once(text, contact_call_anchor, contact_call_replacement, "contact feature call")

    return write_if_changed(path, text)


def patch_exact_token_conditioning(path: Path) -> bool:
    """Avoid creating a nonsensical binary contact on one token's diagonal."""
    text = path.read_text(encoding="utf-8")
    marker = '''        if idx1 == idx2:
            continue
'''
    if marker in text:
        return False
    anchor = '''        if idx1 is None or idx2 is None:
            continue

        contact_conditioning[idx1, idx2] = const.contact_conditioning_info["CONTACT"]
'''
    replacement = '''        if idx1 is None or idx2 is None:
            continue
        if idx1 == idx2:
            continue

        contact_conditioning[idx1, idx2] = const.contact_conditioning_info["CONTACT"]
'''
    text = replace_once(
        text,
        anchor,
        replacement,
        "same-token exact atom conditioning guard",
    )
    return write_if_changed(path, text)


def patch_diffusionv2(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    marker = "sample_ids.split(max_parallel_samples)"
    if marker in text:
        return False

    anchor = '''                sample_ids_chunks = sample_ids.chunk(
                    multiplicity % max_parallel_samples + 1
                )
'''
    replacement = '''                sample_ids_chunks = sample_ids.split(max_parallel_samples)
'''
    text = replace_once(
        text,
        anchor,
        replacement,
        "diffusion max_parallel_samples chunking",
    )
    return write_if_changed(path, text)


def patch_interface_schema(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if all(marker in text for marker in INTERFACE_PATCH_MARKERS["schema.py"]):
        return False

    parser_anchor = "\n\n\ndef parse_boltz_schema("
    helper = '''


def interface_patch_to_ids(patch, chain_to_idx, atom_idx_map, chains, label):
    """Resolve one CSP-active protein patch to residue-token identifiers."""
    if not isinstance(patch, dict):
        msg = f"{label} must be a mapping with chain and residues."
        raise ValueError(msg)
    chain_name = str(patch.get("chain", ""))
    if chain_name not in chain_to_idx:
        msg = f"{label} chain {chain_name} does not exist."
        raise ValueError(msg)
    if chains[chain_name].type != const.chain_type_ids["PROTEIN"]:
        msg = f"{label} chain {chain_name} must be a protein chain."
        raise ValueError(msg)
    residues = patch.get("residues")
    if not isinstance(residues, list) or len(residues) == 0:
        msg = f"{label} residues must be a nonempty list."
        raise ValueError(msg)

    resolved = []
    seen = set()
    for residue_number, residue_index in enumerate(residues, start=1):
        if isinstance(residue_index, bool) or not isinstance(residue_index, int):
            msg = f"{label} residue {residue_number} must be a positive integer."
            raise ValueError(msg)
        if residue_index < 1:
            msg = f"{label} residue {residue_number} must be a positive integer."
            raise ValueError(msg)
        if residue_index > len(chains[chain_name].sequence):
            msg = (
                f"{label} residue {chain_name}:{residue_index} exceeds "
                f"chain length {len(chains[chain_name].sequence)}."
            )
            raise ValueError(msg)
        if residue_index in seen:
            msg = f"{label} contains duplicate residue {residue_index}."
            raise ValueError(msg)
        seen.add(residue_index)
        try:
            resolved.append(
                token_spec_to_ids(
                    chain_name,
                    residue_index,
                    chain_to_idx,
                    atom_idx_map,
                    chains,
                )
            )
        except KeyError as exc:
            msg = f"Unable to resolve {label} residue {chain_name}:{residue_index}."
            raise ValueError(msg) from exc
    return resolved


def interface_residue_pair_is_eligible(residue1, residue2, cyclic_period_by_chain):
    """Return whether two patch residues are not covalent sequence neighbors."""
    if residue1[0] != residue2[0]:
        return True
    residue_delta = abs(residue1[1] - residue2[1])
    cyclic_period = cyclic_period_by_chain.get(residue1[0], 0)
    return (
        residue_delta > 1
        and not (
            cyclic_period > 0
            and cyclic_period - residue_delta <= 1
        )
    )
'''
    text = replace_once(
        text,
        parser_anchor,
        helper + parser_anchor,
        "schema interface patch resolver",
    )

    list_anchor = '''    atom_contact_union_constraints = []
    seen_atom_contact_pairs = {}
    constraints = schema.get("constraints", [])
'''
    list_replacement = '''    atom_contact_union_constraints = []
    interface_contact_constraints = []
    seen_interface_contacts = {}
    seen_atom_contact_pairs = {}
    constraints = schema.get("constraints", [])
'''
    text = replace_once(text, list_anchor, list_replacement, "schema interface list")

    branch_anchor = '''        elif "pocket" in constraint:
'''
    branch_replacement = '''        elif "interface_contact" in constraint:
            if not boltz_2:
                msg = "interface_contact constraint is not supported in Boltz-1!"
                raise ValueError(msg)

            interface_number = len(interface_contact_constraints) + 1
            interface_contact = constraint["interface_contact"]
            if not isinstance(interface_contact, dict):
                msg = f"interface_contact {interface_number} must be a mapping."
                raise ValueError(msg)
            if (
                "patch1" not in interface_contact
                or "patch2" not in interface_contact
                or "max_distance" not in interface_contact
            ):
                msg = (
                    f"interface_contact {interface_number} was not properly "
                    "specified; expected patch1, patch2, max_distance, and force."
                )
                raise ValueError(msg)
            try:
                max_distance = float(interface_contact["max_distance"])
            except (TypeError, ValueError) as exc:
                msg = f"interface_contact {interface_number} max_distance must be finite."
                raise ValueError(msg) from exc
            if not np.isfinite(max_distance) or not (4.0 <= max_distance <= 20.0):
                msg = (
                    f"interface_contact {interface_number} max_distance must "
                    "satisfy 4.0 <= max_distance <= 20.0 Angstrom."
                )
                raise ValueError(msg)
            force = interface_contact.get("force", False)
            if not isinstance(force, bool):
                msg = f"interface_contact {interface_number} force must be true or false."
                raise ValueError(msg)
            patch1 = interface_patch_to_ids(
                interface_contact["patch1"],
                chain_to_idx,
                atom_idx_map,
                chains,
                f"interface_contact {interface_number} patch1",
            )
            patch2 = interface_patch_to_ids(
                interface_contact["patch2"],
                chain_to_idx,
                atom_idx_map,
                chains,
                f"interface_contact {interface_number} patch2",
            )
            overlap = set(patch1).intersection(patch2)
            if overlap:
                residues = ", ".join(str(residue[1] + 1) for residue in sorted(overlap))
                msg = (
                    f"interface_contact {interface_number} same-chain patches "
                    f"must be disjoint; overlapping residues: {residues}."
                )
                raise ValueError(msg)
            cyclic_period_by_chain = {
                chain_to_idx[chain_name]: chains[chain_name].cyclic_period
                for chain_name in chain_to_idx
            }
            patch1_without_target = [
                residue
                for residue in patch1
                if not any(
                    interface_residue_pair_is_eligible(
                        residue,
                        target,
                        cyclic_period_by_chain,
                    )
                    for target in patch2
                )
            ]
            patch2_without_target = [
                residue
                for residue in patch2
                if not any(
                    interface_residue_pair_is_eligible(
                        residue,
                        target,
                        cyclic_period_by_chain,
                    )
                    for target in patch1
                )
            ]
            if patch1_without_target or patch2_without_target:
                details = []
                if patch1_without_target:
                    details.append(
                        "patch1: "
                        + ", ".join(
                            str(residue[1] + 1)
                            for residue in patch1_without_target
                        )
                    )
                if patch2_without_target:
                    details.append(
                        "patch2: "
                        + ", ".join(
                            str(residue[1] + 1)
                            for residue in patch2_without_target
                        )
                    )
                msg = (
                    f"interface_contact {interface_number} same-chain patches "
                    "are invalid: every active residue must have an eligible "
                    "opposite-patch residue after excluding linear or cyclic "
                    f"sequence neighbors; {'; '.join(details)}."
                )
                raise ValueError(msg)
            canonical_patches = tuple(
                sorted((tuple(sorted(patch1)), tuple(sorted(patch2))))
            )
            if canonical_patches in seen_interface_contacts:
                previous_number, previous_distance = seen_interface_contacts[
                    canonical_patches
                ]
                relation = (
                    "conflicts with"
                    if previous_distance != max_distance
                    else "duplicates"
                )
                msg = (
                    f"interface_contact {interface_number} {relation} "
                    f"interface_contact {previous_number}; duplicate or reversed "
                    "patch pairs are not allowed."
                )
                raise ValueError(msg)
            seen_interface_contacts[canonical_patches] = (
                interface_number,
                max_distance,
            )
            interface_contact_constraints.append(
                (patch1, patch2, max_distance, force)
            )
        elif "pocket" in constraint:
'''
    text = replace_once(text, branch_anchor, branch_replacement, "schema interface branch")

    options_anchor = '''        atom_contact_union_constraints=atom_contact_union_constraints,
    )
'''
    options_replacement = '''        atom_contact_union_constraints=atom_contact_union_constraints,
        interface_contact_constraints=interface_contact_constraints,
    )
'''
    text = replace_once(text, options_anchor, options_replacement, "schema interface options")
    return write_if_changed(path, text)


def patch_interface_schema_v2(path: Path) -> bool:
    """Reject duplicate/reversed interface definitions in already-patched images."""
    text = path.read_text(encoding="utf-8")
    if INTERFACE_SCHEMA_V2_MARKER in text:
        return False
    list_anchor = '''    interface_contact_constraints = []
    seen_atom_contact_pairs = {}
'''
    list_replacement = '''    interface_contact_constraints = []
    seen_interface_contacts = {}
    seen_atom_contact_pairs = {}
'''
    legacy_list_anchor = '''    seen_atom_contact_pairs = {}
    interface_contact_constraints = []
'''
    legacy_list_replacement = '''    seen_atom_contact_pairs = {}
    interface_contact_constraints = []
    seen_interface_contacts = {}
'''
    if list_anchor in text:
        text = replace_once(
            text,
            list_anchor,
            list_replacement,
            "schema interface duplicate tracking",
        )
    else:
        text = replace_once(
            text,
            legacy_list_anchor,
            legacy_list_replacement,
            "legacy schema interface duplicate tracking",
        )
    append_anchor = '''            interface_contact_constraints.append(
                (patch1, patch2, max_distance, force)
            )
'''
    append_replacement = '''            canonical_patches = tuple(
                sorted((tuple(sorted(patch1)), tuple(sorted(patch2))))
            )
            if canonical_patches in seen_interface_contacts:
                previous_number, previous_distance = seen_interface_contacts[
                    canonical_patches
                ]
                relation = (
                    "conflicts with"
                    if previous_distance != max_distance
                    else "duplicates"
                )
                msg = (
                    f"interface_contact {interface_number} {relation} "
                    f"interface_contact {previous_number}; duplicate or reversed "
                    "patch pairs are not allowed."
                )
                raise ValueError(msg)
            seen_interface_contacts[canonical_patches] = (
                interface_number,
                max_distance,
            )
            interface_contact_constraints.append(
                (patch1, patch2, max_distance, force)
            )
'''
    text = replace_once(
        text,
        append_anchor,
        append_replacement,
        "schema interface duplicate validation",
    )
    return write_if_changed(path, text)


def patch_interface_schema_neighbor_validation(path: Path) -> bool:
    """Require every active residue to have a non-neighbor opposite target."""
    text = path.read_text(encoding="utf-8")
    if INTERFACE_SCHEMA_NEIGHBOR_MARKER in text:
        return False

    helper_marker = "def interface_residue_pair_is_eligible("
    if helper_marker not in text:
        resolver_anchor = "\ndef interface_patch_to_ids("
        helper = '''
def interface_residue_pair_is_eligible(residue1, residue2, cyclic_period_by_chain):
    """Return whether two patch residues are not covalent sequence neighbors."""
    if residue1[0] != residue2[0]:
        return True
    residue_delta = abs(residue1[1] - residue2[1])
    cyclic_period = cyclic_period_by_chain.get(residue1[0], 0)
    return (
        residue_delta > 1
        and not (
            cyclic_period > 0
            and cyclic_period - residue_delta <= 1
        )
    )


'''
        text = replace_once(
            text,
            resolver_anchor,
            "\n" + helper + "def interface_patch_to_ids(",
            "interface residue eligibility helper",
        )

    old_validation = '''            has_non_neighbor_pair = any(
                residue1[0] != residue2[0]
                or abs(residue1[1] - residue2[1]) > 1
                for residue1 in patch1
                for residue2 in patch2
            )
            if not has_non_neighbor_pair:
                msg = (
                    f"interface_contact {interface_number} same-chain patches "
                    "must include at least one non-neighbor residue pair."
                )
                raise ValueError(msg)
'''
    no_validation_anchor = '''            if overlap:
                residues = ", ".join(str(residue[1] + 1) for residue in sorted(overlap))
                msg = (
                    f"interface_contact {interface_number} same-chain patches "
                    f"must be disjoint; overlapping residues: {residues}."
                )
                raise ValueError(msg)
'''
    complete_validation = '''            cyclic_period_by_chain = {
                chain_to_idx[chain_name]: chains[chain_name].cyclic_period
                for chain_name in chain_to_idx
            }
            patch1_without_target = [
                residue
                for residue in patch1
                if not any(
                    interface_residue_pair_is_eligible(
                        residue,
                        target,
                        cyclic_period_by_chain,
                    )
                    for target in patch2
                )
            ]
            patch2_without_target = [
                residue
                for residue in patch2
                if not any(
                    interface_residue_pair_is_eligible(
                        residue,
                        target,
                        cyclic_period_by_chain,
                    )
                    for target in patch1
                )
            ]
            if patch1_without_target or patch2_without_target:
                details = []
                if patch1_without_target:
                    details.append(
                        "patch1: "
                        + ", ".join(
                            str(residue[1] + 1)
                            for residue in patch1_without_target
                        )
                    )
                if patch2_without_target:
                    details.append(
                        "patch2: "
                        + ", ".join(
                            str(residue[1] + 1)
                            for residue in patch2_without_target
                        )
                    )
                msg = (
                    f"interface_contact {interface_number} same-chain patches "
                    "are invalid: every active residue must have an eligible "
                    "opposite-patch residue after excluding linear or cyclic "
                    f"sequence neighbors; {'; '.join(details)}."
                )
                raise ValueError(msg)
'''
    if old_validation in text:
        text = replace_once(
            text,
            old_validation,
            complete_validation,
            "complete interface residue eligibility validation",
        )
    else:
        text = replace_once(
            text,
            no_validation_anchor,
            no_validation_anchor + complete_validation,
            "complete interface residue eligibility validation",
        )
    return write_if_changed(path, text)


def patch_interface_types(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if all(marker in text for marker in INTERFACE_PATCH_MARKERS["types.py"]):
        return False
    anchor = '''    atom_contact_union_constraints: Optional[
        list[
            list[
                tuple[
                    tuple[int, int, int],
                    tuple[int, int, int],
                    float,
                    bool,
                ]
            ]
        ]
    ] = None
'''
    replacement = anchor + '''    interface_contact_constraints: Optional[
        list[
            tuple[
                list[tuple[int, int]],
                list[tuple[int, int]],
                float,
                bool,
            ]
        ]
    ] = None
'''
    text = replace_once(text, anchor, replacement, "types interface field")
    return write_if_changed(path, text)


def patch_interface_inferencev2(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if all(marker in text for marker in INTERFACE_PATCH_MARKERS["inferencev2.py"]):
        return False
    none_anchor = '''            atom_contact_union_constraints = None
        else:
'''
    none_replacement = '''            atom_contact_union_constraints = None
            interface_contact_constraints = None
        else:
'''
    text = replace_once(text, none_anchor, none_replacement, "inference interface none")
    options_anchor = '''            atom_contact_union_constraints = options.atom_contact_union_constraints
'''
    options_replacement = options_anchor + '''            interface_contact_constraints = options.interface_contact_constraints
'''
    text = replace_once(text, options_anchor, options_replacement, "inference interface options")
    call_anchor = '''                inference_atom_contact_union_constraints=atom_contact_union_constraints,
                compute_constraint_features=True,
'''
    call_replacement = '''                inference_atom_contact_union_constraints=atom_contact_union_constraints,
                inference_interface_contact_constraints=interface_contact_constraints,
                compute_constraint_features=True,
'''
    text = replace_once(text, call_anchor, call_replacement, "inference interface call")
    return write_if_changed(path, text)


def patch_interface_failure_propagation(path: Path) -> bool:
    """Do not let PredictionDataset swallow or substitute interface failures."""
    text = path.read_text(encoding="utf-8")
    if INTERFACE_FAILURE_PROPAGATION_MARKER in text:
        return False
    anchor = '''        except Exception as e:  # noqa: BLE001
            import traceback

            traceback.print_exc()
            print(f"Featurizer failed on {record.id} with error {e}. Skipping.")  # noqa: T201
            return self.__getitem__(0)
'''
    replacement = '''        except Exception as e:  # noqa: BLE001
            if interface_contact_constraints:
                raise
            import traceback

            traceback.print_exc()
            print(f"Featurizer failed on {record.id} with error {e}. Skipping.")  # noqa: T201
            return self.__getitem__(0)
'''
    text = replace_once(
        text,
        anchor,
        replacement,
        "interface featurizer failure propagation",
    )
    return write_if_changed(path, text)


def patch_interface_featurizerv2(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if all(marker in text for marker in INTERFACE_PATCH_MARKERS["featurizerv2.py"]):
        return False

    function_anchor = '''def process_contact_feature_constraints(
'''
    helper = '''def apply_interface_contact_potentials(
    token_data,
    constraints,
    pair_index,
    union_index,
    negation_mask,
    thresholds,
    union_idx,
):
    """Add reciprocal active-residue-to-opposite-patch ambiguous groups."""
    token_by_residue = {
        (int(token["asym_id"]), int(token["res_idx"])): token
        for token in token_data
        if token["mol_type"] != const.chain_type_ids["NONPOLYMER"]
    }
    for patch1, patch2, max_distance, force in constraints or []:
        if not force:
            continue
        patch1_tokens = [token_by_residue[tuple(selector)] for selector in patch1]
        patch2_tokens = [token_by_residue[tuple(selector)] for selector in patch2]
        for source_tokens, target_tokens in (
            (patch1_tokens, patch2_tokens),
            (patch2_tokens, patch1_tokens),
        ):
            target_atoms = torch.cat(
                [
                    torch.arange(
                        int(token["atom_idx"]),
                        int(token["atom_idx"] + token["atom_num"]),
                    )
                    for token in target_tokens
                ]
            )
            for source_token in source_tokens:
                source_atoms = torch.arange(
                    int(source_token["atom_idx"]),
                    int(source_token["atom_idx"] + source_token["atom_num"]),
                )
                atom_idx_pairs = torch.cartesian_prod(source_atoms, target_atoms).T
                pair_index.append(atom_idx_pairs)
                union_index.append(
                    torch.full((atom_idx_pairs.shape[1],), union_idx)
                )
                negation_mask.append(
                    torch.ones((atom_idx_pairs.shape[1],), dtype=torch.bool)
                )
                thresholds.append(
                    torch.full((atom_idx_pairs.shape[1],), max_distance)
                )
                union_idx += 1
    return union_idx


def process_contact_feature_constraints(
'''
    text = replace_once(
        text,
        function_anchor,
        helper,
        "interface potential helper",
    )

    signature_anchor = '''    inference_atom_contact_union_constraints: Optional[list[
        list[
            tuple[
                tuple[int, int, int],
                tuple[int, int, int],
                float,
                bool,
            ]
        ]
    ]] = None,
):
'''
    signature_replacement = '''    inference_atom_contact_union_constraints: Optional[list[
        list[
            tuple[
                tuple[int, int, int],
                tuple[int, int, int],
                float,
                bool,
            ]
        ]
    ]] = None,
    inference_interface_contact_constraints: Optional[
        list[
            tuple[
                list[tuple[int, int]],
                list[tuple[int, int]],
                float,
                bool,
            ]
        ]
    ] = None,
):
'''
    text = replace_once(text, signature_anchor, signature_replacement, "interface contact signature")

    output_anchor = '''    if len(pair_index) > 0:
        pair_index = torch.cat(pair_index, dim=1)
'''
    output_replacement = '''    union_idx = apply_interface_contact_potentials(
        token_data,
        inference_interface_contact_constraints,
        pair_index,
        union_index,
        negation_mask,
        thresholds,
        union_idx,
    )

    if len(pair_index) > 0:
        pair_index = torch.cat(pair_index, dim=1)
'''
    text = replace_once(text, output_anchor, output_replacement, "interface potential pairs")

    process_signature_anchor = '''        inference_atom_contact_union_constraints: Optional[
            list[
                list[
                    tuple[
                        tuple[int, int, int],
                        tuple[int, int, int],
                        float,
                        bool,
                    ]
                ]
            ]
        ] = None,
        compute_affinity: bool = False,
'''
    process_signature_replacement = '''        inference_atom_contact_union_constraints: Optional[
            list[
                list[
                    tuple[
                        tuple[int, int, int],
                        tuple[int, int, int],
                        float,
                        bool,
                    ]
                ]
            ]
        ] = None,
        inference_interface_contact_constraints: Optional[
            list[
                tuple[
                    list[tuple[int, int]],
                    list[tuple[int, int]],
                    float,
                    bool,
                ]
            ]
        ] = None,
        compute_affinity: bool = False,
'''
    text = replace_once(
        text,
        process_signature_anchor,
        process_signature_replacement,
        "featurizer interface process signature",
    )

    call_anchor = '''                inference_atom_contact_union_constraints=inference_atom_contact_union_constraints if inference_atom_contact_union_constraints else [],
            )
'''
    call_replacement = '''                inference_atom_contact_union_constraints=inference_atom_contact_union_constraints if inference_atom_contact_union_constraints else [],
                inference_interface_contact_constraints=inference_interface_contact_constraints if inference_interface_contact_constraints else [],
            )
'''
    text = replace_once(text, call_anchor, call_replacement, "featurizer interface call")
    return write_if_changed(path, text)


def interface_features_v2_source() -> str:
    return '''def apply_interface_contact_potentials(data, constraints):
    """Build literal heavy-atom reciprocal AIR guidance and clash-protection pairs."""
    token_data = data.tokens
    pair_index, union_index, negation_mask, thresholds = [], [], [], []
    pair_weights, group_thresholds, group_weights = [], [], []
    clash_pair_index = []
    seen_clash_pairs = set()
    union_idx = 0
    clash_distance = 2.5
    max_interface_atom_pairs = 250_000
    interface_atom_pair_count = 0
    token_by_residue = {}
    global_to_local_atom = {}
    cyclic_period_by_chain = {
        int(chain["asym_id"]): int(chain["cyclic_period"])
        for chain in getattr(data.structure, "chains", [])
        if int(chain["cyclic_period"]) > 0
    }
    local_atom_start = 0
    for token in token_data:
        atom_start = int(token["atom_idx"])
        atom_count = int(token["atom_num"])
        for offset in range(atom_count):
            global_to_local_atom[atom_start + offset] = local_atom_start + offset
        if token["mol_type"] != const.chain_type_ids["NONPOLYMER"]:
            token_by_residue[
                (int(token["asym_id"]), int(token["res_idx"]))
            ] = (token, local_atom_start)
        local_atom_start += atom_count

    bonded_pairs = set()
    for bond in getattr(data.structure, "bonds", []):
        atom1 = global_to_local_atom.get(int(bond["atom_1"]))
        atom2 = global_to_local_atom.get(int(bond["atom_2"]))
        if atom1 is not None and atom2 is not None:
            bonded_pairs.add(tuple(sorted((atom1, atom2))))

    def available_patch_tokens(patch, label):
        missing = [
            tuple(selector)
            for selector in patch
            if tuple(selector) not in token_by_residue
        ]
        if missing:
            missing_text = ", ".join(
                f"chain_index={selector[0]},residue_index={selector[1]}"
                for selector in missing
            )
            raise ValueError(
                f"{label} lost forced active residue(s) during cropping: "
                f"{missing_text}. Increase the crop size or reduce the input."
            )
        return [token_by_residue[tuple(selector)] for selector in patch]

    def same_chain_neighbors(token1, token2):
        chain1 = int(token1["asym_id"])
        chain2 = int(token2["asym_id"])
        if chain1 != chain2:
            return False
        residue_delta = abs(
            int(token1["res_idx"]) - int(token2["res_idx"])
        )
        cyclic_period = cyclic_period_by_chain.get(chain1, 0)
        return (
            residue_delta <= 1
            or (
                cyclic_period > 0
                and cyclic_period - residue_delta <= 1
            )
        )

    def eligible_atom_pairs(token1, local_start1, token2, local_start2):
        if same_chain_neighbors(token1, token2):
            return []
        pairs = []
        for atom1 in range(
            local_start1,
            local_start1 + int(token1["atom_num"]),
        ):
            for atom2 in range(
                local_start2,
                local_start2 + int(token2["atom_num"]),
            ):
                if tuple(sorted((atom1, atom2))) not in bonded_pairs:
                    pairs.append((atom1, atom2))
        return pairs

    for interface_number, (
        patch1,
        patch2,
        max_distance,
        force,
    ) in enumerate(constraints or [], start=1):
        if not force:
            continue
        patch1_tokens = available_patch_tokens(
            patch1,
            f"interface_contact {interface_number} patch1",
        )
        patch2_tokens = available_patch_tokens(
            patch2,
            f"interface_contact {interface_number} patch2",
        )
        literal_threshold = float(max_distance)

        for source_label, source_tokens, target_tokens in (
            ("patch1", patch1_tokens, patch2_tokens),
            ("patch2", patch2_tokens, patch1_tokens),
        ):
            direction_groups = []
            for source_token, source_local_start in source_tokens:
                group_pairs = []
                for target_token, target_local_start in target_tokens:
                    group_pairs.extend(
                        eligible_atom_pairs(
                            source_token,
                            source_local_start,
                            target_token,
                            target_local_start,
                        )
                    )
                if not group_pairs:
                    raise ValueError(
                        f"interface_contact {interface_number} {source_label} "
                        "contains an active residue with no eligible opposite-"
                        "patch heavy-atom pair after excluding sequence "
                        "neighbors and explicit bonds."
                    )
                direction_groups.append(
                    torch.tensor(group_pairs, dtype=torch.long).T
                )
            direction_group_weight = 0.5 / len(direction_groups)
            for atom_pairs in direction_groups:
                interface_atom_pair_count += atom_pairs.shape[1]
                if interface_atom_pair_count > max_interface_atom_pairs:
                    raise ValueError(
                        "interface_contact generated more than "
                        f"{max_interface_atom_pairs} eligible heavy-atom pairs; "
                        "reduce the interface patch sizes."
                    )
                pair_index.append(atom_pairs)
                union_index.append(
                    torch.full(
                        (atom_pairs.shape[1],),
                        union_idx,
                        dtype=torch.long,
                    )
                )
                negation_mask.append(
                    torch.ones(
                        (atom_pairs.shape[1],),
                        dtype=torch.bool,
                    )
                )
                thresholds.append(
                    torch.full(
                        (atom_pairs.shape[1],),
                        literal_threshold,
                    )
                )
                pair_weights.append(
                    torch.full(
                        (atom_pairs.shape[1],),
                        1.0,
                    )
                )
                group_thresholds.append(literal_threshold)
                group_weights.append(direction_group_weight)
                union_idx += 1

        for (token1, local_start1) in patch1_tokens:
            for (token2, local_start2) in patch2_tokens:
                for atom1, atom2 in eligible_atom_pairs(
                    token1,
                    local_start1,
                    token2,
                    local_start2,
                ):
                    canonical_pair = tuple(sorted((atom1, atom2)))
                    if canonical_pair in seen_clash_pairs:
                        continue
                    seen_clash_pairs.add(canonical_pair)
                    clash_pair_index.append((atom1, atom2))

    if pair_index:
        pair_index = torch.cat(pair_index, dim=1)
        union_index = torch.cat(union_index)
        negation_mask = torch.cat(negation_mask)
        thresholds = torch.cat(thresholds)
        pair_weights = torch.cat(pair_weights)
        group_thresholds = torch.tensor(group_thresholds, dtype=torch.float32)
        group_weights = torch.tensor(group_weights, dtype=torch.float32)
    else:
        pair_index = torch.empty((2, 0), dtype=torch.long)
        union_index = torch.empty((0,), dtype=torch.long)
        negation_mask = torch.empty((0,), dtype=torch.bool)
        thresholds = torch.empty((0,), dtype=torch.float32)
        pair_weights = torch.empty((0,), dtype=torch.float32)
        group_thresholds = torch.empty((0,), dtype=torch.float32)
        group_weights = torch.empty((0,), dtype=torch.float32)

    if clash_pair_index:
        clash_pair_index = torch.tensor(clash_pair_index, dtype=torch.long).T
        clash_thresholds = torch.full(
            (clash_pair_index.shape[1],),
            clash_distance,
            dtype=torch.float32,
        )
    else:
        clash_pair_index = torch.empty((2, 0), dtype=torch.long)
        clash_thresholds = torch.empty((0,), dtype=torch.float32)

    return {
        "interface_contact_pair_index": pair_index,
        "interface_contact_union_index": union_index,
        "interface_contact_negation_mask": negation_mask,
        "interface_contact_thresholds": thresholds,
        "interface_contact_pair_weights": pair_weights,
        "interface_contact_group_thresholds": group_thresholds,
        "interface_contact_group_weights": group_weights,
        "interface_clash_pair_index": clash_pair_index,
        "interface_clash_thresholds": clash_thresholds,
    }

'''


def patch_interface_feature_separation(path: Path) -> bool:
    """Keep interface-only tensors separate from native token-contact features."""
    text = path.read_text(encoding="utf-8")
    marker = '"interface_contact_pair_index"'
    if marker in text:
        return False

    helper_start = text.index("def apply_interface_contact_potentials(")
    helper_end = text.index("\ndef process_contact_feature_constraints(", helper_start)
    old_helper = text[helper_start:helper_end]
    new_helper = interface_features_v2_source()
    text = text[:helper_start] + new_helper + text[helper_end + 1:]

    call_anchor = '''    union_idx = apply_interface_contact_potentials(
        token_data,
        inference_interface_contact_constraints,
        pair_index,
        union_index,
        negation_mask,
        thresholds,
        union_idx,
    )

    if len(pair_index) > 0:
'''
    call_replacement = '''    interface_features = apply_interface_contact_potentials(
        data,
        inference_interface_contact_constraints,
    )

    if len(pair_index) > 0:
'''
    text = replace_once(
        text,
        call_anchor,
        call_replacement,
        "separate interface potential features",
    )

    return_anchor = '''    return {
        "contact_pair_index": pair_index,
        "contact_union_index": union_index,
        "contact_negation_mask": negation_mask,
        "contact_thresholds": thresholds,
    }
'''
    return_replacement = '''    return {
        "contact_pair_index": pair_index,
        "contact_union_index": union_index,
        "contact_negation_mask": negation_mask,
        "contact_thresholds": thresholds,
        **interface_features,
    }
'''
    text = replace_once(
        text,
        return_anchor,
        return_replacement,
        "return separate interface potential features",
    )
    if old_helper == new_helper:
        raise RuntimeError("Interface feature separation did not change the helper.")
    return write_if_changed(path, text)


def patch_interface_features_v2(path: Path) -> bool:
    """Upgrade an already-patched image to reciprocal AIR interface features."""
    text = path.read_text(encoding="utf-8")
    if (
        INTERFACE_FEATURES_V2_MARKER in text
        and INTERFACE_FEATURES_CYCLIC_MARKER in text
        and INTERFACE_FEATURES_CROP_MARKER in text
        and INTERFACE_FEATURES_AIR_MARKER in text
    ):
        return False
    helper_start = text.index("def apply_interface_contact_potentials(")
    helper_end = text.index("\ndef process_contact_feature_constraints(", helper_start)
    text = (
        text[:helper_start]
        + interface_features_v2_source()
        + text[helper_end + 1:]
    )
    call_anchor = '''    interface_features = apply_interface_contact_potentials(
        token_data,
        inference_interface_contact_constraints,
    )
'''
    call_replacement = '''    interface_features = apply_interface_contact_potentials(
        data,
        inference_interface_contact_constraints,
    )
'''
    if call_anchor in text:
        text = replace_once(
            text,
            call_anchor,
            call_replacement,
            "pass tokenized data to interface feature builder",
        )
    return write_if_changed(path, text)


def patch_potentials(path: Path) -> bool:
    """Use exact hard-OR energies and residue-coherent interface gradients."""
    text = path.read_text(encoding="utf-8")
    if all(marker in text for marker in PATCH_MARKERS["potentials.py"]):
        return False

    class_anchor = "class Potential(ABC):\n"
    helper = '''def hard_union_reduction(energy, union_index):
    """Return per-group minima and equal subgradients for exact ties."""
    expanded_index = union_index.expand_as(energy)
    group_count = int(union_index.max().item()) + 1
    group_shape = (*energy.shape[:-1], group_count)
    minima = torch.full(
        group_shape,
        torch.inf,
        dtype=energy.dtype,
        device=energy.device,
    ).scatter_reduce(-1, expanded_index, energy, "amin")
    selected = energy == minima[..., union_index]
    tie_count = torch.zeros(
        group_shape,
        dtype=energy.dtype,
        device=energy.device,
    ).scatter_reduce(
        -1,
        expanded_index,
        selected.to(dtype=energy.dtype),
        "sum",
    )
    derivative_weight = (
        selected.to(dtype=energy.dtype)
        / tie_count[..., union_index].clamp_min(1.0)
    )
    return minima, derivative_weight


class Potential(ABC):
'''
    text = replace_once(text, class_anchor, helper, "hard union reduction helper")

    compute_anchor = '''        if union_index is not None:
            neg_exp_energy = torch.exp(-1 * parameters["union_lambda"] * energy)
            Z = torch.zeros(
                (*energy.shape[:-1], union_index.max() + 1), device=union_index.device
            ).scatter_reduce(
                -1,
                union_index.expand_as(neg_exp_energy),
                neg_exp_energy,
                "sum",
            )
            softmax_energy = neg_exp_energy / Z[..., union_index]
            softmax_energy[Z[..., union_index] == 0] = 0
            return (energy * softmax_energy).sum(dim=-1)
'''
    compute_replacement = '''        if union_index is not None:
            minimum_energy, _ = hard_union_reduction(energy, union_index)
            return minimum_energy.sum(dim=-1)
'''
    text = replace_once(
        text,
        compute_anchor,
        compute_replacement,
        "exact hard-OR potential energy",
    )

    gradient_anchor = '''        if union_index is not None:
            neg_exp_energy = torch.exp(-1 * parameters["union_lambda"] * energy)
            Z = torch.zeros(
                (*energy.shape[:-1], union_index.max() + 1), device=union_index.device
            ).scatter_reduce(
                -1,
                union_index.expand_as(energy),
                neg_exp_energy,
                "sum",
            )
            softmax_energy = neg_exp_energy / Z[..., union_index]
            softmax_energy[Z[..., union_index] == 0] = 0
            f = torch.zeros(
                (*energy.shape[:-1], union_index.max() + 1), device=union_index.device
            ).scatter_reduce(
                -1,
                union_index.expand_as(energy),
                energy * softmax_energy,
                "sum",
            )
            dSoftmax = (
                dEnergy
                * softmax_energy
                * (1 + parameters["union_lambda"] * (energy - f[..., union_index]))
            )
            prod = dSoftmax.tile(grad_value.shape[-3]).unsqueeze(
                -1
            ) * grad_value.flatten(start_dim=-3, end_dim=-2)
'''
    gradient_replacement = '''        if union_index is not None:
            _, derivative_weight = hard_union_reduction(energy, union_index)
            dUnion = dEnergy * derivative_weight
            prod = dUnion.tile(grad_value.shape[-3]).unsqueeze(
                -1
            ) * grad_value.flatten(start_dim=-3, end_dim=-2)
'''
    text = replace_once(
        text,
        gradient_anchor,
        gradient_replacement,
        "exact hard-OR potential gradient",
    )

    contact_anchor = '''class ContactPotentital(FlatBottomPotential, DistancePotential):
    def compute_args(self, feats, parameters):
        index = feats["contact_pair_index"][0]
        union_index = feats["contact_union_index"][0]
        negation_mask = feats["contact_negation_mask"][0]
        lower_bounds = None
        upper_bounds = feats["contact_thresholds"][0].clone()
        k = torch.ones_like(upper_bounds)
        return (
            index,
            (k, lower_bounds, upper_bounds),
            None,
            None,
            (negation_mask, union_index),
        )


def get_potentials(steering_args, boltz2=False):
'''
    contact_replacement = '''class ContactPotentital(FlatBottomPotential, DistancePotential):
    feature_prefix = "contact"

    def compute_args(self, feats, parameters):
        prefix = self.feature_prefix
        index = feats[f"{prefix}_pair_index"][0]
        union_index = feats[f"{prefix}_union_index"][0]
        negation_mask = feats[f"{prefix}_negation_mask"][0]
        lower_bounds = None
        upper_bounds = feats[f"{prefix}_thresholds"][0].clone()
        k = torch.ones_like(upper_bounds)
        return (
            index,
            (k, lower_bounds, upper_bounds),
            None,
            None,
            (negation_mask, union_index),
        )


class InterfaceContactPotentital(ContactPotentital):
    """Interface contact potential that translates residues instead of atoms."""

    feature_prefix = "interface_contact"

    def compute_gradient(self, coords, feats, parameters):
        atom_gradient = super().compute_gradient(coords, feats, parameters)
        atom_to_token = feats["atom_to_token"][0].to(
            device=atom_gradient.device,
            dtype=atom_gradient.dtype,
        )
        atom_pad_mask = feats["atom_pad_mask"][0].to(
            device=atom_gradient.device,
            dtype=atom_gradient.dtype,
        )
        atom_to_token = atom_to_token * atom_pad_mask.unsqueeze(-1)
        token_gradient = torch.einsum(
            "at,...ad->...td",
            atom_to_token,
            atom_gradient,
        )
        gradient_norm = torch.linalg.vector_norm(
            token_gradient,
            dim=-1,
            keepdim=True,
        )
        token_gradient = token_gradient / gradient_norm.clamp_min(1.0)
        return torch.einsum(
            "at,...td->...ad",
            atom_to_token,
            token_gradient,
        )


def get_potentials(steering_args, boltz2=False):
'''
    text = replace_once(
        text,
        contact_anchor,
        contact_replacement,
        "residue-coherent interface potential",
    )

    potential_list_anchor = '''                ContactPotentital(
                    parameters={
                        "guidance_interval": 4,
                        "guidance_weight": (
                            PiecewiseStepFunction(
                                thresholds=[0.25, 0.75], values=[0.0, 0.5, 1.0]
                            )
                            if steering_args["contact_guidance_update"]
                            else 0.0
                        ),
                        "resampling_weight": 1.0,
                        "union_lambda": ExponentialInterpolation(
                            start=8.0, end=0.0, alpha=-2.0
                        ),
                    }
                ),
                TemplateReferencePotential(
'''
    potential_list_replacement = '''                ContactPotentital(
                    parameters={
                        "guidance_interval": 4,
                        "guidance_weight": (
                            PiecewiseStepFunction(
                                thresholds=[0.25, 0.75], values=[0.0, 0.5, 1.0]
                            )
                            if steering_args["contact_guidance_update"]
                            else 0.0
                        ),
                        "resampling_weight": 1.0,
                    }
                ),
                InterfaceContactPotentital(
                    parameters={
                        "guidance_interval": 4,
                        "guidance_weight": (
                            PiecewiseStepFunction(
                                thresholds=[0.25, 0.75], values=[0.0, 0.5, 1.0]
                            )
                            if steering_args["contact_guidance_update"]
                            else 0.0
                        ),
                        "resampling_weight": 1.0,
                    }
                ),
                TemplateReferencePotential(
'''
    text = replace_once(
        text,
        potential_list_anchor,
        potential_list_replacement,
        "register interface contact potential",
    )
    return write_if_changed(path, text)


def interface_potentials_v2_source() -> str:
    return '''def translate_interface_gradient(atom_gradient, feats, max_norm):
    """Convert sparse atom forces into capped rigid translations per residue."""
    atom_to_token = feats["atom_to_token"][0].to(
        device=atom_gradient.device,
        dtype=atom_gradient.dtype,
    )
    atom_pad_mask = feats["atom_pad_mask"][0].to(
        device=atom_gradient.device,
        dtype=atom_gradient.dtype,
    )
    atom_to_token = atom_to_token * atom_pad_mask.unsqueeze(-1)
    token_gradient = torch.einsum(
        "at,...ad->...td",
        atom_to_token,
        atom_gradient,
    )
    gradient_norm = torch.linalg.vector_norm(
        token_gradient,
        dim=-1,
        keepdim=True,
    )
    cap = torch.as_tensor(
        max_norm,
        dtype=token_gradient.dtype,
        device=token_gradient.device,
    )
    token_gradient = token_gradient * cap / gradient_norm.clamp_min(cap)
    return torch.einsum(
        "at,...td->...ad",
        atom_to_token,
        token_gradient,
    )


class InterfaceContactPotentital(ContactPotentital):
    """Literal heavy-atom reciprocal AIR guidance with a bounded robust loss."""

    feature_prefix = "interface_contact"

    def _geometry(self, coords, feats):
        pair_index = feats["interface_contact_pair_index"][0].to(
            device=coords.device
        )
        if pair_index.shape[1] == 0:
            return None
        group_index = feats["interface_contact_union_index"][0].to(
            device=coords.device
        )
        group_thresholds = feats["interface_contact_group_thresholds"][0].to(
            device=coords.device,
            dtype=coords.dtype,
        )
        group_weights = feats["interface_contact_group_weights"][0].to(
            device=coords.device,
            dtype=coords.dtype,
        )
        delta = (
            coords.index_select(-2, pair_index[0])
            - coords.index_select(-2, pair_index[1])
        )
        raw_distance = torch.linalg.vector_norm(delta, dim=-1)
        pair_shape = (*([1] * (raw_distance.dim() - 1)), -1)
        expanded_group_index = group_index.view(pair_shape).expand_as(
            raw_distance
        )
        group_shape = (*raw_distance.shape[:-1], group_thresholds.numel())
        minimum_distance = torch.full(
            group_shape,
            torch.inf,
            dtype=coords.dtype,
            device=coords.device,
        ).scatter_reduce(
            -1,
            expanded_group_index,
            raw_distance,
            "amin",
        )
        return (
            pair_index,
            group_index,
            group_thresholds,
            group_weights,
            delta,
            raw_distance,
            minimum_distance,
        )

    def compute(self, coords, feats, parameters):
        geometry = self._geometry(coords, feats)
        if geometry is None:
            return torch.zeros(
                coords.shape[:-2],
                dtype=coords.dtype,
                device=coords.device,
            )
        (
            _,
            _,
            group_thresholds,
            group_weights,
            _,
            _,
            minimum_distance,
        ) = geometry
        group_shape = (*([1] * (minimum_distance.dim() - 1)), -1)
        violation = torch.relu(
            minimum_distance - group_thresholds.view(group_shape)
        )
        huber_delta = parameters.get("huber_delta", 2.0)
        penalty = torch.where(
            violation <= huber_delta,
            violation.square() / (2.0 * huber_delta),
            violation - (0.5 * huber_delta),
        )
        return (penalty * group_weights.view(group_shape)).sum(dim=-1)

    def compute_gradient(self, coords, feats, parameters):
        geometry = self._geometry(coords, feats)
        if geometry is None:
            return torch.zeros_like(coords)
        (
            pair_index,
            group_index,
            group_thresholds,
            group_weights,
            delta,
            raw_distance,
            minimum_distance,
        ) = geometry
        group_shape = (*([1] * (minimum_distance.dim() - 1)), -1)
        violation = torch.relu(
            minimum_distance - group_thresholds.view(group_shape)
        )
        huber_delta = parameters.get("huber_delta", 2.0)
        huber_slope = (violation / huber_delta).clamp(max=1.0)
        gradient_strength = parameters.get("gradient_strength", 4.0)
        group_coefficient = (
            huber_slope
            * group_weights.view(group_shape)
            * gradient_strength
        )
        minimum_by_pair = minimum_distance.index_select(-1, group_index)
        active_pair = (
            (raw_distance == minimum_by_pair)
            & (group_coefficient.index_select(-1, group_index) > 0.0)
        ).to(dtype=coords.dtype)
        pair_shape = (*([1] * (raw_distance.dim() - 1)), -1)
        expanded_group_index = group_index.view(pair_shape).expand_as(
            raw_distance
        )
        tie_count = torch.zeros(
            (*raw_distance.shape[:-1], group_thresholds.numel()),
            dtype=coords.dtype,
            device=coords.device,
        ).scatter_add(
            -1,
            expanded_group_index,
            active_pair,
        )
        tie_count_by_pair = tie_count.index_select(
            -1,
            group_index,
        ).clamp_min(1.0)
        coefficient_by_pair = group_coefficient.index_select(
            -1,
            group_index,
        ) * active_pair / tie_count_by_pair
        direction = delta / raw_distance.clamp_min(1e-6).unsqueeze(-1)
        pair_gradient = coefficient_by_pair.unsqueeze(-1) * direction
        atom_gradient = torch.zeros_like(coords)
        index_shape = (*([1] * (coords.dim() - 2)), -1, 1)
        output_shape = (*coords.shape[:-2], pair_index.shape[1], 3)
        first_index = pair_index[0].view(index_shape).expand(output_shape)
        second_index = pair_index[1].view(index_shape).expand(output_shape)
        atom_gradient.scatter_add_(-2, first_index, pair_gradient)
        atom_gradient.scatter_add_(-2, second_index, -pair_gradient)
        return translate_interface_gradient(
            atom_gradient,
            feats,
            parameters["max_token_gradient"],
        )


class InterfaceClashPotentital(FlatBottomPotential, DistancePotential):
    """Repel severe cross-patch overlaps without changing native contacts."""

    def compute_args(self, feats, parameters):
        index = feats["interface_clash_pair_index"][0]
        lower_bounds = feats["interface_clash_thresholds"][0].clone()
        upper_bounds = None
        k = torch.full_like(lower_bounds, parameters["clash_strength"])
        return (
            index,
            (k, lower_bounds, upper_bounds),
            None,
            None,
            None,
        )

    def compute_gradient(self, coords, feats, parameters):
        atom_gradient = super().compute_gradient(coords, feats, parameters)
        atom_gradient = torch.nan_to_num(
            atom_gradient,
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        return translate_interface_gradient(
            atom_gradient,
            feats,
            parameters["max_token_gradient"],
        )


'''


def patch_interface_potentials_v2(path: Path) -> bool:
    """Upgrade an already-patched image without changing native contact code."""
    text = path.read_text(encoding="utf-8")
    if (
        INTERFACE_POTENTIALS_V2_MARKER in text
        and text.count("InterfaceClashPotentital(") >= 2
        and INTERFACE_POTENTIALS_RESAMPLING_MARKER in text
        and INTERFACE_POTENTIALS_AIR_MARKER in text
        and INTERFACE_POTENTIALS_AIR_REGISTRATION_MARKER in text
    ):
        return False

    class_start = text.index("class InterfaceContactPotentital(")
    class_end = text.index("\ndef get_potentials(", class_start)
    text = (
        text[:class_start]
        + interface_potentials_v2_source()
        + text[class_end + 1:]
    )

    registration_anchor = '''                InterfaceContactPotentital(
                    parameters={
                        "guidance_interval": 4,
                        "guidance_weight": (
                            PiecewiseStepFunction(
                                thresholds=[0.25, 0.75], values=[0.0, 0.5, 1.0]
                            )
                            if steering_args["contact_guidance_update"]
                            else 0.0
                        ),
                        "resampling_weight": 1.0,
                    }
                ),
                TemplateReferencePotential(
'''
    registration_replacement = '''                InterfaceContactPotentital(
                    parameters={
                        "guidance_interval": 4,
                        "guidance_weight": (
                            PiecewiseStepFunction(
                                thresholds=[0.25, 0.75], values=[0.0, 0.5, 1.0]
                            )
                            if steering_args["contact_guidance_update"]
                            else 0.0
                        ),
                        # Reciprocal per-active-residue AIR energy participates in particle resampling.
                        "resampling_weight": 1.0,
                        "max_token_gradient": 0.5,
                        "huber_delta": 2.0,
                        "gradient_strength": 4.0,
                    }
                ),
                InterfaceClashPotentital(
                    parameters={
                        "guidance_interval": 4,
                        "guidance_weight": (
                            PiecewiseStepFunction(
                                thresholds=[0.25, 0.75], values=[0.0, 0.5, 1.0]
                            )
                            if steering_args["contact_guidance_update"]
                            else 0.0
                        ),
                        "resampling_weight": 0.0,
                        "clash_strength": 0.5,
                        "max_token_gradient": 0.5,
                    }
                ),
                TemplateReferencePotential(
'''
    if registration_anchor in text:
        text = replace_once(
            text,
            registration_anchor,
            registration_replacement,
            "register interface AIR and clash potentials",
        )
    else:
        existing_v2_anchor = '''                        "resampling_weight": 1.0,
                        "max_token_gradient": 0.5,
                    }
                ),
                InterfaceClashPotentital(
'''
        existing_v2_replacement = '''                        # Reciprocal per-active-residue AIR energy participates in particle resampling.
                        "resampling_weight": 1.0,
                        "max_token_gradient": 0.5,
                        "huber_delta": 2.0,
                        "gradient_strength": 4.0,
                    }
                ),
                InterfaceClashPotentital(
'''
        minimax_resampling_anchor = '''                        # Reciprocal minimax interface energy participates in particle resampling.
                        "resampling_weight": 1.0,
                        "max_token_gradient": 0.5,
                    }
                ),
                InterfaceClashPotentital(
'''
        calibrated_resampling_anchor = '''                        # Interface energy participates in calibrated particle resampling.
                        "resampling_weight": 1.0,
                        "max_token_gradient": 0.5,
                    }
                ),
                InterfaceClashPotentital(
'''
        if minimax_resampling_anchor in text:
            text = replace_once(
                text,
                minimax_resampling_anchor,
                existing_v2_replacement,
                "migrate minimax interface particle resampling",
            )
        elif calibrated_resampling_anchor in text:
            text = replace_once(
                text,
                calibrated_resampling_anchor,
                existing_v2_replacement,
                "migrate calibrated interface particle resampling",
            )
        elif existing_v2_anchor in text:
            text = replace_once(
                text,
                existing_v2_anchor,
                existing_v2_replacement,
                "register interface AIR particle resampling",
            )
        else:
            no_resampling_anchor = '''                        # Interface energy is excluded from particle resampling.
                        "resampling_weight": 0.0,
                        "max_token_gradient": 0.5,
                    }
                ),
                InterfaceClashPotentital(
'''
            text = replace_once(
                text,
                no_resampling_anchor,
                existing_v2_replacement,
                "restore interface AIR particle resampling",
            )
    return write_if_changed(path, text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the Boltz version and source hashes without modifying files.",
    )
    parser.add_argument(
        "--verify-applied",
        action="store_true",
        help="Verify that the complete interface-v2 runtime patch is installed.",
    )
    args = parser.parse_args()
    paths = {
        "schema.py": Path(inspect.getfile(schema)),
        "types.py": Path(inspect.getfile(types)),
        "inferencev2.py": Path(inspect.getfile(inferencev2)),
        "featurizerv2.py": Path(inspect.getfile(featurizerv2)),
        "diffusionv2.py": Path(inspect.getfile(diffusionv2)),
        "potentials.py": Path(inspect.getfile(potentials)),
    }

    print("boltz version:", getattr(boltz, "__version__", "unknown"))
    for label, path in paths.items():
        print(f"{label}: {path}")

    check_compatibility(paths)
    if args.verify_applied:
        verify_applied_patch(paths)
        return
    if args.check:
        print("Boltz atom_contact patch compatibility check passed.")
        return

    changed = {
        "schema.py": patch_schema(paths["schema.py"]),
        "types.py": patch_types(paths["types.py"]),
        "inferencev2.py": patch_inferencev2(paths["inferencev2.py"]),
        "featurizerv2.py": patch_featurizerv2(paths["featurizerv2.py"]),
        "diffusionv2.py": patch_diffusionv2(paths["diffusionv2.py"]),
        "potentials.py": patch_potentials(paths["potentials.py"]),
    }
    changed["schema.py"] = (
        patch_exact_atom_validation(paths["schema.py"]) or changed["schema.py"]
    )
    changed["featurizerv2.py"] = (
        patch_exact_token_conditioning(paths["featurizerv2.py"])
        or changed["featurizerv2.py"]
    )
    interface_changed = {
        "schema.py": patch_interface_schema(paths["schema.py"]),
        "types.py": patch_interface_types(paths["types.py"]),
        "inferencev2.py": patch_interface_inferencev2(paths["inferencev2.py"]),
        "featurizerv2.py": patch_interface_featurizerv2(paths["featurizerv2.py"]),
    }
    for label, was_changed in interface_changed.items():
        changed[label] = changed[label] or was_changed
    changed["inferencev2.py"] = (
        patch_interface_failure_propagation(paths["inferencev2.py"])
        or changed["inferencev2.py"]
    )
    changed["schema.py"] = (
        patch_interface_schema_v2(paths["schema.py"]) or changed["schema.py"]
    )
    changed["schema.py"] = (
        patch_interface_schema_neighbor_validation(paths["schema.py"])
        or changed["schema.py"]
    )
    changed["featurizerv2.py"] = (
        patch_interface_feature_separation(paths["featurizerv2.py"])
        or changed["featurizerv2.py"]
    )
    changed["featurizerv2.py"] = (
        patch_interface_features_v2(paths["featurizerv2.py"])
        or changed["featurizerv2.py"]
    )
    changed["potentials.py"] = (
        patch_interface_potentials_v2(paths["potentials.py"])
        or changed["potentials.py"]
    )

    for label, was_changed in changed.items():
        print(f"{label}: {'patched' if was_changed else 'already patched'}")

    for path in paths.values():
        py_compile.compile(str(path), doraise=True)
    print("Boltz atom_contact patch compiled successfully.")


if __name__ == "__main__":
    main()
