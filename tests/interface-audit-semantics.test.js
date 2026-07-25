"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { normalize } = require("../public/interface-audit-semantics");

test("schema 8 distinguishes existential contact from strict coverage", () => {
  const result = normalize({
    satisfied: true,
    patch_contact_satisfied: true,
    all_active_residues_satisfied: false,
    patch1_residue_total: 2,
    patch1_residue_satisfied: 1,
    patch2_residue_total: 1,
    patch2_residue_satisfied: 1,
    balanced_residue_satisfaction_fraction: 0.75
  }, 8);
  assert.equal(result.patchContact, true);
  assert.equal(result.allActiveResidues, false);
  assert.equal(result.status, "partial");
  assert.equal(result.balancedCoverage, 0.75);
});

test("legacy strict interface reports are not mislabeled as no patch contact", () => {
  const result = normalize({
    satisfied: false,
    residue_restraints: [
      { patch: "patch1", satisfied: true },
      { patch: "patch2", satisfied: false }
    ]
  }, 6);
  assert.equal(result.patchContact, true);
  assert.equal(result.allActiveResidues, false);
  assert.equal(result.status, "partial");
});

test("legacy reports without residue detail keep failed patch contact unresolved", () => {
  const result = normalize({ satisfied: false }, 5);
  assert.equal(result.patchContact, null);
  assert.equal(result.allActiveResidues, false);
  assert.equal(result.status, "unresolved");
});
