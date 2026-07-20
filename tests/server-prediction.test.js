"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { buildBoltzCommand } = require("../server");

const input = path.join("fixtures", "atom_contact_example.yaml");
const unionInput = path.join("fixtures", "atom_contact_union_example.yaml");

test("atom-contact commands default override on without run-specific output directories", () => {
  const prediction = buildBoltzCommand({ data: input, preset: "standard" });
  assert.equal(prediction.options.override, true);
  assert.equal(prediction.args.includes("--override"), true);
  assert.equal(prediction.outputDirectory, "workspace/results/boltz_results_atom_contact_example");
});

test("explicit override and physical potentials off are respected for atom contacts", () => {
  const prediction = buildBoltzCommand({
    data: input,
    preset: "custom",
    options: { override: false, use_potentials: false }
  });
  assert.equal(prediction.options.override, false);
  assert.equal(prediction.options.use_potentials, false);
  assert.equal(prediction.args.includes("--override"), false);
  assert.equal(prediction.args.includes("--use_potentials"), false);
  assert.equal(prediction.atomContacts.length, 1);
});

test("union-only atom contacts trigger the same safe override policy", () => {
  const prediction = buildBoltzCommand({ data: unionInput, preset: "standard" });
  assert.equal(prediction.options.override, true);
  assert.equal(prediction.atomContacts.length, 0);
  assert.equal(prediction.atomContactUnions.length, 1);
  assert.equal(prediction.atomContactUnions[0].alternatives.length, 2);
});
