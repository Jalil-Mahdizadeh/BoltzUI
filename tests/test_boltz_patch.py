from pathlib import Path
from types import SimpleNamespace
import hashlib
import inspect
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch
import yaml

from boltz.data import const
import boltz.data.module.inferencev2 as inferencev2_module
from boltz.data.feature.featurizerv2 import (
    apply_atom_contact_token_conditioning,
    process_contact_feature_constraints,
    process_token_features,
)
from boltz.data.module.inferencev2 import PredictionDataset
from boltz.data.parse.schema import atom_contact_spec_to_ids
from boltz.data.parse.yaml import parse_yaml
from boltz.data.types import InferenceOptions
from boltz.main import BoltzSteeringParams, load_canonicals
from boltz.model.modules.diffusionv2 import AtomDiffusion
from boltz.model.potentials.potentials import (
    ContactPotentital,
    InterfaceClashPotentital,
    InterfaceContactPotentital,
    get_potentials,
)


ROOT = Path(__file__).resolve().parents[1]


class BoltzPatchTests(unittest.TestCase):
    def test_prediction_dataset_propagates_interface_feature_failures(self):
        class FailingFeaturizer:
            def process(self, *args, **kwargs):
                raise ValueError("forced interface crop loss")

        record = SimpleNamespace(
            id="interface-error",
            inference_options=InferenceOptions(
                interface_contact_constraints=[
                    ([(0, 0)], [(1, 0)], 6.0, True)
                ]
            ),
        )
        dataset = object.__new__(PredictionDataset)
        dataset.manifest = SimpleNamespace(records=[record])
        dataset.target_dir = Path(".")
        dataset.msa_dir = Path(".")
        dataset.mol_dir = Path(".")
        dataset.constraints_dir = None
        dataset.template_dir = None
        dataset.extra_mols_dir = None
        dataset.affinity = False
        dataset.override_method = None
        dataset.canonicals = {}
        dataset.tokenizer = SimpleNamespace(
            tokenize=lambda _: SimpleNamespace(
                tokens=np.array(
                    [("ALA",)],
                    dtype=[("res_name", "U3")],
                )
            )
        )
        dataset.featurizer = FailingFeaturizer()
        input_data = SimpleNamespace(extra_mols={})
        with (
            patch.object(inferencev2_module, "load_input", return_value=input_data),
            patch.object(inferencev2_module, "load_molecules", return_value={}),
            self.assertRaisesRegex(ValueError, "forced interface crop loss"),
        ):
            dataset[0]

        source = inspect.getsource(PredictionDataset.__getitem__)
        self.assertIn(
            "if interface_contact_constraints:\n                raise",
            source,
        )
        self.assertIn("return self.__getitem__(0)", source)

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

    def test_parser_rejects_duplicate_and_reversed_interface_patches(self):
        source = yaml.safe_load(
            (ROOT / "fixtures" / "interface_contact_example.yaml").read_text()
        )
        first = source["constraints"][0]["interface_contact"]
        duplicates = [
            json.loads(json.dumps(first)),
            {
                "patch1": first["patch2"],
                "patch2": first["patch1"],
                "max_distance": 7.0,
                "force": True,
            },
        ]
        canonicals = load_canonicals(Path("/opt/boltz-cache/mols"))
        for index, duplicate in enumerate(duplicates):
            document = json.loads(json.dumps(source))
            document["constraints"].append({"interface_contact": duplicate})
            with tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / f"duplicate-interface-{index}.yaml"
                target.write_text(yaml.safe_dump(document))
                with self.assertRaisesRegex(
                    ValueError,
                    r"interface_contact 2 (duplicates|conflicts with) "
                    r"interface_contact 1",
                ):
                    parse_yaml(
                        target,
                        canonicals,
                        Path("/opt/boltz-cache/mols"),
                        boltz2=True,
                    )

    def test_parser_rejects_adjacent_only_single_chain_interface_patches(self):
        source = yaml.safe_load(
            (ROOT / "fixtures" / "interface_contact_single_chain_example.yaml").read_text()
        )
        interface = source["constraints"][0]["interface_contact"]
        interface["patch1"]["residues"] = [2]
        interface["patch2"]["residues"] = [3]
        canonicals = load_canonicals(Path("/opt/boltz-cache/mols"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "adjacent-interface.yaml"
            target.write_text(yaml.safe_dump(source))
            with self.assertRaisesRegex(
                ValueError,
                "every active residue must have an eligible opposite-patch residue",
            ):
                parse_yaml(
                    target,
                    canonicals,
                    Path("/opt/boltz-cache/mols"),
                    boltz2=True,
                )

    def test_parser_rejects_partially_ineligible_same_chain_patches(self):
        source = yaml.safe_load(
            (ROOT / "fixtures" / "interface_contact_single_chain_example.yaml").read_text()
        )
        interface = source["constraints"][0]["interface_contact"]
        interface["patch1"]["residues"] = [1, 5]
        interface["patch2"]["residues"] = [2]
        canonicals = load_canonicals(Path("/opt/boltz-cache/mols"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "partially-adjacent-interface.yaml"
            target.write_text(yaml.safe_dump(source))
            with self.assertRaisesRegex(ValueError, r"patch1: 1"):
                parse_yaml(
                    target,
                    canonicals,
                    Path("/opt/boltz-cache/mols"),
                    boltz2=True,
                )

    def test_parser_rejects_cyclic_chain_closing_interface_neighbors(self):
        source = yaml.safe_load(
            (ROOT / "fixtures" / "interface_contact_single_chain_example.yaml").read_text()
        )
        source["sequences"][0]["protein"]["cyclic"] = True
        interface = source["constraints"][0]["interface_contact"]
        interface["patch1"]["residues"] = [1]
        interface["patch2"]["residues"] = [6]
        canonicals = load_canonicals(Path("/opt/boltz-cache/mols"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "cyclic-neighbor-interface.yaml"
            target.write_text(yaml.safe_dump(source))
            with self.assertRaisesRegex(
                ValueError,
                "linear or cyclic sequence neighbors",
            ):
                parse_yaml(
                    target,
                    canonicals,
                    Path("/opt/boltz-cache/mols"),
                    boltz2=True,
                )

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

    @staticmethod
    def interface_features(
        pair_index,
        group_index,
        pair_weights,
        group_thresholds,
        group_weights,
        atom_to_token,
    ):
        pair_thresholds = group_thresholds.index_select(0, group_index)
        return {
            "interface_contact_pair_index": pair_index.unsqueeze(0),
            "interface_contact_union_index": group_index.unsqueeze(0),
            "interface_contact_negation_mask": torch.ones_like(
                group_index, dtype=torch.bool
            ).unsqueeze(0),
            "interface_contact_thresholds": pair_thresholds.unsqueeze(0),
            "interface_contact_pair_weights": pair_weights.unsqueeze(0),
            "interface_contact_group_thresholds": group_thresholds.unsqueeze(0),
            "interface_contact_group_weights": group_weights.unsqueeze(0),
            "atom_to_token": atom_to_token.unsqueeze(0),
            "atom_pad_mask": torch.ones(
                (1, atom_to_token.shape[0]), dtype=torch.bool
            ),
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

    def test_interface_hard_min_gradient_translates_and_caps_each_residue(self):
        potential = InterfaceContactPotentital(parameters={})
        features = self.interface_features(
            torch.tensor(
                [[0, 2], [2, 0]],
                dtype=torch.long,
            ),
            torch.tensor([0, 1], dtype=torch.long),
            torch.ones(2),
            torch.full((2,), 8.0),
            torch.full((2,), 0.5),
            torch.tensor([
                [1.0, 0.0],
                [1.0, 0.0],
                [0.0, 1.0],
                [0.0, 1.0],
            ]),
        )
        coords = torch.tensor(
            [[
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [10.0, 0.0, 0.0],
                [11.0, 0.0, 0.0],
            ]]
        )
        parameters = {"max_token_gradient": 0.5}
        self.assertAlmostEqual(float(potential.compute(coords, features, parameters)), 1.0)
        gradient = potential.compute_gradient(coords, features, parameters)
        self.assertTrue(torch.equal(gradient[:, 0], gradient[:, 1]))
        self.assertTrue(torch.equal(gradient[:, 2], gradient[:, 3]))
        token_norms = torch.linalg.vector_norm(gradient[:, [0, 2]], dim=-1)
        self.assertTrue(torch.all(token_norms <= 0.5))
        self.assertTrue(torch.all(token_norms > 0.0))
        self.assertLess(
            float(potential.compute(coords - 0.1 * gradient, features, parameters)),
            1.0,
        )

    def test_interface_hard_min_huber_loss_matches_literal_cutoff_and_is_finite(self):
        potential = InterfaceContactPotentital(parameters={})
        features = self.interface_features(
            torch.tensor([[0, 0], [1, 2]], dtype=torch.long),
            torch.zeros(2, dtype=torch.long),
            torch.ones(2),
            torch.tensor([5.0]),
            torch.tensor([1.0]),
            torch.eye(3),
        )
        parameters = {"max_token_gradient": 0.5}
        coords = torch.tensor([[
            [0.0, 0.0, 0.0],
            [6.0, 0.0, 0.0],
            [12.0, 0.0, 0.0],
        ]])
        self.assertAlmostEqual(
            float(potential.compute(coords, features, parameters)),
            0.25,
            places=5,
        )
        gradient = potential.compute_gradient(coords, features, parameters)
        self.assertTrue(torch.isfinite(gradient).all())

        overlapped = coords.clone()
        overlapped[:, 1:] = 0.0
        self.assertTrue(
            torch.isfinite(potential.compute(overlapped, features, parameters)).all()
        )
        self.assertTrue(
            torch.isfinite(
                potential.compute_gradient(overlapped, features, parameters)
            ).all()
        )
        distant = coords.clone()
        distant[:, 1:, 0] = torch.tensor([1e8, 2e8])
        self.assertTrue(
            torch.isfinite(potential.compute(distant, features, parameters)).all()
        )
        self.assertTrue(
            torch.isfinite(
                potential.compute_gradient(distant, features, parameters)
            ).all()
        )

    def test_interface_normalized_huber_steers_every_violated_active_residue(self):
        potential = InterfaceContactPotentital(parameters={})
        features = self.interface_features(
            torch.tensor([[0, 1], [2, 3]], dtype=torch.long),
            torch.tensor([0, 1], dtype=torch.long),
            torch.ones(2),
            torch.full((2,), 8.0),
            torch.full((2,), 0.25),
            torch.eye(4),
        )
        coords = torch.tensor([[
            [0.0, 0.0, 0.0],
            [0.0, 10.0, 0.0],
            [12.0, 0.0, 0.0],
            [0.0, 20.0, 0.0],
        ]])
        parameters = {"max_token_gradient": 0.5}

        self.assertAlmostEqual(
            float(potential.compute(coords, features, parameters)),
            1.0,
        )
        gradient = potential.compute_gradient(coords, features, parameters)
        self.assertGreater(
            float(torch.linalg.vector_norm(gradient[:, [0, 2]])),
            0.0,
        )
        self.assertGreater(
            float(torch.linalg.vector_norm(gradient[:, [1, 3]])),
            0.0,
        )
        self.assertLess(
            float(potential.compute(coords - 0.1 * gradient, features, parameters)),
            1.0,
        )

    def test_interface_hard_min_keeps_true_ambiguous_or_semantics(self):
        potential = InterfaceContactPotentital(parameters={})
        pair_count = 16
        features = self.interface_features(
            torch.stack((
                torch.zeros(pair_count, dtype=torch.long),
                torch.arange(1, pair_count + 1, dtype=torch.long),
            )),
            torch.zeros(pair_count, dtype=torch.long),
            torch.ones(pair_count),
            torch.tensor([8.0]),
            torch.tensor([1.0]),
            torch.eye(pair_count + 1),
        )
        coords = torch.zeros((1, pair_count + 1, 3))
        coords[:, 1, 0] = 8.0
        coords[:, 2:, 0] = torch.arange(100.0, 100.0 + pair_count - 1)
        parameters = {"max_token_gradient": 0.5}
        self.assertEqual(
            float(potential.compute(coords, features, parameters)),
            0.0,
        )
        self.assertTrue(
            torch.equal(
                potential.compute_gradient(coords, features, parameters),
                torch.zeros_like(coords),
            )
        )

    def test_interface_clash_potential_repels_whole_residues(self):
        potential = InterfaceClashPotentital(parameters={})
        features = {
            "interface_clash_pair_index": torch.tensor(
                [[[0], [2]]], dtype=torch.long
            ),
            "interface_clash_thresholds": torch.tensor([[2.5]]),
            "atom_to_token": torch.tensor([[
                [1.0, 0.0],
                [1.0, 0.0],
                [0.0, 1.0],
                [0.0, 1.0],
            ]]),
            "atom_pad_mask": torch.ones((1, 4), dtype=torch.bool),
        }
        parameters = {
            "clash_strength": 0.5,
            "max_token_gradient": 0.5,
        }
        coords = torch.tensor([[
            [0.0, 0.0, 0.0],
            [0.5, 0.0, 0.0],
            [1.5, 0.0, 0.0],
            [2.0, 0.0, 0.0],
        ]])
        self.assertAlmostEqual(
            float(potential.compute(coords, features, parameters)),
            0.5,
        )
        gradient = potential.compute_gradient(coords, features, parameters)
        self.assertTrue(torch.equal(gradient[:, 0], gradient[:, 1]))
        self.assertTrue(torch.equal(gradient[:, 2], gradient[:, 3]))
        self.assertLess(
            float(potential.compute(coords - 0.1 * gradient, features, parameters)),
            0.5,
        )
        overlapped = coords.clone()
        overlapped[:, 2] = overlapped[:, 0]
        self.assertTrue(
            torch.isfinite(
                potential.compute_gradient(overlapped, features, parameters)
            ).all()
        )

    def test_union_alternatives_do_not_enter_binary_token_conditioning(self):
        parameters = inspect.signature(process_token_features).parameters
        self.assertIn("inference_atom_contact_constraints", parameters)
        self.assertNotIn("inference_atom_contact_union_constraints", parameters)
        self.assertNotIn("inference_interface_contact_constraints", parameters)

    def test_native_token_pipeline_source_is_unchanged(self):
        self.assertEqual(
            hashlib.sha256(
                inspect.getsource(process_token_features).encode()
            ).hexdigest(),
            "88ad8c642be5d886c2d6f230770a125949198007dd9b3a58e30ba148893040c8",
        )
        self.assertEqual(
            hashlib.sha256(
                inspect.getsource(ContactPotentital).encode()
            ).hexdigest(),
            "24eab3cbea60b8de1ef9a3c10ad7e64b6c9bb9ca7aedcda21144c15c5cc6519c",
        )

    def test_native_token_contact_fixture_parses_unchanged(self):
        target = parse_yaml(
            ROOT / "fixtures" / "token_contact_example.yaml",
            load_canonicals(Path("/opt/boltz-cache/mols")),
            Path("/opt/boltz-cache/mols"),
            boltz2=True,
        )
        self.assertEqual(
            target.record.inference_options.contact_constraints,
            [((0, 0), (1, 0), 4.0, True)],
        )

    def test_interface_patches_create_reciprocal_per_residue_union_groups(self):
        tokens = np.array(
            [
                (const.chain_type_ids["PROTEIN"], 0, 0, 10, 2, 11),
                (const.chain_type_ids["PROTEIN"], 0, 2, 20, 2, 21),
                (const.chain_type_ids["PROTEIN"], 1, 0, 40, 2, 41),
                (const.chain_type_ids["PROTEIN"], 1, 1, 60, 2, 61),
            ],
            dtype=[
                ("mol_type", np.int64),
                ("asym_id", np.int64),
                ("res_idx", np.int64),
                ("atom_idx", np.int64),
                ("atom_num", np.int64),
                ("disto_idx", np.int64),
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
        self.assertEqual(
            features["interface_contact_pair_index"].shape,
            (2, 32),
        )
        self.assertTrue(
            torch.equal(
                torch.bincount(features["interface_contact_union_index"]),
                torch.full((4,), 8),
            )
        )
        self.assertTrue(
            torch.equal(
                features["interface_contact_thresholds"],
                torch.full((32,), 6.0),
            )
        )
        self.assertTrue(
            torch.equal(
                features["interface_contact_pair_weights"],
                torch.ones(32),
            )
        )
        self.assertTrue(
            torch.equal(
                features["interface_contact_group_weights"],
                torch.full((4,), 0.25),
            )
        )
        self.assertTrue(
            torch.equal(
                features["interface_contact_group_thresholds"],
                torch.full((4,), 6.0),
            )
        )
        self.assertEqual(features["interface_clash_pair_index"].shape, (2, 16))
        potential_features = {
            key: value.unsqueeze(0)
            for key, value in features.items()
            if key.startswith("interface_contact_")
        }
        atom_to_token = torch.zeros((8, 4))
        atom_to_token[0:2, 0] = 1.0
        atom_to_token[2:4, 1] = 1.0
        atom_to_token[4:6, 2] = 1.0
        atom_to_token[6:8, 3] = 1.0
        potential_features["atom_to_token"] = atom_to_token.unsqueeze(0)
        potential_features["atom_pad_mask"] = torch.ones(
            (1, 8), dtype=torch.bool
        )
        coords = torch.zeros((1, 8, 3))
        coords[:, 4:, 0] = 10.0
        self.assertAlmostEqual(
            float(
                InterfaceContactPotentital(parameters={}).compute(
                    coords,
                    potential_features,
                    {"max_token_gradient": 0.5},
                )
            ),
            3.0,
            places=5,
        )

    def test_multiple_interfaces_have_independent_direction_normalized_groups(self):
        tokens = np.array(
            [
                (const.chain_type_ids["PROTEIN"], 0, 0, 10, 1, 10),
                (const.chain_type_ids["PROTEIN"], 1, 0, 20, 1, 20),
                (const.chain_type_ids["PROTEIN"], 2, 0, 30, 1, 30),
            ],
            dtype=[
                ("mol_type", np.int64),
                ("asym_id", np.int64),
                ("res_idx", np.int64),
                ("atom_idx", np.int64),
                ("atom_num", np.int64),
                ("disto_idx", np.int64),
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
                ([(0, 0)], [(1, 0)], 6.0, True),
                ([(1, 0)], [(2, 0)], 10.0, True),
            ],
        )
        self.assertTrue(
            torch.equal(
                features["interface_contact_union_index"],
                torch.arange(4),
            )
        )
        self.assertTrue(
            torch.equal(
                features["interface_contact_group_thresholds"],
                torch.tensor([6.0, 6.0, 10.0, 10.0]),
            )
        )
        self.assertTrue(
            torch.equal(
                features["interface_contact_group_weights"],
                torch.full((4,), 0.5),
            )
        )
        self.assertAlmostEqual(
            float(features["interface_contact_group_weights"][:2].sum()),
            1.0,
        )
        self.assertAlmostEqual(
            float(features["interface_contact_group_weights"][2:].sum()),
            1.0,
        )
        self.assertEqual(features["interface_clash_pair_index"].shape, (2, 2))

        potential_features = {
            key: value.unsqueeze(0)
            for key, value in features.items()
            if key.startswith("interface_contact_")
        }
        potential_features["atom_to_token"] = torch.eye(3).unsqueeze(0)
        potential_features["atom_pad_mask"] = torch.ones(
            (1, 3), dtype=torch.bool
        )
        coords = torch.tensor([[
            [0.0, 0.0, 0.0],
            [10.0, 0.0, 0.0],
            [24.0, 0.0, 0.0],
        ]])
        self.assertAlmostEqual(
            float(
                InterfaceContactPotentital(parameters={}).compute(
                    coords,
                    potential_features,
                    {"max_token_gradient": 0.5},
                )
            ),
            6.0,
        )

    def test_interface_uses_compact_local_heavy_atom_indices(self):
        tokens = np.array(
            [
                (const.chain_type_ids["PROTEIN"], 0, 0, 100, 3, 101),
                (const.chain_type_ids["PROTEIN"], 1, 0, 200, 3, 202),
            ],
            dtype=[
                ("mol_type", np.int64),
                ("asym_id", np.int64),
                ("res_idx", np.int64),
                ("atom_idx", np.int64),
                ("atom_num", np.int64),
                ("disto_idx", np.int64),
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
                ([(0, 0)], [(1, 0)], 6.0, True)
            ],
        )
        self.assertEqual(
            features["interface_contact_pair_index"].shape,
            (2, 18),
        )
        self.assertEqual(
            int(features["interface_contact_pair_index"].min()),
            0,
        )
        self.assertEqual(
            int(features["interface_contact_pair_index"].max()),
            5,
        )

    def test_forced_interface_rejects_same_chain_covalent_neighbors(self):
        tokens = np.array(
            [
                (const.chain_type_ids["PROTEIN"], 0, 0, 0, 1, 0),
                (const.chain_type_ids["PROTEIN"], 0, 1, 1, 1, 1),
            ],
            dtype=[
                ("mol_type", np.int64),
                ("asym_id", np.int64),
                ("res_idx", np.int64),
                ("atom_idx", np.int64),
                ("atom_num", np.int64),
                ("disto_idx", np.int64),
            ],
        )
        data = SimpleNamespace(tokens=tokens, structure=SimpleNamespace(chains=[]))
        with self.assertRaisesRegex(ValueError, "no eligible opposite-patch"):
            process_contact_feature_constraints(
                data,
                inference_pocket_constraints=[],
                inference_contact_constraints=[],
                inference_atom_contact_constraints=[],
                inference_atom_contact_union_constraints=[],
                inference_interface_contact_constraints=[
                    ([(0, 0)], [(0, 1)], 6.0, True)
                ],
            )

    def test_interface_clash_pairs_exclude_cyclic_chain_closing_neighbors(self):
        tokens = np.array(
            [
                (const.chain_type_ids["PROTEIN"], 0, 0, 0, 1, 0),
                (const.chain_type_ids["PROTEIN"], 0, 3, 1, 1, 1),
            ],
            dtype=[
                ("mol_type", np.int64),
                ("asym_id", np.int64),
                ("res_idx", np.int64),
                ("atom_idx", np.int64),
                ("atom_num", np.int64),
                ("disto_idx", np.int64),
            ],
        )
        chain_dtype = [("asym_id", np.int64), ("cyclic_period", np.int64)]
        for cyclic_period in (4, 0):
            chains = np.array([(0, cyclic_period)], dtype=chain_dtype)
            data = SimpleNamespace(
                tokens=tokens,
                structure=SimpleNamespace(chains=chains, bonds=[]),
            )
            if cyclic_period:
                with self.assertRaisesRegex(
                    ValueError,
                    "no eligible opposite-patch",
                ):
                    process_contact_feature_constraints(
                        data,
                        inference_pocket_constraints=[],
                        inference_contact_constraints=[],
                        inference_atom_contact_constraints=[],
                        inference_atom_contact_union_constraints=[],
                        inference_interface_contact_constraints=[
                            ([(0, 0)], [(0, 3)], 6.0, True)
                        ],
                    )
            else:
                features = process_contact_feature_constraints(
                    data,
                    inference_pocket_constraints=[],
                    inference_contact_constraints=[],
                    inference_atom_contact_constraints=[],
                    inference_atom_contact_union_constraints=[],
                    inference_interface_contact_constraints=[
                        ([(0, 0)], [(0, 3)], 6.0, True)
                    ],
                )
                self.assertEqual(
                    features["interface_clash_pair_index"].shape,
                    (2, 1),
                )
                self.assertEqual(
                    features["interface_contact_pair_index"].shape,
                    (2, 2),
                )

    def test_forced_interface_rejects_no_eligible_pairs_after_bond_exclusion(self):
        tokens = np.array(
            [
                (const.chain_type_ids["PROTEIN"], 0, 0, 10, 1, 10),
                (const.chain_type_ids["PROTEIN"], 1, 0, 20, 1, 20),
            ],
            dtype=[
                ("mol_type", np.int64),
                ("asym_id", np.int64),
                ("res_idx", np.int64),
                ("atom_idx", np.int64),
                ("atom_num", np.int64),
                ("disto_idx", np.int64),
            ],
        )
        bonds = np.array(
            [(10, 20)],
            dtype=[("atom_1", np.int64), ("atom_2", np.int64)],
        )
        data = SimpleNamespace(
            tokens=tokens,
            structure=SimpleNamespace(chains=[], bonds=bonds),
        )
        with self.assertRaisesRegex(ValueError, "no eligible opposite-patch"):
            process_contact_feature_constraints(
                data,
                inference_pocket_constraints=[],
                inference_contact_constraints=[],
                inference_atom_contact_constraints=[],
                inference_atom_contact_union_constraints=[],
                inference_interface_contact_constraints=[
                    ([(0, 0)], [(1, 0)], 6.0, True)
                ],
            )

    def test_interface_features_do_not_change_native_contact_tensors(self):
        tokens = np.array(
            [
                (const.chain_type_ids["PROTEIN"], 0, 0, 0, 2, 0),
                (const.chain_type_ids["PROTEIN"], 1, 0, 2, 2, 2),
            ],
            dtype=[
                ("mol_type", np.int64),
                ("asym_id", np.int64),
                ("res_idx", np.int64),
                ("atom_idx", np.int64),
                ("atom_num", np.int64),
                ("disto_idx", np.int64),
            ],
        )
        data = SimpleNamespace(tokens=tokens, structure=SimpleNamespace(chains=[]))
        shared = {
            "inference_pocket_constraints": [],
            "inference_contact_constraints": [
                ((0, 0), (1, 0), 6.0, True),
            ],
            "inference_atom_contact_constraints": [
                ((0, 0, 0), (1, 0, 2), 4.0, True),
            ],
            "inference_atom_contact_union_constraints": [
                [
                    ((0, 0, 0), (1, 0, 2), 5.0, True),
                    ((0, 0, 1), (1, 0, 3), 6.0, True),
                ],
            ],
        }
        baseline = process_contact_feature_constraints(
            data,
            **shared,
            inference_interface_contact_constraints=[],
        )
        guided = process_contact_feature_constraints(
            data,
            **shared,
            inference_interface_contact_constraints=[
                ([(0, 0)], [(1, 0)], 6.0, True)
            ],
        )
        for key in (
            "contact_pair_index",
            "contact_union_index",
            "contact_negation_mask",
            "contact_thresholds",
        ):
            self.assertTrue(torch.equal(baseline[key], guided[key]), key)
        self.assertTrue(
            torch.equal(
                baseline["contact_pair_index"],
                torch.tensor([
                    [0, 0, 1, 1, 0, 0, 1],
                    [2, 3, 2, 3, 2, 2, 3],
                ]),
            )
        )
        self.assertTrue(
            torch.equal(
                baseline["contact_union_index"],
                torch.tensor([0, 0, 0, 0, 1, 2, 2]),
            )
        )
        self.assertTrue(
            torch.equal(
                baseline["contact_thresholds"],
                torch.tensor([6.0, 6.0, 6.0, 6.0, 4.0, 5.0, 6.0]),
            )
        )

    def test_forced_interface_fails_if_cropping_removes_active_residues(self):
        tokens = np.array(
            [
                (const.chain_type_ids["PROTEIN"], 0, 0, 0, 1, 0),
                (const.chain_type_ids["PROTEIN"], 1, 0, 1, 1, 1),
            ],
            dtype=[
                ("mol_type", np.int64),
                ("asym_id", np.int64),
                ("res_idx", np.int64),
                ("atom_idx", np.int64),
                ("atom_num", np.int64),
                ("disto_idx", np.int64),
            ],
        )
        data = SimpleNamespace(tokens=tokens, structure=SimpleNamespace(chains=[]))
        with self.assertRaisesRegex(ValueError, "lost forced active residue"):
            process_contact_feature_constraints(
                data,
                inference_pocket_constraints=[],
                inference_contact_constraints=[],
                inference_atom_contact_constraints=[],
                inference_atom_contact_union_constraints=[],
                inference_interface_contact_constraints=[
                    ([(0, 0), (0, 5)], [(1, 0), (1, 5)], 6.0, True),
                ],
            )

        features = process_contact_feature_constraints(
            data,
            inference_pocket_constraints=[],
            inference_contact_constraints=[],
            inference_atom_contact_constraints=[],
            inference_atom_contact_union_constraints=[],
            inference_interface_contact_constraints=[
                ([(2, 0)], [(1, 0)], 6.0, False),
            ],
        )
        self.assertEqual(features["interface_contact_pair_index"].shape, (2, 0))

    def test_interface_rejects_pathological_heavy_atom_pair_counts(self):
        tokens = np.array(
            [
                (const.chain_type_ids["PROTEIN"], 0, 0, 0, 355, 0),
                (const.chain_type_ids["PROTEIN"], 1, 0, 355, 355, 355),
            ],
            dtype=[
                ("mol_type", np.int64),
                ("asym_id", np.int64),
                ("res_idx", np.int64),
                ("atom_idx", np.int64),
                ("atom_num", np.int64),
                ("disto_idx", np.int64),
            ],
        )
        data = SimpleNamespace(tokens=tokens, structure=SimpleNamespace(chains=[]))
        with patch("torch.tensor", wraps=torch.tensor) as tensors, self.assertRaisesRegex(
            ValueError,
            "more than 250000 eligible heavy-atom pairs",
        ):
            process_contact_feature_constraints(
                data,
                inference_pocket_constraints=[],
                inference_contact_constraints=[],
                inference_atom_contact_constraints=[],
                inference_atom_contact_union_constraints=[],
                inference_interface_contact_constraints=[
                    ([(0, 0)], [(1, 0)], 6.0, True)
                ],
            )

        allocated_pairs = sum(
            len(call.args[0]) for call in tensors.call_args_list
            if call.args and isinstance(call.args[0], list) and call.args[0]
            and isinstance(call.args[0][0], tuple) and len(call.args[0][0]) == 2
        )
        self.assertLessEqual(allocated_pairs, 250_000)

    def test_force_off_interface_is_report_only(self):
        tokens = np.array(
            [
                (const.chain_type_ids["PROTEIN"], 0, 0, 0, 1, 0),
                (const.chain_type_ids["PROTEIN"], 0, 2, 1, 1, 1),
            ],
            dtype=[
                ("mol_type", np.int64),
                ("asym_id", np.int64),
                ("res_idx", np.int64),
                ("atom_idx", np.int64),
                ("atom_num", np.int64),
                ("disto_idx", np.int64),
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
        interface = next(
            potential
            for potential in potentials
            if isinstance(potential, InterfaceContactPotentital)
        )
        self.assertEqual(interface.parameters["resampling_weight"], 1.0)
        self.assertEqual(interface.parameters["huber_delta"], 2.0)
        self.assertEqual(interface.parameters["gradient_strength"], 4.0)
        clash = next(
            potential
            for potential in potentials
            if isinstance(potential, InterfaceClashPotentital)
        )
        self.assertEqual(clash.parameters["resampling_weight"], 0.0)

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
