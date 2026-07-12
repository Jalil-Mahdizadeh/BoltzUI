"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { METHOD_CHOICES, optionSchema, resolvePredictionOptions } = require("../lib/prediction-config");

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
  assert.equal(resolved.options.override, true);
  assert.equal(resolved.options.model, "boltz2");
});

test("custom preset preserves validated manual values", () => {
  const resolved = resolvePredictionOptions({ sampling_steps: "275", step_scale: "1.2" }, "custom");
  assert.equal(resolved.options.sampling_steps, "275");
  assert.equal(resolved.options.step_scale, "1.2");
});

test("atom-contact tasks default override on but respect explicit custom override off", () => {
  const automatic = resolvePredictionOptions({}, "standard", { hasAtomContacts: true });
  assert.equal(automatic.options.override, true);

  const explicit = resolvePredictionOptions({ override: false }, "custom", { hasAtomContacts: true });
  assert.equal(explicit.options.override, false);
});

test("Method is a supported dropdown and defaults to X-RAY DIFFRACTION", () => {
  const method = optionSchema.find((option) => option.key === "method");
  assert.equal(method.type, "select");
  assert.equal(method.default, "x-ray diffraction");
  assert.equal(method.choiceLabels[method.default], "X-RAY DIFFRACTION");
  assert.deepEqual(method.choices, METHOD_CHOICES);
  assert.equal(method.choices.some((choice) => /^future[1-5]$/i.test(choice)), false);
  assert.throws(
    () => resolvePredictionOptions({ method: "unsupported method" }, "custom"),
    /Method must be one of/
  );
});
