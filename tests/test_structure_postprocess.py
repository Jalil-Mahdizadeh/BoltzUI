"""Small molecular integration tests executed inside the BoltzUI image."""

import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from structure_postprocess import process_result_directory


class StructurePostprocessTests(unittest.TestCase):
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "structures" / "standard_dipeptide.pdb"

    def _result(self, directory: str) -> tuple[Path, str]:
        source = Path(directory) / "predictions" / "case" / "case_model_0.pdb"
        source.parent.mkdir(parents=True)
        shutil.copy2(self.fixture, source)
        return source, hashlib.sha256(source.read_bytes()).hexdigest()

    def test_addh_preserves_original_and_confidence(self):
        with tempfile.TemporaryDirectory() as directory:
            source, original_hash = self._result(directory)
            report = process_result_directory(directory, "addh")
            model = report["models"][0]
            self.assertEqual(report["status"], "succeeded")
            self.assertGreater(model["hydrogens_added"], 0)
            self.assertTrue(model["pdb_confidence_b_factors_preserved"])
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)
            self.assertTrue((Path(directory) / model["output"]).is_file())

    def test_energy_minimization_lowers_energy(self):
        with tempfile.TemporaryDirectory() as directory:
            self._result(directory)
            report = process_result_directory(directory, "addh_energy_min")
            energy = report["models"][0]["potential_energy"]
            self.assertLess(energy["final_kj_mol"], energy["initial_kj_mol"])


if __name__ == "__main__":
    unittest.main()
