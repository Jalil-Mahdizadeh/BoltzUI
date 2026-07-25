"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const {
  measureStructure,
  measureInterfaceContact,
  measureTokenContact,
  measureUnionGroup,
  parseMmcif,
  parsePdb,
  summarizeModelAudit,
  writeRestraintReport
} = require("../lib/restraint-report");

const structures = path.join(__dirname, "..", "fixtures", "structures");
const restraint = {
  chain1: "A", residue1: 1, atom1: "OG",
  chain2: "B", residue2: 1, atom2: "N",
  max_distance: 4, force: true
};

test("PDB parsing supports post-prediction distance measurement", () => {
  const atoms = parsePdb(fs.readFileSync(path.join(structures, "atom_contact_model_0.pdb"), "utf8"));
  const measured = measureStructure(restraint, atoms, "model_0");
  assert.equal(measured.observed_distance, 3);
  assert.equal(measured.excess_distance, 0);
  assert.equal(measured.satisfied, true);
});

test("mmCIF parsing supports post-prediction distance measurement", () => {
  const atoms = parseMmcif(fs.readFileSync(path.join(structures, "atom_contact_model_0.cif"), "utf8"));
  const measured = measureStructure(restraint, atoms, "model_0");
  assert.equal(measured.observed_distance, 3);
  assert.equal(measured.satisfied, true);
});

test("missing endpoint is reported as unresolved", () => {
  const atoms = parsePdb(fs.readFileSync(path.join(structures, "atom_contact_model_0.pdb"), "utf8"));
  const measured = measureStructure({ ...restraint, atom1: "MISSING" }, atoms, "model_0");
  assert.equal(measured.status, "unresolved");
  assert.equal(measured.satisfied, null);
  assert.match(measured.unresolved_reason, /A:1:MISSING/);
});

test("token contacts measure the closest atom pair between selected tokens", () => {
  const atoms = parsePdb(fs.readFileSync(path.join(structures, "atom_contact_model_0.pdb"), "utf8"));
  const measured = measureTokenContact({
    chain1: "A", token1: 1,
    chain2: "B", token2: 1,
    max_distance: 4, force: true
  }, atoms, "model_0");
  assert.equal(measured.observed_distance, 3);
  assert.equal(measured.satisfied, true);
  assert.equal(measured.closest_atom1, "A:1:OG");
  assert.equal(measured.closest_atom2, "B:1:N");
});

test("mmCIF token contacts resolve both endpoints in one identifier namespace", () => {
  const atoms = parseMmcif(fs.readFileSync(path.join(structures, "atom_contact_model_0.cif"), "utf8"));
  const measured = measureTokenContact({
    chain1: "A", token1: 1,
    chain2: "B", token2: 1,
    max_distance: 2, force: false
  }, atoms, "model_0");
  assert.equal(measured.observed_distance, 3);
  assert.equal(measured.status, "violated");
  assert.equal(measured.excess_distance, 1);
});

test("token-only runs write the generic contact restraint report", async () => {
  const resultDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "boltzui-token-report-"));
  const predictionDirectory = path.join(resultDirectory, "predictions", "case");
  fs.mkdirSync(predictionDirectory, { recursive: true });
  fs.copyFileSync(
    path.join(structures, "atom_contact_model_0.pdb"),
    path.join(predictionDirectory, "case_model_0.pdb")
  );
  const { report, reportPath } = await writeRestraintReport(resultDirectory, [], [], [{
    chain1: "A", token1: 1,
    chain2: "B", token2: 1,
    max_distance: 4, force: true
  }]);
  assert.equal(path.basename(reportPath), "contact_restraints.json");
  assert.equal(report.schema_version, 8);
  assert.equal(report.token_contacts[0].models[0].satisfied, true);
  assert.equal(report.model_summaries[0].token.satisfied, 1);
});

test("union report is satisfied when any one alternative is satisfied", () => {
  const atoms = parsePdb(fs.readFileSync(path.join(structures, "atom_contact_model_0.pdb"), "utf8"));
  const union = measureUnionGroup({
    alternatives: [
      { ...restraint, alternative_index: 1 },
      {
        chain1: "A", residue1: 1, atom1: "N",
        chain2: "B", residue2: 1, atom2: "N",
        max_distance: 4, alternative_index: 2
      }
    ]
  }, atoms, "model_0");
  assert.equal(union.measurements[0].satisfied, true);
  assert.equal(union.measurements[1].satisfied, false);
  assert.equal(union.summary.status, "satisfied");
  assert.equal(union.summary.satisfied, true);
  assert.deepEqual(union.summary.satisfying_alternatives, [1]);
});

test("interface audit applies reciprocal ambiguity and ignores added hydrogens", () => {
  const pdb = `${fs.readFileSync(path.join(structures, "atom_contact_model_0.pdb"), "utf8")}
ATOM      6  H   SER A   1       1.000   0.000   0.000  1.00 80.00           H
ATOM      7  H   GLY B   1       1.100   0.000   0.000  1.00 80.00           H
END
`;
  const measured = measureInterfaceContact({
    patch1: { chain: "A", residues: [1] },
    patch2: { chain: "B", residues: [1] },
    max_distance: 4,
    force: true
  }, parsePdb(pdb), "model_0");
  assert.equal(measured.satisfied, true);
  assert.equal(measured.patch_contact_satisfied, true);
  assert.equal(measured.all_active_residues_satisfied, true);
  assert.equal(measured.residue_restraints.length, 2);
  assert.equal(measured.residue_restraints[0].observed_distance, 3);
  assert.equal(measured.residue_restraints[1].observed_distance, 3);
  assert.equal(measured.residue_total, 2);
  assert.equal(measured.residue_satisfied, 2);
  assert.equal(measured.residue_satisfaction_fraction, 1);
  assert.equal(measured.patch1_residue_satisfaction_fraction, 1);
  assert.equal(measured.patch2_residue_satisfaction_fraction, 1);
  assert.equal(measured.balanced_residue_satisfaction_fraction, 1);
  assert.equal(measured.minimum_observed_distance, 3);
  assert.equal(measured.sub_2A_cross_patch_atom_pairs, 0);
  assert.equal(measured.has_sub_2A_cross_patch_overlap, false);
});

test("interface patch contact and strict active-residue coverage are separate", () => {
  const pdb = `ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 80.00           C
ATOM      2  CA  ALA A   3      20.000   0.000   0.000  1.00 80.00           C
ATOM      3  CA  GLY B   1       3.000   0.000   0.000  1.00 80.00           C
END
`;
  const measured = measureInterfaceContact({
    patch1: { chain: "A", residues: [1, 3] },
    patch2: { chain: "B", residues: [1] },
    max_distance: 4,
    force: true
  }, parsePdb(pdb), "model_0");
  assert.equal(measured.satisfied, true);
  assert.equal(measured.patch_contact_satisfied, true);
  assert.equal(measured.all_active_residues_satisfied, false);
  assert.equal(measured.status, "partial");
  assert.equal(measured.residue_satisfied, 2);
  assert.equal(measured.residue_total, 3);
  assert.equal(measured.patch1_residue_satisfaction_fraction, 0.5);
  assert.equal(measured.patch2_residue_satisfaction_fraction, 1);
  assert.equal(measured.balanced_residue_satisfaction_fraction, 0.75);
});

test("interface audit excludes immediate same-chain neighbors", () => {
  const pdb = `ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 80.00           C
ATOM      2  CA  GLY A   2       1.500   0.000   0.000  1.00 80.00           C
END
`;
  const measured = measureInterfaceContact({
    patch1: { chain: "A", residues: [1] },
    patch2: { chain: "A", residues: [2] },
    max_distance: 4,
    force: true
  }, parsePdb(pdb), "model_0");
  assert.equal(measured.satisfied, null);
  assert.equal(measured.status, "unresolved");
  assert.match(measured.unresolved_reason, /linear or cyclic sequence neighbors/);
});

test("interface audit excludes cyclic chain-closing neighbors", () => {
  const pdb = `ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 80.00           C
ATOM      2  CA  GLY A   6       1.500   0.000   0.000  1.00 80.00           C
END
`;
  const measured = measureInterfaceContact({
    patch1: { chain: "A", residues: [1] },
    patch2: { chain: "A", residues: [6] },
    cyclic_periods: { A: 6 },
    max_distance: 4,
    force: false
  }, parsePdb(pdb), "model_0");
  assert.equal(measured.satisfied, null);
  assert.equal(measured.status, "unresolved");
  assert.match(measured.unresolved_reason, /linear or cyclic sequence neighbors/);
});

test("interface audit reports severe cross-patch heavy-atom overlap", () => {
  const pdb = fs.readFileSync(
    path.join(structures, "atom_contact_model_0.pdb"),
    "utf8"
  ).replace(
    "ATOM      4  N   GLY B   1       3.000",
    "ATOM      4  N   GLY B   1       1.500"
  );
  const measured = measureInterfaceContact({
    patch1: { chain: "A", residues: [1] },
    patch2: { chain: "B", residues: [1] },
    max_distance: 4,
    force: true
  }, parsePdb(pdb), "model_0");
  assert.equal(measured.minimum_observed_distance, 1.5);
  assert.equal(measured.sub_2A_cross_patch_atom_pairs, 1);
  assert.equal(measured.has_sub_2A_cross_patch_overlap, true);
});

test("partially unresolved union reports indeterminate instead of a false violation", () => {
  const atoms = parsePdb(fs.readFileSync(path.join(structures, "atom_contact_model_0.pdb"), "utf8"));
  const union = measureUnionGroup({
    alternatives: [
      { ...restraint, max_distance: 2, alternative_index: 1 },
      { ...restraint, atom1: "MISSING", alternative_index: 2 }
    ]
  }, atoms, "model_0");
  assert.equal(union.summary.status, "indeterminate");
  assert.equal(union.summary.satisfied, null);
  assert.deepEqual(union.summary.unresolved_alternatives, [2]);
});

test("large restraint reports expose per-model exact and union aggregates", () => {
  const summary = summarizeModelAudit("model_0", [
    {
      models: [
        { model: "model_0", status: "satisfied", satisfied: true, excess_distance: 0 }
      ]
    },
    {
      models: [
        { model: "model_0", status: "violated", satisfied: false, excess_distance: 1.25 }
      ]
    },
    {
      models: [
        { model: "model_0", status: "unresolved", satisfied: null, excess_distance: null }
      ]
    }
  ], [
    {
      models: [
        { model: "model_0", status: "satisfied", satisfied: true, minimum_excess_distance: 0 }
      ]
    },
    {
      models: [
        { model: "model_0", status: "violated", satisfied: false, minimum_excess_distance: 0.75 }
      ]
    },
    {
      models: [
        { model: "model_0", status: "indeterminate", satisfied: null, minimum_excess_distance: 0.5 }
      ]
    }
  ]);

  assert.deepEqual(summary.exact, {
    total: 3,
    resolved: 2,
    satisfied: 1,
    violated: 1,
    unresolved: 1,
    satisfaction_fraction_of_resolved: 0.5,
    mean_excess_distance: 0.625,
    mean_violation_excess_distance: 1.25,
    maximum_excess_distance: 1.25
  });
  assert.deepEqual(summary.token, {
    total: 0,
    resolved: 0,
    satisfied: 0,
    violated: 0,
    unresolved: 0,
    satisfaction_fraction_of_resolved: null,
    mean_excess_distance: null,
    mean_violation_excess_distance: null,
    maximum_excess_distance: null
  });
  assert.deepEqual(summary.interface, {
    total: 0,
    resolved: 0,
    satisfied: 0,
    violated: 0,
    unresolved: 0,
    satisfaction_fraction_of_resolved: null,
    residue_total: 0,
    residue_satisfied: 0,
    residue_satisfaction_fraction: null,
    all_active_residues_satisfied: 0,
    all_active_residues_satisfied_count: 0,
    minimum_observed_distance: null,
    sub_2A_cross_patch_atom_pairs: 0,
    patch1_residue_total: 0,
    patch1_residue_satisfied: 0,
    patch1_residue_satisfaction_fraction: null,
    patch2_residue_total: 0,
    patch2_residue_satisfied: 0,
    patch2_residue_satisfaction_fraction: null,
    balanced_residue_satisfaction_fraction: null,
    mean_maximum_excess_distance: null,
    maximum_excess_distance: null
  });
  assert.deepEqual(summary.union, {
    total: 3,
    conclusive: 2,
    satisfied: 1,
    violated: 1,
    indeterminate: 1,
    unresolved: 0,
    satisfaction_fraction_of_conclusive: 0.5,
    mean_minimum_excess_distance: 0.375,
    mean_violation_excess_distance: 0.75,
    maximum_minimum_excess_distance: 0.75
  });
});

test("model summaries aggregate interface coverage and overlap warnings", () => {
  const summary = summarizeModelAudit("model_0", [], [], [], [
    {
      models: [{
        model: "model_0",
        status: "violated",
        satisfied: false,
        all_active_residues_satisfied: false,
        maximum_excess_distance: 3,
        minimum_observed_distance: 1.5,
        residue_total: 6,
        residue_satisfied: 4,
        patch1_residue_total: 3,
        patch1_residue_satisfied: 2,
        patch2_residue_total: 3,
        patch2_residue_satisfied: 2,
        balanced_residue_satisfaction_fraction: 2 / 3,
        sub_2A_cross_patch_atom_pairs: 2
      }]
    },
    {
      models: [{
        model: "model_0",
        status: "satisfied",
        satisfied: true,
        all_active_residues_satisfied: true,
        maximum_excess_distance: 0,
        minimum_observed_distance: 3,
        residue_total: 4,
        residue_satisfied: 4,
        patch1_residue_total: 2,
        patch1_residue_satisfied: 2,
        patch2_residue_total: 2,
        patch2_residue_satisfied: 2,
        balanced_residue_satisfaction_fraction: 1,
        sub_2A_cross_patch_atom_pairs: 0
      }]
    }
  ]);
  assert.deepEqual(summary.interface, {
    total: 2,
    resolved: 2,
    satisfied: 1,
    violated: 1,
    unresolved: 0,
    satisfaction_fraction_of_resolved: 0.5,
    residue_total: 10,
    residue_satisfied: 8,
    residue_satisfaction_fraction: 0.8,
    all_active_residues_satisfied: 1,
    all_active_residues_satisfied_count: 1,
    minimum_observed_distance: 1.5,
    sub_2A_cross_patch_atom_pairs: 2,
    patch1_residue_total: 5,
    patch1_residue_satisfied: 4,
    patch1_residue_satisfaction_fraction: 0.8,
    patch2_residue_total: 5,
    patch2_residue_satisfied: 4,
    patch2_residue_satisfaction_fraction: 0.8,
    balanced_residue_satisfaction_fraction: ((2 / 3) + 1) / 2,
    mean_maximum_excess_distance: 1.5,
    maximum_excess_distance: 3
  });
});

const mmcifHeader = `data_test
loop_
_atom_site.group_PDB
_atom_site.label_atom_id
_atom_site.label_alt_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.auth_atom_id
_atom_site.auth_asym_id
_atom_site.auth_seq_id
_atom_site.pdbx_PDB_ins_code
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z`;

test("mmCIF restraint endpoints cannot mix author and label namespaces", () => {
  const atoms = parseMmcif(`${mmcifHeader}
ATOM OG . X 1 OG A 10 ? 0.0 0.0 0.0
ATOM N  . Y 2 N  B 20 ? 3.0 0.0 0.0
#`);
  const measured = measureStructure({
    chain1: "A", residue1: 10, atom1: "OG",
    chain2: "Y", residue2: 2, atom2: "N",
    max_distance: 4
  }, atoms, "model_mixed");
  assert.equal(measured.status, "unresolved");
  assert.match(measured.unresolved_reason, /entirely in the author or label namespace/);
});

test("mmCIF author resolution is insertion-code aware", () => {
  const atoms = parseMmcif(`${mmcifHeader}
ATOM OG . X 1 OG A 42 A 0.0 0.0 0.0
ATOM N  . Y 1 N  B 18 ? 3.0 0.0 0.0
#`);
  const measured = measureStructure({
    chain1: "A", residue1: 42, atom1: "OG",
    chain2: "B", residue2: 18, atom2: "N",
    max_distance: 4
  }, atoms, "model_inserted");
  assert.equal(measured.status, "satisfied");
  assert.equal(measured.observed_distance, 3);
});
