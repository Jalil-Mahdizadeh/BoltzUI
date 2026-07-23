"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  buildPolymerChainIndex,
  validateInterfacePatch
} = require("../public/interface-builder-validation");

test("builder interface validation indexes every declared polymer chain", () => {
  const chains = buildPolymerChainIndex([
    { ids: "A", type: "protein", sequence: "SAK" },
    { ids: "B, C", type: "protein", sequence: "GD" }
  ]);
  assert.equal(chains.get("A").length, 3);
  assert.equal(chains.get("B").length, 2);
  assert.equal(chains.get("C").length, 2);
});

test("builder interface validation rejects missing chains and unavailable residues", () => {
  const chains = buildPolymerChainIndex([
    { ids: "A", type: "protein", sequence: "SAK" },
    { ids: "B", type: "protein", sequence: "GD" }
  ]);
  assert.deepEqual(validateInterfacePatch("A", [1, 3], "Patch 1", chains), []);
  assert.deepEqual(
    validateInterfacePatch("C", [1], "Patch 2", chains),
    ['Patch 2 chain "C" does not exist among the current polymers.']
  );
  assert.deepEqual(
    validateInterfacePatch("B", [3], "Patch 2", chains),
    ["Patch 2 residue B:3 exceeds chain length 2."]
  );
});

test("builder interface validation requires an unambiguous protein chain", () => {
  const chains = buildPolymerChainIndex([
    { ids: "A", type: "protein", sequence: "SA" },
    { ids: "A", type: "protein", sequence: "GD" },
    { ids: "R", type: "rna", sequence: "AC" }
  ]);
  assert.match(validateInterfacePatch("A", [1], "Patch 1", chains)[0], /more than one polymer/);
  assert.match(validateInterfacePatch("R", [1], "Patch 2", chains)[0], /must be a protein/);
});
