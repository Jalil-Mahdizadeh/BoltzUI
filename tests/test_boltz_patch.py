from pathlib import Path
from types import SimpleNamespace
import unittest

import torch
import yaml

from boltz.data.feature.featurizerv2 import process_contact_feature_constraints
from boltz.data.parse.schema import atom_contact_spec_to_ids
from boltz.data.parse.yaml import parse_yaml
from boltz.data.types import InferenceOptions
from boltz.main import load_canonicals


ROOT = Path(__file__).resolve().parents[1]


class BoltzPatchTests(unittest.TestCase):
    def test_example_parses_with_real_boltz_schema(self):
        target = parse_yaml(
            ROOT / "fixtures" / "atom_contact_example.yaml",
            load_canonicals(Path("/opt/boltz-cache/mols")),
            Path("/opt/boltz-cache/mols"),
            boltz2=True,
        )
        restraints = target.record.inference_options.atom_contact_constraints
        self.assertEqual(len(restraints), 1)
        self.assertEqual(restraints[0][2], 4.0)

    def test_exact_pair_and_threshold_propagation(self):
        data = SimpleNamespace(tokens=[], structure=SimpleNamespace(chains=[]))
        features = process_contact_feature_constraints(
            data,
            inference_pocket_constraints=[],
            inference_contact_constraints=[],
            inference_atom_contact_constraints=[((0, 0, 7), (1, 0, 11), 4.0, True)],
        )
        self.assertTrue(torch.equal(features["contact_pair_index"], torch.tensor([[7], [11]])))
        self.assertEqual(features["contact_pair_index"].shape[1], 1)
        self.assertTrue(torch.equal(features["contact_thresholds"], torch.tensor([4.0])))

    def test_endpoint_errors_identify_complete_endpoint(self):
        chain_to_idx = {"A": 0}
        atom_map = {("A", 0, "OG"): (0, 0, 7)}
        with self.assertRaisesRegex(ValueError, "Unable to resolve atom-contact endpoint Z:1:OG"):
            atom_contact_spec_to_ids(["Z", 1, "OG"], chain_to_idx, atom_map, "atom1")
        with self.assertRaisesRegex(ValueError, "Unable to resolve atom-contact endpoint A:2:OG"):
            atom_contact_spec_to_ids(["A", 2, "OG"], chain_to_idx, atom_map, "atom1")
        with self.assertRaisesRegex(ValueError, "Unable to resolve atom-contact endpoint A:1:XX"):
            atom_contact_spec_to_ids(["A", 1, "XX"], chain_to_idx, atom_map, "atom1")

    def test_inference_options_has_separate_atom_contact_field(self):
        self.assertIn("atom_contact_constraints", InferenceOptions.__dataclass_fields__)


if __name__ == "__main__":
    unittest.main()
