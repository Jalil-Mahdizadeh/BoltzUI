"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
const os = require("node:os");
const { buildBoltzCommand, summarizeResultDir } = require("../server");

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

test("hydrogen flags use the BoltzUI wrapper and are passed to copied commands", () => {
  const prediction = buildBoltzCommand({ data: input, preset: "custom", options: { addh: true } });
  assert.equal(prediction.executable, "boltzui-predict");
  assert.equal(prediction.args.includes("--addh"), true);
  assert.match(prediction.command, /^boltzui-predict predict /);
});

test("ligand inputs are rejected instead of silently misparameterized", () => {
  assert.throws(
    () => buildBoltzCommand({ data: path.join("fixtures", "protein_ligand_example.yaml"), preset: "custom", options: { addh: true } }),
    /ligand chain B/
  );
});

test("modified polymers are rejected by the same authoritative preflight", () => {
  assert.throws(
    () => buildBoltzCommand({ data: path.join("fixtures", "protein_modified_example.yaml"), preset: "custom", options: { addh_energy_min: true } }),
    /modified residue \(MSE\)/
  );
});

test("result summaries expose originals and successful post-processed variants", async () => {
  const result = fs.mkdtempSync(path.join(os.tmpdir(), "boltzui-result-"));
  const prediction = path.join(result, "predictions", "case");
  const processed = path.join(result, "postprocessed", "addh", "case");
  fs.mkdirSync(prediction, { recursive: true });
  fs.mkdirSync(processed, { recursive: true });
  fs.writeFileSync(path.join(prediction, "case_model_0.pdb"), "END\n");
  fs.writeFileSync(path.join(prediction, "confidence_case_model_0.json"), JSON.stringify({ confidence_score: 0.8 }));
  fs.writeFileSync(path.join(processed, "case_model_0_addh.pdb"), "END\n");
  fs.writeFileSync(path.join(result, "boltzui_postprocess.json"), JSON.stringify({
    mode: "addh",
    models: [{ status: "succeeded", model_index: 0, output: "postprocessed/addh/case/case_model_0_addh.pdb" }]
  }));
  const summary = await summarizeResultDir(result);
  assert.deepEqual(summary.models.map((model) => model.variant), ["original", "addh"]);
  assert.equal(summary.structures, 2);
  assert.equal(summary.bestModel.variant, "original");
});
