"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { measureStructure, parseMmcif, parsePdb } = require("../lib/restraint-report");

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
