#!/usr/bin/env python3
"""Add neutral-pH hydrogens and optionally minimize Boltz structures."""

from __future__ import annotations

import hashlib
from importlib.metadata import PackageNotFoundError, version as package_version
import json
import math
import os
from pathlib import Path
import platform as python_platform
import tempfile
from datetime import datetime, timezone
from typing import Any


PH = 7.0
FORCEFIELD_FILES = ("amber14-all.xml", "implicit/gbn2.xml")
MINIMIZATION_TOLERANCE = 10.0
MINIMIZATION_MAX_ITERATIONS = 250
STANDARD_RESIDUES = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
    "A", "C", "G", "U", "DA", "DC", "DG", "DT",
}
STRUCTURE_EXTENSIONS = {".pdb", ".cif", ".mmcif"}


class PostprocessError(RuntimeError):
    """Raised when a structure cannot be safely post-processed."""


def _dependencies():
    try:
        import openmm
        from openmm import app, unit
        from pdbfixer import PDBFixer
    except ImportError as exc:
        raise PostprocessError(
            "Hydrogen post-processing requires OpenMM and PDBFixer. "
            "Use the BoltzUI Docker image or install requirements-postprocess.txt."
        ) from exc
    return openmm, app, unit, PDBFixer


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _pdb_confidence_maps(path: Path) -> tuple[dict[tuple[str, str, str, str], float], dict[tuple[str, str, str], float]]:
    atom_values: dict[tuple[str, str, str, str], float] = {}
    residue_values: dict[tuple[str, str, str], list[float]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith(("ATOM  ", "HETATM")) or len(line) < 66:
            continue
        try:
            value = float(line[60:66])
        except ValueError:
            continue
        residue_key = (line[21:22], line[22:27], line[17:20])
        atom_values[(*residue_key, line[12:16])] = value
        residue_values.setdefault(residue_key, []).append(value)
    return atom_values, {key: sum(values) / len(values) for key, values in residue_values.items()}


def _apply_pdb_confidence(source: Path, output: Path) -> bool:
    atom_values, residue_values = _pdb_confidence_maps(source)
    if not atom_values:
        return False
    changed = False
    lines = output.read_text(encoding="utf-8").splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.startswith(("ATOM  ", "HETATM")) or len(line) < 66:
            continue
        residue_key = (line[21:22], line[22:27], line[17:20])
        value = atom_values.get((*residue_key, line[12:16]), residue_values.get(residue_key))
        if value is None:
            continue
        lines[index] = f"{line[:60]}{value:6.2f}{line[66:]}"
        changed = True
    if changed:
        output.write_text("".join(lines), encoding="utf-8")
    return changed


def _atomic_structure(path: Path, topology: Any, positions: Any, app: Any, source: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        if path.suffix.lower() == ".pdb":
            app.PDBFile.writeFile(topology, positions, handle, keepIds=True)
        else:
            app.PDBxFile.writeFile(topology, positions, handle, keepIds=True)
        temporary = Path(handle.name)
    try:
        confidence_preserved = path.suffix.lower() == ".pdb" and _apply_pdb_confidence(source, temporary)
        os.replace(temporary, path)
        return confidence_preserved
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _residue_label(residue: Any) -> str:
    chain_id = residue.chain.id or str(residue.chain.index + 1)
    return f"{chain_id}:{residue.id}:{residue.name}"


def _topology_counts(topology: Any) -> dict[str, int]:
    atoms = list(topology.atoms())
    hydrogen_count = sum(atom.element is not None and atom.element.symbol == "H" for atom in atoms)
    return {
        "atoms": len(atoms),
        "heavy_atoms": len(atoms) - hydrogen_count,
        "hydrogens": hydrogen_count,
        "residues": sum(1 for _ in topology.residues()),
        "chains": sum(1 for _ in topology.chains()),
    }


def _normalize_nucleic_5prime_phosphates(modeller: Any) -> list[dict[str, Any]]:
    """Convert Boltz's first-residue phosphate to Amber's standard 5'-OH terminus."""
    changes = []
    atoms_to_delete = []
    for chain in list(modeller.topology.chains()):
        residues = list(chain.residues())
        if not residues or residues[0].name.upper() not in {"A", "C", "G", "U", "DA", "DC", "DG", "DT"}:
            continue
        residue = residues[0]
        atoms = {atom.name: atom for atom in residue.atoms()}
        phosphate_names = [name for name in ("P", "OP1", "OP2") if name in atoms]
        if len(phosphate_names) != 3 or "O5'" not in atoms:
            continue
        atoms_to_delete.extend(atoms[name] for name in phosphate_names)
        changes.append({
            "residue": _residue_label(residue),
            "atoms": phosphate_names,
            "reason": "Normalized Boltz's 5-prime phosphate to the Amber OL3/OL15 5-prime hydroxyl terminus.",
        })
    if atoms_to_delete:
        modeller.delete(atoms_to_delete)
    return changes


def _positions_nanometers(positions: Any, unit: Any) -> list[tuple[float, float, float]]:
    values = positions.value_in_unit(unit.nanometer)
    return [(float(value[0]), float(value[1]), float(value[2])) for value in values]


def _select_platform(openmm: Any) -> tuple[Any, dict[str, str]]:
    available = {
        openmm.Platform.getPlatform(index).getName(): openmm.Platform.getPlatform(index)
        for index in range(openmm.Platform.getNumPlatforms())
    }
    for name in ("CUDA", "OpenCL", "CPU"):
        if name not in available:
            continue
        platform = available[name]
        property_names = set(platform.getPropertyNames())
        properties: dict[str, str] = {}
        if "Precision" in property_names and name in {"CUDA", "OpenCL"}:
            properties["Precision"] = "mixed"
        if "DeterministicForces" in property_names and name == "CUDA":
            properties["DeterministicForces"] = "true"
        return platform, properties
    raise PostprocessError("No supported OpenMM CUDA, OpenCL, or CPU platform is available.")


def _heavy_atom_rmsd(before: Any, after: Any, topology: Any, unit: Any) -> tuple[float, float]:
    before_nm = _positions_nanometers(before, unit)
    after_nm = _positions_nanometers(after, unit)
    squared = []
    for atom, first, second in zip(topology.atoms(), before_nm, after_nm):
        if atom.element is not None and atom.element.symbol == "H":
            continue
        displacement = math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second))) * 10.0
        squared.append(displacement * displacement)
    if not squared:
        return 0.0, 0.0
    return math.sqrt(sum(squared) / len(squared)), math.sqrt(max(squared))


def _validate_and_repair(source: Path, PDBFixer: Any) -> tuple[Any, dict[str, Any]]:
    fixer = PDBFixer(filename=str(source))
    residues = list(fixer.topology.residues())
    unsupported = sorted({_residue_label(residue) for residue in residues if residue.name.upper() not in STANDARD_RESIDUES})
    if unsupported:
        preview = ", ".join(unsupported[:8])
        suffix = " ..." if len(unsupported) > 8 else ""
        raise PostprocessError(
            "Unsupported residue(s) for the Amber14 protein/RNA/DNA post-processor: "
            f"{preview}{suffix}. Ligands and modified residues require an explicitly parameterized force field."
        )

    fixer.findMissingResidues()
    missing_residues = [
        {"chain_index": int(chain_index), "residue_index": int(residue_index), "names": list(names)}
        for (chain_index, residue_index), names in fixer.missingResidues.items()
    ]
    # Never invent unresolved polymer segments in a predicted structure.
    fixer.missingResidues = {}

    fixer.findNonstandardResidues()
    if fixer.nonstandardResidues:
        labels = ", ".join(_residue_label(residue) for residue, _ in fixer.nonstandardResidues[:8])
        raise PostprocessError(f"Nonstandard residues require explicit parameterization: {labels}.")

    fixer.findMissingAtoms()
    missing_heavy_atoms = [
        {"residue": _residue_label(residue), "atoms": [atom.name for atom in atoms]}
        for residue, atoms in fixer.missingAtoms.items()
        if atoms
    ]
    if missing_heavy_atoms:
        details = "; ".join(f"{item['residue']} ({', '.join(item['atoms'])})" for item in missing_heavy_atoms[:8])
        raise PostprocessError(
            "The predicted structure is missing non-terminal heavy atoms; refusing to change its heavy-atom model: "
            f"{details}."
        )

    terminal_atoms = [
        {"residue": _residue_label(residue), "atoms": list(atoms)}
        for residue, atoms in fixer.missingTerminals.items()
        if atoms
    ]
    unexpected = [item for item in terminal_atoms if any(atom != "OXT" for atom in item["atoms"])]
    if unexpected:
        raise PostprocessError(f"Unexpected missing terminal atoms: {unexpected}.")
    if terminal_atoms:
        fixer.addMissingAtoms()

    return fixer, {
        "unresolved_missing_residue_segments_not_built": missing_residues,
        "terminal_heavy_atoms_added": terminal_atoms,
    }


def process_structure(source: Path, output: Path, mode: str) -> dict[str, Any]:
    if mode not in {"addh", "addh_energy_min"}:
        raise ValueError(f"Unsupported post-processing mode: {mode}")
    openmm, app, unit, PDBFixer = _dependencies()
    original_hash = _sha256(source)
    fixer, repairs = _validate_and_repair(source, PDBFixer)
    modeller = app.Modeller(fixer.topology, fixer.positions)
    before = _topology_counts(modeller.topology)
    removed_terminal_atoms = _normalize_nucleic_5prime_phosphates(modeller)
    after_terminal_normalization = _topology_counts(modeller.topology)
    hydrogen_forcefield = app.ForceField("amber14-all.xml")
    platform, platform_properties = _select_platform(openmm)
    variants = modeller.addHydrogens(hydrogen_forcefield, pH=PH, platform=platform)
    after_hydrogens = _topology_counts(modeller.topology)
    if after_hydrogens["hydrogens"] <= before["hydrogens"]:
        raise PostprocessError("OpenMM did not add any hydrogens to the structure.")

    energy = None
    displacement = None
    positions = modeller.positions
    if mode == "addh_energy_min":
        forcefield = app.ForceField(*FORCEFIELD_FILES)
        system = forcefield.createSystem(
            modeller.topology,
            nonbondedMethod=app.NoCutoff,
            constraints=app.HBonds,
            rigidWater=True,
            removeCMMotion=False,
        )
        integrator = openmm.VerletIntegrator(1.0 * unit.femtosecond)
        context = openmm.Context(system, integrator, platform, platform_properties)
        try:
            context.setPositions(modeller.positions)
            initial = context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
            openmm.LocalEnergyMinimizer.minimize(
                context,
                MINIMIZATION_TOLERANCE * unit.kilojoule_per_mole / unit.nanometer,
                MINIMIZATION_MAX_ITERATIONS,
            )
            final_state = context.getState(getEnergy=True, getPositions=True)
            final = final_state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
            positions = final_state.getPositions()
            rmsd, maximum = _heavy_atom_rmsd(modeller.positions, positions, modeller.topology, unit)
            energy = {
                "initial_kj_mol": float(initial),
                "final_kj_mol": float(final),
                "change_kj_mol": float(final - initial),
            }
            displacement = {"heavy_atom_rmsd_angstrom": rmsd, "maximum_heavy_atom_angstrom": maximum}
        finally:
            del context
            del integrator

    confidence_preserved = _atomic_structure(output, modeller.topology, positions, app, source)
    if _sha256(source) != original_hash:
        raise PostprocessError("The original Boltz structure changed during post-processing.")

    selected_variants = [
        {"residue": _residue_label(residue), "variant": variant}
        for residue, variant in zip(modeller.topology.residues(), variants)
        if variant is not None
    ]
    return {
        "status": "succeeded",
        "source_sha256": original_hash,
        "output_sha256": _sha256(output),
        "counts_before": before,
        "counts_after_terminal_normalization": after_terminal_normalization,
        "counts_after": _topology_counts(modeller.topology),
        "hydrogens_added": after_hydrogens["hydrogens"] - before["hydrogens"],
        "selected_protonation_variants": selected_variants,
        **repairs,
        "terminal_heavy_atoms_removed": removed_terminal_atoms,
        "potential_energy": energy,
        "coordinate_displacement": displacement,
        "openmm_platform": platform.getName(),
        "pdb_confidence_b_factors_preserved": confidence_preserved,
    }


def _source_files(predictions: Path) -> list[Path]:
    return sorted(
        path for path in predictions.rglob("*")
        if path.is_file() and path.suffix.lower() in STRUCTURE_EXTENSIONS
    )


def process_result_directory(result_directory: Path | str, mode: str) -> dict[str, Any]:
    result_directory = Path(result_directory).resolve()
    predictions = result_directory / "predictions"
    if not predictions.is_dir():
        raise PostprocessError(f"Boltz predictions directory was not found: {predictions}")
    sources = _source_files(predictions)
    if not sources:
        raise PostprocessError(f"No PDB or mmCIF models were found under {predictions}.")

    openmm, _, _, _ = _dependencies()
    try:
        pdbfixer_version = package_version("pdbfixer")
    except PackageNotFoundError:
        pdbfixer_version = "unknown"
    report_path = result_directory / "boltzui_postprocess.json"
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "running",
        "mode": mode,
        "started_at": _utc_now(),
        "completed_at": None,
        "configuration": {
            "pH": PH,
            "hydrogen_forcefield": ["amber14-all.xml"],
            "minimization_forcefield": list(FORCEFIELD_FILES) if mode == "addh_energy_min" else None,
            "implicit_solvent": "GBn2" if mode == "addh_energy_min" else None,
            "nonbonded_method": "NoCutoff" if mode == "addh_energy_min" else None,
            "constraints": "HBonds" if mode == "addh_energy_min" else None,
            "minimizer": "OpenMM LocalEnergyMinimizer (L-BFGS)" if mode == "addh_energy_min" else None,
            "tolerance_kj_mol_nm": MINIMIZATION_TOLERANCE if mode == "addh_energy_min" else None,
            "max_iterations": MINIMIZATION_MAX_ITERATIONS if mode == "addh_energy_min" else None,
            "platform_priority": ["CUDA", "OpenCL", "CPU"],
        },
        "software": {
            "openmm": getattr(openmm, "__version__", "unknown"),
            "pdbfixer": pdbfixer_version,
            "python": python_platform.python_version(),
        },
        "models": [],
        "summary": {"requested": len(sources), "succeeded": 0, "failed": 0},
    }
    suffix = "_addh_energy_min" if mode == "addh_energy_min" else "_addh"
    for source in sources:
        relative = source.relative_to(predictions)
        output = result_directory / "postprocessed" / mode / relative.parent / f"{source.stem}{suffix}{source.suffix}"
        entry: dict[str, Any] = {
            "source": source.relative_to(result_directory).as_posix(),
            "output": output.relative_to(result_directory).as_posix(),
            "model_index": None,
            "status": "running",
        }
        try:
            import re
            match = re.search(r"model_(\d+)", source.name)
            entry["model_index"] = int(match.group(1)) if match else None
            entry.update(process_structure(source, output, mode))
            report["summary"]["succeeded"] += 1
        except Exception as exc:  # report every model; fail the wrapper after preserving originals
            entry.update({"status": "failed", "error": str(exc)})
            report["summary"]["failed"] += 1
        report["models"].append(entry)
        _atomic_json(report_path, report)

    report["completed_at"] = _utc_now()
    report["status"] = "succeeded" if report["summary"]["failed"] == 0 else "failed"
    _atomic_json(report_path, report)
    if report["status"] != "succeeded":
        failures = "; ".join(item.get("error", "unknown error") for item in report["models"] if item["status"] == "failed")
        raise PostprocessError(f"Structure post-processing failed: {failures}")
    return report


__all__ = ["PostprocessError", "process_result_directory", "process_structure"]
