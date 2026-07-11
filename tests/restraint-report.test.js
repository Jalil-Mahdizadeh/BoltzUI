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
