"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { inputMsaSummary, parseInputText, validateAtomContacts } = require("../lib/atom-contact");

const fixture = fs.readFileSync(path.join(__dirname, "..", "fixtures", "atom_contact_example.yaml"), "utf8");

function documentFromFixture() {
  return parseInputText(fixture, ".yaml");
}

test("valid atom-contact example parses and validates", () => {
  const result = validateAtomContacts(documentFromFixture(), { usePotentials: true });
  assert.equal(result.restraints.length, 1);
  assert.deepEqual(result.restraints[0], {
    chain1: "A", residue1: 1, atom1: "OG",
    chain2: "B", residue2: 1, atom2: "N",
    max_distance: 4, force: true
  });
});

test("non-atom-contact input remains unaffected", () => {
  const result = validateAtomContacts({ sequences: [{ protein: { id: "A", sequence: "M" } }] }, { usePotentials: false });
  assert.deepEqual(result.restraints, []);
});

test("invalid chain fails preflight", () => {
  const document = documentFromFixture();
  document.constraints[0].atom_contact.atom1[0] = "Z";
  assert.throws(() => validateAtomContacts(document, { usePotentials: true }), /Z:1:OG: chain does not exist/);
});

test("invalid polymer residue fails preflight", () => {
  const document = documentFromFixture();
  document.constraints[0].atom_contact.atom1[1] = 2;
  assert.throws(() => validateAtomContacts(document, { usePotentials: true }), /A:2:OG: residue exceeds chain length 1/);
});

test("empty atom name fails preflight", () => {
  const document = documentFromFixture();
  document.constraints[0].atom_contact.atom1[2] = "";
  assert.throws(() => validateAtomContacts(document, { usePotentials: true }), /atom name must be nonempty/);
});

test("identical endpoints and invalid distances fail preflight", () => {
  const identical = documentFromFixture();
  identical.constraints[0].atom_contact.atom2 = ["A", 1, "OG"];
  assert.throws(() => validateAtomContacts(identical, { usePotentials: true }), /endpoints are identical/);

  const invalidDistance = documentFromFixture();
  invalidDistance.constraints[0].atom_contact.max_distance = "not-a-number";
  assert.throws(() => validateAtomContacts(invalidDistance, { usePotentials: true }), /max_distance must be finite and positive/);
});

test("atom-contact validation does not require optional physical potentials", () => {
  const result = validateAtomContacts(documentFromFixture(), { usePotentials: false });
  assert.equal(result.restraints.length, 1);
});

test("explicit empty MSA is recorded without claiming server use", () => {
  const msa = inputMsaSummary(documentFromFixture(), { use_msa_server: true, msa_server_url: "https://example.test" });
  assert.equal(msa.mode, "empty");
  assert.equal(msa.use_msa_server, false);
  assert.equal(msa.server_url, null);
});

test("duplicate and conflicting duplicate restraints are distinguished", () => {
  const duplicate = documentFromFixture();
  duplicate.constraints.push(JSON.parse(JSON.stringify(duplicate.constraints[0])));
  assert.throws(() => validateAtomContacts(duplicate, { usePotentials: true }), /Duplicate atom_contact restraint/);

  const conflict = documentFromFixture();
  const reversed = JSON.parse(JSON.stringify(conflict.constraints[0]));
  [reversed.atom_contact.atom1, reversed.atom_contact.atom2] = [reversed.atom_contact.atom2, reversed.atom_contact.atom1];
  reversed.atom_contact.max_distance = 5;
  conflict.constraints.push(reversed);
  assert.throws(() => validateAtomContacts(conflict, { usePotentials: true }), /Conflicting duplicate atom_contact restraint/);
});
