"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { defaultOptions, presets } = require("../lib/prediction-config");

const ROOT = path.resolve(__dirname, "..");
const FILES = ["README.md", "REQUIREMENTS.md", "DOCKER_HUB.md"];
const START = "<!-- BEGIN GENERATED PREDICTION PRESETS -->";
const END = "<!-- END GENERATED PREDICTION PRESETS -->";

function value(preset, key) {
  if (preset.overrides && Object.prototype.hasOwnProperty.call(preset.overrides, key)) {
    return preset.overrides[key];
  }
  return defaultOptions()[key];
}

function generatedBlock() {
  const standard = presets.find((preset) => preset.id === "standard");
  const atomContact = presets.find((preset) => preset.id === "atom_contact");
  return [
    START,
    "| Preset | Sampling steps | Step scale | Potentials | Status |",
    "|---|---:|---:|---|---|",
    `| ${standard.label} | ${value(standard, "sampling_steps")} | ${value(standard, "step_scale")} | ${value(standard, "use_potentials") ? "On" : "Off"} | Standard |`,
    `| ${atomContact.label} | ${value(atomContact, "sampling_steps")} | ${value(atomContact, "step_scale")} | ${value(atomContact, "use_potentials") ? "On" : "Off"} | Experimental |`,
    "",
    "The atom-contact exploration preset is experimental. Its lower step scale changes the reverse-diffusion update and sample diversity and may interact with inference-time potential guidance; it is not a mathematical guarantee of restraint satisfaction.",
    END
  ].join("\n");
}

function synchronize(fileName, checkOnly) {
  const filePath = path.join(ROOT, fileName);
  const original = fs.readFileSync(filePath, "utf8");
  const pattern = new RegExp(`${START}[\\s\\S]*?${END}`);
  if (!pattern.test(original)) throw new Error(`${fileName} is missing generated preset markers.`);
  const updated = original.replace(pattern, generatedBlock());
  if (checkOnly && updated !== original) throw new Error(`${fileName} preset documentation is stale. Run npm run docs:sync.`);
  if (!checkOnly && updated !== original) fs.writeFileSync(filePath, updated, "utf8");
}

const checkOnly = process.argv.includes("--check");
for (const fileName of FILES) synchronize(fileName, checkOnly);
console.log(checkOnly ? "Prediction preset documentation is current." : "Prediction preset documentation synchronized.");
