#!/usr/bin/env python3
"""Patch Boltz 2.2.1 atom contacts and diffusion sample chunking."""

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


EXPECTED_BOLTZ_VERSION = "2.2.1"
EXPECTED_SOURCE_SHA256 = {
    "schema.py": "c0dae4c89c4c4a22175a433b5a0c68860329d2a292c76224328bdde19b73b743",
    "types.py": "e7e5ede40e0c208bcb966acd04caebb3b017e8a50b85b1aa3cae4cdf83b71707",
    "inferencev2.py": "675235dff103d698dc65f2ebaca85a62b664ab28cd09f4b1c0166e6e56b47db4",
    "featurizerv2.py": "af1f9e6ec0c3d7289eb1f7503c3c1c3ee0d9f03436778dd4a7d412b8f7bd9f94",
    "diffusionv2.py": "9eacc8cf7daeb62dffa81a09a1f93d2e268a4b7b68b5b88c2058c5ebf5ca4057",
}
PATCH_MARKERS = {
    "schema.py": ("atom_contact_constraints", "def atom_contact_spec_to_ids"),
    "types.py": ("atom_contact_constraints",),
    "inferencev2.py": ("atom_contact_constraints",),
    "featurizerv2.py": ("inference_atom_contact_constraints",),
    "diffusionv2.py": ("sample_ids.split(max_parallel_samples)",),
}


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
    if "atom_contact_constraints" in text and "def atom_contact_spec_to_ids" in text:
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
                    "distance guidance is implemented through a soft inference-time potential."
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
            atom_contact_constraints.append((atom1, atom2, max_distance, force))
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
    )
'''
    text = replace_once(text, options_anchor, options_replacement, "schema InferenceOptions")

    return write_if_changed(path, text)


def patch_types(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "atom_contact_constraints" in text:
        return False

    anchor = '''    contact_constraints: Optional[
        list[tuple[tuple[int, int], tuple[int, int], float, bool]]
    ] = None
'''
    replacement = anchor + '''    atom_contact_constraints: Optional[
        list[tuple[tuple[int, int, int], tuple[int, int, int], float, bool]]
    ] = None
'''
    text = replace_once(text, anchor, replacement, "types atom_contact field")
    return write_if_changed(path, text)


def patch_inferencev2(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "atom_contact_constraints" in text:
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
            pocket_constraints, contact_constraints, atom_contact_constraints = None, None, None
        else:
            pocket_constraints, contact_constraints, atom_contact_constraints = (
                options.pocket_constraints,
                options.contact_constraints,
                options.atom_contact_constraints,
            )
'''
    text = replace_once(text, options_anchor, options_replacement, "inference atom_contact options")

    call_anchor = '''                inference_pocket_constraints=pocket_constraints,
                inference_contact_constraints=contact_constraints,
                compute_constraint_features=True,
'''
    call_replacement = '''                inference_pocket_constraints=pocket_constraints,
                inference_contact_constraints=contact_constraints,
                inference_atom_contact_constraints=atom_contact_constraints,
                compute_constraint_features=True,
'''
    text = replace_once(text, call_anchor, call_replacement, "inference featurizer call")
    return write_if_changed(path, text)


def patch_featurizerv2(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "inference_atom_contact_constraints" in text:
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
            )
'''
    text = replace_once(text, contact_call_anchor, contact_call_replacement, "contact feature call")

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the Boltz version and source hashes without modifying files.",
    )
    args = parser.parse_args()
    paths = {
        "schema.py": Path(inspect.getfile(schema)),
        "types.py": Path(inspect.getfile(types)),
        "inferencev2.py": Path(inspect.getfile(inferencev2)),
        "featurizerv2.py": Path(inspect.getfile(featurizerv2)),
        "diffusionv2.py": Path(inspect.getfile(diffusionv2)),
    }

    print("boltz version:", getattr(boltz, "__version__", "unknown"))
    for label, path in paths.items():
        print(f"{label}: {path}")

    check_compatibility(paths)
    if args.check:
        print("Boltz atom_contact patch compatibility check passed.")
        return

    changed = {
        "schema.py": patch_schema(paths["schema.py"]),
        "types.py": patch_types(paths["types.py"]),
        "inferencev2.py": patch_inferencev2(paths["inferencev2.py"]),
        "featurizerv2.py": patch_featurizerv2(paths["featurizerv2.py"]),
        "diffusionv2.py": patch_diffusionv2(paths["diffusionv2.py"]),
    }

    for label, was_changed in changed.items():
        print(f"{label}: {'patched' if was_changed else 'already patched'}")

    for path in paths.values():
        py_compile.compile(str(path), doraise=True)
    print("Boltz atom_contact patch compiled successfully.")


if __name__ == "__main__":
    main()
