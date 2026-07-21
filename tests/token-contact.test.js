"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { parseInputText } = require("../lib/atom-contact");
const {
  documentHasTokenContacts,
  validateTokenContacts
} = require("../lib/token-contact");

const fixture = fs.readFileSync(
  path.join(__dirname, "..", "fixtures", "nmr2boltz", "token_constraints.yaml"),
  "utf8"
);

function fullDocument() {
  return {
    sequences: [
      { protein: { id: "A", sequence: "M".repeat(20) } },
      { protein: { id: "B", sequence: "M".repeat(50) } },
      { ligand: { id: "L", ccd: "ATP" } }
    ],
    constraints: [
      { contact: { token1: ["A", 17], token2: ["B", 42], max_distance: 6, force: false } }
    ]
  };
}

test("constraints-only nmr2boltz token YAML validates for the loader", () => {
  const document = parseInputText(fixture);
  const result = validateTokenContacts(document, { validateChains: false });
  assert.equal(documentHasTokenContacts(document), true);
  assert.deepEqual(result.contacts, [{
    chain1: "A", token1: 17,
    chain2: "B", token2: 42,
    max_distance: 6, force: false
  }]);
});

test("token validation ignores other constraint types and accepts an empty list", () => {
  assert.deepEqual(validateTokenContacts({ constraints: [] }).contacts, []);
  assert.deepEqual(validateTokenContacts({ constraints: [{ atom_contact: {} }] }).contacts, []);
});

test("token validation accepts polymer residues and ligand atom names", () => {
  const document = fullDocument();
  document.constraints.push({
    contact: { token1: ["A", 1], token2: ["L", "C1"], max_distance: 4, force: true }
  });
  const result = validateTokenContacts(document);
  assert.equal(result.contacts.length, 2);
  assert.deepEqual(result.contacts[1], {
    chain1: "A", token1: 1,
    chain2: "L", token2: "C1",
    max_distance: 4, force: true
  });
});

test("token validation rejects invalid endpoints and unresolved selectors", () => {
  const malformed = fullDocument();
  malformed.constraints[0].contact.token1 = ["A"];
  assert.throws(() => validateTokenContacts(malformed), /must be \[CHAIN_ID, RES_IDX\/ATOM_NAME\]/);

  const missingChain = fullDocument();
  missingChain.constraints[0].contact.token1 = ["Z", 1];
  assert.throws(() => validateTokenContacts(missingChain), /chain does not exist/);

  const longResidue = fullDocument();
  longResidue.constraints[0].contact.token1 = ["A", 21];
  assert.throws(() => validateTokenContacts(longResidue), /residue exceeds chain length 20/);

  const polymerAtom = fullDocument();
  polymerAtom.constraints[0].contact.token1 = ["A", "CA"];
  assert.throws(() => validateTokenContacts(polymerAtom), /polymer tokens require a positive residue index/);

  const ligandResidue = fullDocument();
  ligandResidue.constraints[0].contact.token1 = ["L", 1];
  assert.throws(() => validateTokenContacts(ligandResidue), /ligand tokens require an atom name/);
});

test("token validation enforces distance, force, and distinct endpoints", () => {
  const distance = fullDocument();
  distance.constraints[0].contact.max_distance = 20.1;
  assert.throws(() => validateTokenContacts(distance), /between 4.0 and 20.0 Angstrom/);

  const force = fullDocument();
  force.constraints[0].contact.force = "false";
  assert.throws(() => validateTokenContacts(force), /force must be true or false/);

  const identical = fullDocument();
  identical.constraints[0].contact.token2 = ["A", 17];
  assert.throws(() => validateTokenContacts(identical), /endpoints are identical/);
});

test("duplicate and conflicting reversed token contacts are distinguished", () => {
  const duplicate = fullDocument();
  duplicate.constraints.push({
    contact: { token1: ["B", 42], token2: ["A", 17], max_distance: 6, force: false }
  });
  assert.throws(() => validateTokenContacts(duplicate), /Duplicate contact constraint/);

  const conflict = fullDocument();
  conflict.constraints.push({
    contact: { token1: ["B", 42], token2: ["A", 17], max_distance: 7, force: false }
  });
  assert.throws(() => validateTokenContacts(conflict), /Conflicting duplicate contact constraint/);
});
