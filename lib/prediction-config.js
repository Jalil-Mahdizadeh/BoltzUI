"use strict";

const DEFAULT_PRESET = "standard";

const optionSchema = [
  { key: "out_dir", flag: "--out_dir", label: "Output directory", type: "path", group: "Paths & checkpoints", default: "workspace/results", placeholder: "workspace/results" },
  { key: "cache", flag: "--cache", label: "Cache path", type: "path", group: "Paths & checkpoints", default: "/opt/boltz-cache" },
  { key: "checkpoint", flag: "--checkpoint", label: "Structure checkpoint", type: "path", group: "Paths & checkpoints" },
  { key: "affinity_checkpoint", flag: "--affinity_checkpoint", label: "Affinity checkpoint", type: "path", group: "Paths & checkpoints" },
  { key: "devices", flag: "--devices", label: "Devices", type: "int", group: "Execution", default: "1", min: 1 },
  { key: "accelerator", flag: "--accelerator", label: "Accelerator", type: "select", group: "Execution", default: "gpu", choices: ["gpu", "cpu", "tpu"] },
  { key: "model", flag: "--model", label: "Model", type: "select", group: "Execution", default: "boltz2", choices: ["boltz1", "boltz2"] },
  { key: "method", flag: "--method", label: "Method", type: "text", group: "Execution" },

  { key: "recycling_steps", flag: "--recycling_steps", label: "Recycling steps", type: "int", group: "Sampling", default: "3", min: 0 },
  { key: "sampling_steps", flag: "--sampling_steps", label: "Sampling steps", type: "int", group: "Sampling", default: "200", min: 1 },
  { key: "diffusion_samples", flag: "--diffusion_samples", label: "Diffusion samples", type: "int", group: "Sampling", default: "1", min: 1 },
  { key: "max_parallel_samples", flag: "--max_parallel_samples", label: "Max parallel samples", type: "int", group: "Sampling", default: "1", min: 1 },
  { key: "step_scale", flag: "--step_scale", label: "Step scale", type: "float", group: "Sampling", default: "1.5", min: 0 },
  { key: "seed", flag: "--seed", label: "Seed", type: "int", group: "Sampling", default: "1", min: -1, placeholder: "-1 for random" },
  { key: "use_potentials", flag: "--use_potentials", label: "Use potentials", type: "bool", group: "Sampling", default: false },

  { key: "use_msa_server", flag: "--use_msa_server", label: "Use MSA server", type: "bool", group: "MSA settings", subgroup: "MSA server", default: true },
  { key: "msa_server_url", flag: "--msa_server_url", label: "MSA server URL", type: "text", group: "MSA settings", subgroup: "MSA server", default: "https://api.colabfold.com" },
  { key: "msa_pairing_strategy", flag: "--msa_pairing_strategy", label: "MSA pairing", type: "select", group: "MSA settings", subgroup: "MSA server", default: "greedy", choices: ["greedy", "complete"] },
  { key: "msa_server_username", flag: "--msa_server_username", label: "MSA username", type: "text", group: "MSA settings", subgroup: "MSA credentials", secret: true, defaultDisplay: "not set" },
  { key: "msa_server_password", flag: "--msa_server_password", label: "MSA password", type: "password", group: "MSA settings", subgroup: "MSA credentials", secret: true, defaultDisplay: "not set" },
  { key: "api_key_header", flag: "--api_key_header", label: "API key header", type: "text", group: "MSA settings", subgroup: "MSA credentials", defaultDisplay: "not set" },
  { key: "api_key_value", flag: "--api_key_value", label: "API key value", type: "password", group: "MSA settings", subgroup: "MSA credentials", secret: true, defaultDisplay: "not set" },
  { key: "max_msa_seqs", flag: "--max_msa_seqs", label: "Max MSA sequences", type: "int", group: "MSA settings", subgroup: "MSA limits", default: "8192", min: 1 },
  { key: "subsample_msa", flag: "--subsample_msa", label: "Subsample MSA", type: "bool", group: "MSA settings", subgroup: "MSA limits", default: true },
  { key: "num_subsampled_msa", flag: "--num_subsampled_msa", label: "Subsampled MSA count", type: "int", group: "MSA settings", subgroup: "MSA limits", default: "1024", min: 1, dependsOn: "subsample_msa" },

  { key: "output_format", flag: "--output_format", label: "Output format", type: "select", group: "Output", default: "pdb", choices: ["pdb", "mmcif"] },
  { key: "write_full_pae", flag: "--write_full_pae", label: "Write full PAE", type: "bool", group: "Output", default: true },
  { key: "write_full_pde", flag: "--write_full_pde", label: "Write full PDE", type: "bool", group: "Output", default: false },
  { key: "write_embeddings", flag: "--write_embeddings", label: "Write embeddings", type: "bool", group: "Output", default: false },
  { key: "override", flag: "--override", label: "Override existing", type: "bool", group: "Output", default: false },

  { key: "num_workers", flag: "--num_workers", label: "Data workers", type: "int", group: "Compute", default: "0", min: 0 },
  { key: "preprocessing_threads", flag: "--preprocessing-threads", label: "Preprocessing threads", type: "int", group: "Compute", default: "1", min: 1 },
  { key: "no_kernels", flag: "--no_kernels", label: "Disable kernels", type: "bool", group: "Compute", default: true },

  { key: "affinity_mw_correction", flag: "--affinity_mw_correction", label: "Affinity MW correction", type: "bool", group: "Affinity", default: false, requiresLigand: true },
  { key: "sampling_steps_affinity", flag: "--sampling_steps_affinity", label: "Affinity sampling steps", type: "int", group: "Affinity", default: "200", min: 1, requiresLigand: true },
  { key: "diffusion_samples_affinity", flag: "--diffusion_samples_affinity", label: "Affinity diffusion samples", type: "int", group: "Affinity", default: "5", min: 1, requiresLigand: true }
];

const presets = [
  {
    id: "standard",
    label: "Standard Boltz-2",
    experimental: false,
    description: "Boltz-2 sampling defaults for routine prediction.",
    overrides: {}
  },
  {
    id: "atom_contact",
    label: "Atom-contact exploration",
    experimental: true,
    description: "Experimental atom-pair guidance settings. A lower step scale changes reverse-diffusion updates and sample diversity and can interact with potential guidance strength.",
    overrides: {
      model: "boltz2",
      sampling_steps: "400",
      step_scale: "1.0",
      use_potentials: true
    }
  },
  {
    id: "custom",
    label: "Custom",
    experimental: false,
    description: "Manually edited prediction parameters.",
    overrides: null
  }
];

function normalizeScalar(value, option) {
  if (value === undefined || value === null) return "";
  const text = String(value).trim();
  if (!text) return "";

  if (option.type === "int") {
    if (!/^-?\d+$/.test(text)) throw new Error(`${option.label} must be an integer.`);
    const number = Number(text);
    if (Number.isFinite(option.min) && number < option.min) throw new Error(`${option.label} must be at least ${option.min}.`);
    return String(number);
  }

  if (option.type === "float") {
    const number = Number(text);
    if (!Number.isFinite(number)) throw new Error(`${option.label} must be a number.`);
    if (Number.isFinite(option.min) && number < option.min) throw new Error(`${option.label} must be at least ${option.min}.`);
    return text;
  }

  if (option.type === "select" && option.choices && !option.choices.includes(text)) {
    throw new Error(`${option.label} must be one of: ${option.choices.join(", ")}.`);
  }
  return text;
}

function normalizeOptions(inputOptions = {}) {
  const normalized = {};
  for (const option of optionSchema) {
    const hasValue = Object.prototype.hasOwnProperty.call(inputOptions, option.key);
    if (option.type === "bool") {
      normalized[option.key] = hasValue ? Boolean(inputOptions[option.key]) : Boolean(option.default);
    } else {
      normalized[option.key] = normalizeScalar(hasValue ? inputOptions[option.key] : option.default, option);
    }
  }
  return normalized;
}

function defaultOptions() {
  return normalizeOptions({});
}

function presetById(id) {
  const preset = presets.find((item) => item.id === id);
  if (!preset) throw new Error(`Unknown prediction preset: ${id}.`);
  return preset;
}

function resolvedPresetOptions(id) {
  const preset = presetById(id);
  if (preset.id === "custom") return null;
  return normalizeOptions({ ...defaultOptions(), ...preset.overrides });
}

function resolvePredictionOptions(inputOptions = {}, presetId = DEFAULT_PRESET) {
  const preset = presetById(presetId || DEFAULT_PRESET);
  const options = preset.id === "custom"
    ? normalizeOptions(inputOptions)
    : resolvedPresetOptions(preset.id);
  return { preset: preset.id, options };
}

function publicPresets() {
  return presets.map((preset) => ({
    id: preset.id,
    label: preset.label,
    experimental: preset.experimental,
    description: preset.description,
    options: resolvedPresetOptions(preset.id)
  }));
}

function serializableOptions(options, { includeSecrets = false } = {}) {
  const output = {};
  for (const option of optionSchema) {
    if (option.secret && !includeSecrets) continue;
    const value = options[option.key];
    if (option.type === "int" || option.type === "float") {
      output[option.key] = value === "" ? null : Number(value);
    } else {
      output[option.key] = value;
    }
  }
  return output;
}

module.exports = {
  DEFAULT_PRESET,
  defaultOptions,
  normalizeOptions,
  optionSchema,
  presets,
  publicPresets,
  resolvePredictionOptions,
  serializableOptions
};
