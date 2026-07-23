#!/usr/bin/env python3
"""Convert an official PDBx/mmCIF coordinate ensemble to legacy PDB syntax."""

from __future__ import print_function

import argparse
import os

import gemmi


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_mmcif")
    parser.add_argument("output_pdb")
    args = parser.parse_args()
    structure = gemmi.read_structure(args.input_mmcif)
    if len(structure) < 1:
        raise SystemExit("No coordinate models found in {}".format(args.input_mmcif))
    temporary = args.output_pdb + ".tmp"
    structure.write_pdb(temporary)
    if not os.path.isfile(temporary) or os.path.getsize(temporary) == 0:
        raise SystemExit("Conversion produced no coordinates")
    os.rename(temporary, args.output_pdb)
    print("{} models written to {}".format(len(structure), args.output_pdb))


if __name__ == "__main__":
    main()
