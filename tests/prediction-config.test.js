"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { resolvePredictionOptions } = require("../lib/prediction-config");

test("Standard Boltz-2 preset resolves authoritative defaults", () => {
  const resolved = resolvePredictionOptions({}, "standard");
  assert.equal(resolved.preset, "standard");
  assert.equal(resolved.options.sampling_steps, "200");
  assert.equal(resolved.options.step_scale, "1.5");
  assert.equal(resolved.options.use_potentials, false);
});

test("atom-contact preset resolves experimental settings", () => {
  const resolved = resolvePredictionOptions({}, "atom_contact");
  assert.equal(resolved.options.sampling_steps, "400");
  assert.equal(resolved.options.step_scale, "1.0");
  assert.equal(resolved.options.use_potentials, true);
  assert.equal(resolved.options.model, "boltz2");
});

test("custom preset preserves validated manual values", () => {
  const resolved = resolvePredictionOptions({ sampling_steps: "275", step_scale: "1.2" }, "custom");
  assert.equal(resolved.options.sampling_steps, "275");
  assert.equal(resolved.options.step_scale, "1.2");
});
