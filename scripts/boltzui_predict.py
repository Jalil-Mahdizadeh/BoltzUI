#!/usr/bin/env python3
"""Boltz CLI pass-through with optional BoltzUI structure post-processing."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from structure_postprocess import PostprocessError, process_result_directory


CUSTOM_FLAGS = {"--addh": "addh", "--addh-energy-min": "addh_energy_min"}
HELP_TEXT = """

BoltzUI post-processing options:
  --addh               Preserve original models and write neutral-pH hydrogenated copies.
  --addh-energy-min    Preserve original models and write neutral-pH, energy-minimized copies.
The two options are mutually exclusive and support standard protein, RNA, and DNA residues.
"""


def split_postprocess_flags(arguments: list[str]) -> tuple[list[str], str | None]:
    forwarded = []
    selected = []
    for argument in arguments:
        if argument in CUSTOM_FLAGS:
            selected.append(CUSTOM_FLAGS[argument])
        else:
            forwarded.append(argument)
    if len(set(selected)) > 1:
        raise PostprocessError("--addh and --addh-energy-min are mutually exclusive.")
    return forwarded, selected[0] if selected else None


def _option_value(arguments: list[str], flag: str, default: str) -> str:
    try:
        index = arguments.index(flag)
    except ValueError:
        return default
    if index + 1 >= len(arguments):
        raise PostprocessError(f"{flag} requires a value.")
    return arguments[index + 1]


def result_directory(arguments: list[str], cwd: Path) -> Path:
    if len(arguments) < 2 or arguments[0] != "predict":
        raise PostprocessError("Hydrogen post-processing is only valid with 'boltzui-predict predict DATA'.")
    data = Path(arguments[1])
    if not data.is_absolute():
        data = cwd / data
    output_root = Path(_option_value(arguments, "--out_dir", "boltz_results"))
    if not output_root.is_absolute():
        output_root = cwd / output_root
    return output_root / f"boltz_results_{data.stem}"


def main(arguments: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    try:
        forwarded, mode = split_postprocess_flags(arguments)
        if mode is not None:
            target = result_directory(forwarded, Path.cwd())
        completed = subprocess.run([os.environ.get("BOLTZ_EXECUTABLE", "boltz"), *forwarded], check=False)
        if any(argument in {"--help", "-h"} for argument in forwarded):
            print(HELP_TEXT)
        if completed.returncode != 0:
            return completed.returncode
        if mode is None:
            if len(forwarded) >= 2 and forwarded[0] == "predict":
                (result_directory(forwarded, Path.cwd()) / "boltzui_postprocess.json").unlink(missing_ok=True)
            return 0
        print(f"BoltzUI: starting {mode} post-processing in {target}", flush=True)
        report = process_result_directory(target, mode)
        print(
            f"BoltzUI: post-processed {report['summary']['succeeded']} model(s); "
            f"report: {target / 'boltzui_postprocess.json'}",
            flush=True,
        )
        return 0
    except (OSError, PostprocessError, ValueError) as exc:
        print(f"BoltzUI post-processing error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
