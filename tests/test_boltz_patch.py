from pathlib import Path
from types import SimpleNamespace
import inspect
import json
import subprocess
import tempfile
import unittest

import numpy as np
import torch
import yaml

from boltz.data import const
from boltz.data.feature.featurizerv2 import (
    apply_atom_contact_token_conditioning,
    process_contact_feature_constraints,
    process_token_features,
)
from boltz.data.parse.schema import atom_contact_spec_to_ids
from boltz.data.parse.yaml import parse_yaml
from boltz.data.types import InferenceOptions
from boltz.main import BoltzSteeringParams, load_canonicals
from boltz.model.modules.diffusionv2 import AtomDiffusion
from boltz.model.potentials.potentials import (
    ContactPotentital,
    InterfaceContactPotentital,
    get_potentials,
)


ROOT = Path(__file__).resolve().parents[1]


class BoltzPatchTests(unittest.TestCase):
    def test_max_parallel_samples_is_a_true_chunk_size(self):
        source = inspect.getsource(AtomDiffusion.sample)
        self.assertIn("sample_ids.split(max_parallel_samples)", source)
        self.assertNotIn("multiplicity % max_parallel_samples", source)
        sample_ids = torch.arange(10)
        expected = {
            1: [1] * 10,
            2: [2] * 5,
            5: [5, 5],
            10: [10],
        }
        for limit, sizes in expected.items():
            self.assertEqual(
                [chunk.numel() for chunk in sample_ids.split(limit)], sizes
            )

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

    def test_union_example_parses_with_real_boltz_schema(self):
        target = parse_yaml(
            ROOT / "fixtures" / "atom_contact_union_example.yaml",
            load_canonicals(Path("/opt/boltz-cache/mols")),
            Path("/opt/boltz-cache/mols"),
            boltz2=True,
        )
        groups = target.record.inference_options.atom_contact_union_constraints
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 2)
        self.assertEqual([alternative[2] for alternative in groups[0]], [4.0, 4.0])

    def test_interface_examples_parse_for_multichain_and_single_chain(self):
        canonicals = load_canonicals(Path("/opt/boltz-cache/mols"))
        for fixture in (
            "interface_contact_example.yaml",
            "interface_contact_single_chain_example.yaml",
        ):
            target = parse_yaml(
                ROOT / "fixtures" / fixture,
                canonicals,
                Path("/opt/boltz-cache/mols"),
                boltz2=True,
            )
            interfaces = target.record.inference_options.interface_contact_constraints
            self.assertEqual(len(interfaces), 1)
            self.assertEqual(interfaces[0][2], 6.0)
            self.assertTrue(interfaces[0][3])

    def test_exact_pair_and_threshold_propagation(self):
        data = SimpleNamespace(tokens=[], structure=SimpleNamespace(chains=[]))
        features = process_contact_feature_constraints(
            data,
            inference_pocket_constraints=[],
            inference_contact_constraints=[],
            inference_atom_contact_constraints=[
                ((0, 0, 7), (1, 0, 11), 4.0, True),
                ((0, 0, 8), (1, 0, 12), 5.0, True),
            ],
        )
        self.assertTrue(
            torch.equal(
                features["contact_pair_index"], torch.tensor([[7, 8], [11, 12]])
            )
        )
        self.assertEqual(features["contact_pair_index"].shape[1], 2)
        self.assertTrue(
            torch.equal(features["contact_thresholds"], torch.tensor([4.0, 5.0]))
        )

    def test_union_alternatives_share_one_union_index_per_group(self):
        data = SimpleNamespace(tokens=[], structure=SimpleNamespace(chains=[]))
        features = process_contact_feature_constraints(
            data,
            inference_pocket_constraints=[],
            inference_contact_constraints=[],
            inference_atom_contact_constraints=[
                ((0, 0, 7), (1, 0, 11), 4.0, True),
            ],
            inference_atom_contact_union_constraints=[
                [
                    ((0, 0, 8), (1, 0, 12), 5.0, True),
                    ((0, 0, 9), (1, 0, 13), 6.0, True),
                ],
                [
                    ((0, 0, 10), (1, 0, 14), 7.0, True),
                    ((0, 0, 15), (1, 0, 16), 8.0, True),
                ],
            ],
        )
        self.assertTrue(
            torch.equal(
                features["contact_pair_index"],
                torch.tensor([[7, 8, 9, 10, 15], [11, 12, 13, 14, 16]]),
            )
        )
        self.assertTrue(
            torch.equal(
                features["contact_union_index"],
                torch.tensor([0, 1, 1, 2, 2]),
            )
        )
        self.assertTrue(
            torch.equal(
                features["contact_thresholds"],
                torch.tensor([4.0, 5.0, 6.0, 7.0, 8.0]),
            )
        )

    @staticmethod
    def contact_features(pair_index, union_index, thresholds, prefix="contact"):
        return {
            f"{prefix}_pair_index": pair_index.unsqueeze(0),
            f"{prefix}_union_index": union_index.unsqueeze(0),
            f"{prefix}_negation_mask": torch.ones_like(
                union_index, dtype=torch.bool
            ).unsqueeze(0),
            f"{prefix}_thresholds": thresholds.unsqueeze(0),
        }

    def test_exact_atom_energy_does_not_underflow_for_large_violations(self):
        potential = ContactPotentital(parameters={})
        features = self.contact_features(
            torch.tensor([[0], [1]], dtype=torch.long),
            torch.tensor([0], dtype=torch.long),
            torch.tensor([6.0]),
        )
        coords = torch.tensor(
            [[[0.0, 0.0, 0.0], [30.0, 0.0, 0.0]]]
        )
        self.assertAlmostEqual(float(potential.compute(coords, features, {})), 24.0)
        gradient = potential.compute_gradient(coords, features, {})
        self.assertGreater(float(torch.linalg.vector_norm(gradient)), 1.0)
        self.assertTrue(torch.isfinite(gradient).all())
        self.assertLess(
            float(potential.compute(coords - 0.1 * gradient, features, {})),
            24.0,
        )

    def test_satisfied_union_has_zero_energy_and_does_not_pull_other_alternatives(self):
        potential = ContactPotentital(parameters={})
        features = self.contact_features(
            torch.tensor([[0, 2], [1, 3]], dtype=torch.long),
            torch.tensor([0, 0], dtype=torch.long),
            torch.tensor([6.0, 6.0]),
        )
        coords = torch.tensor(
            [[
                [0.0, 0.0, 0.0],
                [5.0, 0.0, 0.0],
                [20.0, 0.0, 0.0],
                [40.0, 0.0, 0.0],
            ]]
        )
        self.assertEqual(float(potential.compute(coords, features, {})), 0.0)
        self.assertTrue(
            torch.equal(
                potential.compute_gradient(coords, features, {}),
                torch.zeros_like(coords),
            )
        )

    def test_violated_union_uses_the_closest_alternative_without_underflow(self):
        potential = ContactPotentital(parameters={})
        features = self.contact_features(
            torch.tensor([[0, 2], [1, 3]], dtype=torch.long),
            torch.tensor([0, 0], dtype=torch.long),
            torch.tensor([6.0, 6.0]),
        )
        coords = torch.tensor(
            [[
                [0.0, 0.0, 0.0],
                [30.0, 0.0, 0.0],
                [100.0, 0.0, 0.0],
                [140.0, 0.0, 0.0],
            ]]
        )
        self.assertAlmostEqual(float(potential.compute(coords, features, {})), 24.0)
        gradient = potential.compute_gradient(coords, features, {})
        self.assertGreater(float(torch.linalg.vector_norm(gradient[:, :2])), 1.0)
        self.assertEqual(float(torch.linalg.vector_norm(gradient[:, 2:])), 0.0)

    def test_interface_gradient_translates_and_caps_each_residue(self):
        potential = InterfaceContactPotentital(parameters={})
        features = self.contact_features(
            torch.tensor(
                [[0, 0, 1, 1], [2, 3, 2, 3]],
                dtype=torch.long,
            ),
            torch.zeros(4, dtype=torch.long),
            torch.full((4,), 6.0),
            prefix="interface_contact",
        )
        features["atom_to_token"] = torch.tensor(
            [[
                [1.0, 0.0],
                [1.0, 0.0],
                [0.0, 1.0],
                [0.0, 1.0],
            ]]
        )
        features["atom_pad_mask"] = torch.ones((1, 4), dtype=torch.bool)
        coords = torch.tensor(
            [[
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [10.0, 0.0, 0.0],
                [11.0, 0.0, 0.0],
            ]]
        )
        self.assertAlmostEqual(float(potential.compute(coords, features, {})), 3.0)
        gradient = potential.compute_gradient(coords, features, {})
        self.assertTrue(torch.equal(gradient[:, 0], gradient[:, 1]))
        self.assertTrue(torch.equal(gradient[:, 2], gradient[:, 3]))
        token_norms = torch.linalg.vector_norm(gradient[:, [0, 2]], dim=-1)
        self.assertTrue(torch.all(token_norms <= 1.0))
        self.assertTrue(torch.all(token_norms > 0.0))
        self.assertLess(
            float(potential.compute(coords - 0.1 * gradient, features, {})),
            3.0,
        )

    def test_union_alternatives_do_not_enter_binary_token_conditioning(self):
        parameters = inspect.signature(process_token_features).parameters
        self.assertIn("inference_atom_contact_constraints", parameters)
        self.assertNotIn("inference_atom_contact_union_constraints", parameters)
        self.assertNotIn("inference_interface_contact_constraints", parameters)

    def test_interface_patches_create_reciprocal_per_residue_union_groups(self):
        tokens = np.array(
            [
                (const.chain_type_ids["PROTEIN"], 0, 0, 0, 1),
                (const.chain_type_ids["PROTEIN"], 0, 2, 1, 1),
                (const.chain_type_ids["PROTEIN"], 1, 0, 2, 1),
                (const.chain_type_ids["PROTEIN"], 1, 1, 3, 1),
            ],
            dtype=[
                ("mol_type", np.int64),
                ("asym_id", np.int64),
                ("res_idx", np.int64),
                ("atom_idx", np.int64),
                ("atom_num", np.int64),
            ],
        )
        data = SimpleNamespace(tokens=tokens, structure=SimpleNamespace(chains=[]))
        features = process_contact_feature_constraints(
            data,
            inference_pocket_constraints=[],
            inference_contact_constraints=[],
            inference_atom_contact_constraints=[],
            inference_atom_contact_union_constraints=[],
            inference_interface_contact_constraints=[
                ([(0, 0), (0, 2)], [(1, 0), (1, 1)], 6.0, True)
            ],
        )
        self.assertEqual(features["contact_pair_index"].shape, (2, 0))
        self.assertTrue(
            torch.equal(
                features["interface_contact_pair_index"],
                torch.tensor(
                    [[0, 0, 1, 1, 2, 2, 3, 3], [2, 3, 2, 3, 0, 1, 0, 1]]
                ),
            )
        )
        self.assertTrue(
            torch.equal(
                features["interface_contact_union_index"],
                torch.tensor([0, 0, 1, 1, 2, 2, 3, 3]),
            )
        )
        self.assertTrue(
            torch.equal(
                features["interface_contact_thresholds"],
                torch.full((8,), 6.0),
            )
        )

    def test_force_off_interface_is_report_only(self):
        tokens = np.array(
            [
                (const.chain_type_ids["PROTEIN"], 0, 0, 0, 1),
                (const.chain_type_ids["PROTEIN"], 0, 2, 1, 1),
            ],
            dtype=[
                ("mol_type", np.int64),
                ("asym_id", np.int64),
                ("res_idx", np.int64),
                ("atom_idx", np.int64),
                ("atom_num", np.int64),
            ],
        )
        data = SimpleNamespace(tokens=tokens, structure=SimpleNamespace(chains=[]))
        features = process_contact_feature_constraints(
            data,
            inference_pocket_constraints=[],
            inference_contact_constraints=[],
            inference_atom_contact_constraints=[],
            inference_interface_contact_constraints=[
                ([(0, 0)], [(0, 2)], 6.0, False)
            ],
        )
        self.assertEqual(features["interface_contact_pair_index"].shape, (2, 0))

    def test_endpoint_errors_identify_complete_endpoint(self):
        chain_to_idx = {"A": 0}
        atom_map = {("A", 0, "OG"): (0, 0, 7)}
        with self.assertRaisesRegex(ValueError, "Unable to resolve atom-contact endpoint Z:1:OG"):
            atom_contact_spec_to_ids(["Z", 1, "OG"], chain_to_idx, atom_map, "atom1")
        with self.assertRaisesRegex(ValueError, "Unable to resolve atom-contact endpoint A:2:OG"):
            atom_contact_spec_to_ids(["A", 2, "OG"], chain_to_idx, atom_map, "atom1")
        with self.assertRaisesRegex(ValueError, "Unable to resolve atom-contact endpoint A:1:XX"):
            atom_contact_spec_to_ids(["A", 1, "XX"], chain_to_idx, atom_map, "atom1")

    def test_parser_rejects_endpoints_resolving_to_same_global_atom(self):
        document = yaml.safe_load(
            (ROOT / "fixtures" / "atom_contact_example.yaml").read_text()
        )
        document["constraints"][0]["atom_contact"]["atom2"] = ["A", 1, "OG"]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "identical.yaml"
            target.write_text(yaml.safe_dump(document))
            with self.assertRaisesRegex(ValueError, "same exact atom.*global atom index"):
                parse_yaml(
                    target,
                    load_canonicals(Path("/opt/boltz-cache/mols")),
                    Path("/opt/boltz-cache/mols"),
                    boltz2=True,
                )

    def test_parser_rejects_duplicate_reversed_exact_atom_pairs(self):
        document = yaml.safe_load(
            (ROOT / "fixtures" / "atom_contact_example.yaml").read_text()
        )
        first = document["constraints"][0]["atom_contact"]
        document["constraints"].append({
            "atom_contact": {
                "atom1": first["atom2"],
                "atom2": first["atom1"],
                "max_distance": first["max_distance"],
                "force": True,
            }
        })
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "duplicate-exact.yaml"
            target.write_text(yaml.safe_dump(document))
            with self.assertRaisesRegex(ValueError, "duplicate exact atom pair"):
                parse_yaml(
                    target,
                    load_canonicals(Path("/opt/boltz-cache/mols")),
                    Path("/opt/boltz-cache/mols"),
                    boltz2=True,
                )

    def test_parser_rejects_duplicate_reversed_union_alternatives(self):
        document = yaml.safe_load(
            (ROOT / "fixtures" / "atom_contact_union_example.yaml").read_text()
        )
        first = document["constraints"][0]["atom_contact_union"]["alternatives"][0]
        document["constraints"][0]["atom_contact_union"]["alternatives"][1] = {
            "atom1": first["atom2"],
            "atom2": first["atom1"],
            "max_distance": first["max_distance"],
        }
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "duplicate-union.yaml"
            target.write_text(yaml.safe_dump(document))
            with self.assertRaisesRegex(ValueError, "duplicates another alternative"):
                parse_yaml(
                    target,
                    load_canonicals(Path("/opt/boltz-cache/mols")),
                    Path("/opt/boltz-cache/mols"),
                    boltz2=True,
                )

    def test_parser_rejects_invalid_union_bound_with_group_and_alternative_label(self):
        document = yaml.safe_load(
            (ROOT / "fixtures" / "atom_contact_union_example.yaml").read_text()
        )
        document["constraints"][0]["atom_contact_union"]["alternatives"][1][
            "max_distance"
        ] = 20.000001
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "invalid-union-bound.yaml"
            target.write_text(yaml.safe_dump(document))
            with self.assertRaisesRegex(
                ValueError,
                r"atom_contact_union 1 alternative 2 max_distance.*20\.0",
            ):
                parse_yaml(
                    target,
                    load_canonicals(Path("/opt/boltz-cache/mols")),
                    Path("/opt/boltz-cache/mols"),
                    boltz2=True,
                )

    def test_token_pair_threshold_is_minimum_and_order_independent(self):
        tokens = np.array(
            [(7, 2), (11, 2)],
            dtype=[("atom_idx", np.int64), ("atom_num", np.int64)],
        )
        restraints = [
            ((0, 0, 7), (1, 0, 11), 6.0, True),
            ((0, 0, 8), (1, 0, 12), 4.0, True),
        ]
        outputs = []
        for ordered in (restraints, list(reversed(restraints))):
            conditioning = np.zeros((2, 2), dtype=np.int64)
            thresholds = np.zeros((2, 2), dtype=np.float32)
            apply_atom_contact_token_conditioning(
                conditioning, thresholds, tokens, ordered
            )
            outputs.append(thresholds.copy())
        self.assertTrue(np.array_equal(outputs[0], outputs[1]))
        self.assertEqual(outputs[0][0, 1], 4.0)
        self.assertEqual(outputs[0][1, 0], 4.0)

    def test_same_token_exact_atom_pair_does_not_condition_the_diagonal(self):
        tokens = np.array(
            [(7, 2)],
            dtype=[("atom_idx", np.int64), ("atom_num", np.int64)],
        )
        conditioning = np.zeros((1, 1), dtype=np.int64)
        thresholds = np.zeros((1, 1), dtype=np.float32)
        apply_atom_contact_token_conditioning(
            conditioning,
            thresholds,
            tokens,
            [((0, 0, 7), (0, 0, 8), 4.0, True)],
        )
        self.assertEqual(conditioning[0, 0], 0)
        self.assertEqual(thresholds[0, 0], 0.0)

    def test_contact_guidance_remains_on_without_optional_physical_potentials(self):
        steering = BoltzSteeringParams()
        self.assertTrue(steering.contact_guidance_update)
        self.assertFalse(steering.fk_steering)
        self.assertFalse(steering.physical_guidance_update)
        potentials = get_potentials(
            {
                "fk_steering": False,
                "physical_guidance_update": False,
                "contact_guidance_update": True,
            },
            boltz2=True,
        )
        self.assertTrue(
            any(
                isinstance(potential, InterfaceContactPotentital)
                for potential in potentials
            )
        )

    def test_method_choices_match_boltz_constants_without_future_slots(self):
        script = (
            "const { METHOD_CHOICES } = require('./lib/prediction-config'); "
            "process.stdout.write(JSON.stringify(METHOD_CHOICES));"
        )
        configured = json.loads(
            subprocess.check_output(["node", "-e", script], cwd=ROOT, text=True)
        )
        expected = [
            name for name in const.method_types_ids if not name.startswith("future")
        ]
        self.assertEqual(configured, expected)

    def test_inference_options_has_separate_atom_contact_field(self):
        self.assertIn("atom_contact_constraints", InferenceOptions.__dataclass_fields__)
        self.assertIn(
            "atom_contact_union_constraints",
            InferenceOptions.__dataclass_fields__,
        )
        self.assertIn(
            "interface_contact_constraints",
            InferenceOptions.__dataclass_fields__,
        )


if __name__ == "__main__":
    unittest.main()
