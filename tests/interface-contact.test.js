"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { parseInputFile } = require("../lib/atom-contact");
const {
  documentHasInterfaceContacts,
  validateInterfaceContacts
} = require("../lib/interface-contact");

const fixture = path.join(__dirname, "..", "fixtures", "interface_contact_example.yaml");
const singleChainFixture = path.join(
  __dirname,
  "..",
  "fixtures",
  "interface_contact_single_chain_example.yaml"
);

test("multichain CSP interface patches validate and normalize", () => {
  const document = parseInputFile(fixture);
  const { interfaces } = validateInterfaceContacts(document);
  assert.equal(documentHasInterfaceContacts(document), true);
  assert.deepEqual(interfaces[0], {
    interface_index: 1,
    patch1: { chain: "A", residues: [1, 3] },
    patch2: { chain: "B", residues: [1, 2] },
    max_distance: 6,
    force: true
  });
});

test("disjoint patches on the same protein chain are supported", () => {
  const { interfaces } = validateInterfaceContacts(parseInputFile(singleChainFixture));
  assert.equal(interfaces.length, 1);
  assert.equal(interfaces[0].patch1.chain, "A");
  assert.equal(interfaces[0].patch2.chain, "A");
});

test("same-chain overlap, invalid bounds, and duplicate residues are rejected", () => {
  const document = parseInputFile(singleChainFixture);
  document.constraints[0].interface_contact.patch2.residues = [2, 5];
  assert.throws(() => validateInterfaceContacts(document), /same-chain patches must be disjoint/);

  const invalidBound = parseInputFile(fixture);
  invalidBound.constraints[0].interface_contact.max_distance = 20.1;
  assert.throws(() => validateInterfaceContacts(invalidBound), /between 4.0 and 20.0/);

  const duplicateResidue = parseInputFile(fixture);
  duplicateResidue.constraints[0].interface_contact.patch1.residues = [1, 1];
  assert.throws(() => validateInterfaceContacts(duplicateResidue), /duplicate residue 1/);
});

test("same-chain patches made only of immediate neighbors are rejected", () => {
  const document = parseInputFile(singleChainFixture);
  document.constraints[0].interface_contact.patch1.residues = [2];
  document.constraints[0].interface_contact.patch2.residues = [3];
  assert.throws(
    () => validateInterfaceContacts(document),
    /every active residue must have a non-neighbor residue/
  );
});

test("every same-chain active residue needs an eligible opposite target", () => {
  const document = parseInputFile(singleChainFixture);
  document.constraints[0].interface_contact.patch1.residues = [1, 5];
  document.constraints[0].interface_contact.patch2.residues = [2];
  assert.throws(
    () => validateInterfaceContacts(document),
    /residues without an eligible target: patch1: 1/
  );
});

test("cyclic closure neighbors are rejected and topology is retained for reporting", () => {
  const invalid = parseInputFile(singleChainFixture);
  invalid.sequences[0].protein.cyclic = true;
  invalid.constraints[0].interface_contact.patch1.residues = [1];
  invalid.constraints[0].interface_contact.patch2.residues = [6];
  assert.throws(
    () => validateInterfaceContacts(invalid),
    /every active residue must have a non-neighbor residue/
  );

  const valid = parseInputFile(singleChainFixture);
  valid.sequences[0].protein.cyclic = true;
  valid.constraints[0].interface_contact.patch1.residues = [1];
  valid.constraints[0].interface_contact.patch2.residues = [4];
  const { interfaces } = validateInterfaceContacts(valid);
  assert.deepEqual(interfaces[0].cyclic_periods, { A: 6 });
});

test("interface force accepts an explicit off/report-only state", () => {
  const document = parseInputFile(fixture);
  document.constraints[0].interface_contact.force = false;
  const { interfaces } = validateInterfaceContacts(document);
  assert.equal(interfaces[0].force, false);
});

test("duplicate and reversed interface patch pairs are rejected", () => {
  const duplicate = parseInputFile(fixture);
  duplicate.constraints.push(JSON.parse(JSON.stringify(duplicate.constraints[0])));
  assert.throws(
    () => validateInterfaceContacts(duplicate),
    /Duplicate interface_contact constraint/
  );

  const reversed = parseInputFile(fixture);
  const original = reversed.constraints[0].interface_contact;
  reversed.constraints.push({
    interface_contact: {
      patch1: original.patch2,
      patch2: original.patch1,
      max_distance: 7,
      force: true
    }
  });
  assert.throws(
    () => validateInterfaceContacts(reversed),
    /Duplicate interface_contact constraint/
  );
});
