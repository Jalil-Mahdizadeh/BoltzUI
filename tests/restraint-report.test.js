"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const {
  measureStructure,
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
  assert.equal(report.schema_version, 4);
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
