"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {
  documentHasAtomContacts,
  inputMsaSummary,
  parseInputText,
  validateAtomContacts
} = require("../lib/atom-contact");

const fixture = fs.readFileSync(path.join(__dirname, "..", "fixtures", "atom_contact_example.yaml"), "utf8");
const unionFixture = fs.readFileSync(
  path.join(__dirname, "..", "fixtures", "atom_contact_union_example.yaml"),
  "utf8"
);

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
  assert.deepEqual(result.unionGroups, []);
});

test("valid atom-contact union preserves one OR group and per-alternative bounds", () => {
  const document = parseInputText(unionFixture, ".yaml");
  const result = validateAtomContacts(document);
  assert.equal(documentHasAtomContacts(document), true);
  assert.equal(result.restraints.length, 0);
  assert.equal(result.unionGroups.length, 1);
  assert.equal(result.unionGroups[0].alternatives.length, 2);
  assert.deepEqual(
    result.unionGroups[0].alternatives.map((alternative) => alternative.max_distance),
    [4, 4]
  );
  assert.deepEqual(result.unionGroups[0].alternatives[0], {
    chain1: "A", residue1: 1, atom1: "OG",
    chain2: "B", residue2: 1, atom2: "N",
    max_distance: 4, force: true, alternative_index: 1
  });
});

test("constraints-only nmr2boltz union YAML validates structurally for the loader", () => {
  const text = fs.readFileSync(
    path.join(__dirname, "..", "fixtures", "nmr2boltz", "atom_constraints_union.yaml"),
    "utf8"
  );
  const result = validateAtomContacts(parseInputText(text), { validateChains: false });
  assert.equal(result.unionGroups.length, 1);
  assert.equal(result.unionGroups[0].alternatives.length, 2);
});

test("union validation rejects incomplete, non-forced, duplicate, and unresolved groups", () => {
  const fewer = parseInputText(unionFixture);
  fewer.constraints[0].atom_contact_union.alternatives.pop();
  assert.throws(() => validateAtomContacts(fewer), /at least two/);

  const notForced = parseInputText(unionFixture);
  notForced.constraints[0].atom_contact_union.force = false;
  assert.throws(() => validateAtomContacts(notForced), /requires force: true/);

  const duplicate = parseInputText(unionFixture);
  const first = duplicate.constraints[0].atom_contact_union.alternatives[0];
  duplicate.constraints[0].atom_contact_union.alternatives[1] = {
    atom1: first.atom2,
    atom2: first.atom1,
    max_distance: first.max_distance
  };
  assert.throws(() => validateAtomContacts(duplicate), /Duplicate atom_contact_union 1 alternative/);

  const unresolved = parseInputText(unionFixture);
  unresolved.constraints[0].atom_contact_union.alternatives[1].atom1 = ["Z", 1, "N"];
  assert.throws(
    () => validateAtomContacts(unresolved),
    /Unable to resolve atom-contact endpoint Z:1:N/
  );

  const invalidBound = parseInputText(unionFixture);
  invalidBound.constraints[0].atom_contact_union.alternatives[1].max_distance = 20.000001;
  assert.throws(() => validateAtomContacts(invalidBound), /between 2.0 and 20.0 Angstrom/);

  const identical = parseInputText(unionFixture);
  const alternative = identical.constraints[0].atom_contact_union.alternatives[1];
  alternative.atom2 = [...alternative.atom1];
  assert.throws(() => validateAtomContacts(identical), /endpoints are identical/);

  const nonMapping = parseInputText(unionFixture);
  nonMapping.constraints[0].atom_contact_union.alternatives[1] = "invalid";
  assert.throws(() => validateAtomContacts(nonMapping), /alternative 2 must be a mapping/);
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
