"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const YAML = require("yaml");
const { parseBuilderYaml } = require("../lib/builder-yaml");

function regenerate(parsed) {
  const context = vm.createContext({
    parsed, setTimeout, clearTimeout,
    InterfaceBuilderValidation: require("../public/interface-builder-validation"),
    document: { querySelector: () => ({ value: "", checked: false }) }
  });
  const source = fs.readFileSync(path.join(__dirname, "../public/builder.js"), "utf8")
    .replace(/bindBuilderPage\(\);\s*loadWorkspace\(\);\s*$/, "");
  vm.runInContext(source, context);
  return YAML.parse(vm.runInContext("Object.assign(builderState, parsed); buildYamlFromBuilder().yaml", context));
}

test("builder round trips YAML block scalars, comments, anchors and flow mappings", () => {
  for (const content of [
    "version: 1\nsequences:\n  - protein:\n      id: A\n      sequence: |-\n        ACDE\n        FG\n      msa: empty\n",
    "version: 1\nsequences: # entities\n  - protein:\n      id: A\n      sequence: ACDEFG # normal comment\n      msa: empty\n",
    "version: 1\nsequences: [{protein: {id: [A, B], sequence: &seq ACDEFG, msa: empty}}, {protein: {id: C, sequence: *seq, msa: empty}}]\n"
  ]) {
    const expected = YAML.parse(content).sequences;
    const actual = regenerate(parseBuilderYaml(content)).sequences;
    expected.forEach((entity, index) => {
      assert.equal(actual[index].protein.sequence, entity.protein.sequence.replace(/\s/g, ""));
      assert.deepEqual(actual[index].protein.id, entity.protein.id);
    });
  }
});

test("builder maps nested block lists and quoted template paths", () => {
  const parsed = parseBuilderYaml(`version: 1
sequences:
  - protein: {id: A, sequence: AAAAAA, msa: empty}
constraints:
  - interface_contact:
      patch1: {chain: A, residues: [1]}
      patch2:
        chain: A
        residues:
          - 4
          - 6
      max_distance: 6
      force: true
templates:
  - cif: './a # template.cif'
    chain_id: A
    template_id: X
`);
  assert.equal(parsed.interfaceContacts[0].patch2Residues, "4\n6");
  assert.equal(parsed.templates[0].path, "./a # template.cif");
  assert.deepEqual(regenerate(parsed).constraints[0].interface_contact.patch2.residues, [4, 6]);
});

test("unsupported fields and malformed YAML cannot be silently regenerated", () => {
  assert.throws(() => parseBuilderYaml("version: 1\nsequences: [{protein: {id: A, sequence: ACDE, future_option: true}}]"), /cannot preserve/);
  assert.throws(() => parseBuilderYaml("version: 1\nsequences: ["));
  assert.throws(() => parseBuilderYaml("version: 1\nsequences: [{ligand: {id: A, ccd: ATP}}]"), /no polymers/);
});
