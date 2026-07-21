"""Dependency-free tests for the BoltzUI prediction wrapper."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from boltzui_predict import HELP_TEXT, PostprocessError, result_directory, split_postprocess_flags
from structure_postprocess import _apply_pdb_confidence


class BoltzUiPredictTests(unittest.TestCase):
    def test_custom_flag_is_removed_before_forwarding(self):
        forwarded, mode = split_postprocess_flags([
            "predict", "input.yaml", "--sampling_steps", "200", "--addh"
        ])
        self.assertEqual(mode, "addh")
        self.assertEqual(forwarded, ["predict", "input.yaml", "--sampling_steps", "200"])

    def test_minimization_flag_selects_combined_mode(self):
        forwarded, mode = split_postprocess_flags(["predict", "input.yaml", "--addh-energy-min"])
        self.assertEqual(mode, "addh_energy_min")
        self.assertEqual(forwarded, ["predict", "input.yaml"])

    def test_flags_are_mutually_exclusive(self):
        with self.assertRaisesRegex(PostprocessError, "mutually exclusive"):
            split_postprocess_flags(["predict", "input.yaml", "--addh", "--addh-energy-min"])

    def test_result_directory_matches_boltz_naming(self):
        target = result_directory(
            ["predict", "workspace/inputs/example.yaml", "--out_dir", "workspace/results"],
            Path("/work"),
        )
        self.assertEqual(target, Path("/work/workspace/results/boltz_results_example"))

    def test_help_documents_both_custom_flags(self):
        self.assertIn("--addh", HELP_TEXT)
        self.assertIn("--addh-energy-min", HELP_TEXT)

    def test_pdb_confidence_is_copied_to_heavy_atoms_and_new_hydrogens(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.pdb"
            output = Path(directory) / "output.pdb"
            source.write_text(
                "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 87.65           C  \n",
                encoding="utf-8",
            )
            output.write_text(
                "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C  \n"
                "ATOM      2  HA  ALA A   1       0.100   0.000   0.000  1.00  0.00           H  \n",
                encoding="utf-8",
            )
            self.assertTrue(_apply_pdb_confidence(source, output))
            values = [float(line[60:66]) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(values, [87.65, 87.65])


if __name__ == "__main__":
    unittest.main()
