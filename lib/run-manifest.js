"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const fsp = require("node:fs/promises");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { serializableOptions } = require("./prediction-config");

let cachedRuntimeMetadata = null;

function commandOutput(command, args, cwd) {
  try {
    const result = spawnSync(command, args, { cwd, encoding: "utf8", windowsHide: true });
    if (result.status !== 0) return null;
    return String(result.stdout || result.stderr || "").trim() || null;
  } catch {
    return null;
  }
}

function runtimeMetadata(root) {
  if (cachedRuntimeMetadata) return cachedRuntimeMetadata;
  const gitCommit = commandOutput("git", ["rev-parse", "HEAD"], root);
  const gitDirty = Boolean(commandOutput("git", ["status", "--porcelain"], root));
  const versionOutput = commandOutput("python", ["-c", "import boltz; print(getattr(boltz, '__version__', 'unknown'))"], root);
  const versionMatch = versionOutput && versionOutput.match(/\d+\.\d+\.\d+/);
  cachedRuntimeMetadata = {
    boltzui_git_commit: gitCommit,
    boltzui_git_dirty: gitDirty,
    boltz_version: versionMatch ? versionMatch[0] : versionOutput || "unknown"
  };
  return cachedRuntimeMetadata;
}

function sha256File(filePath) {
  const hash = crypto.createHash("sha256");
  hash.update(fs.readFileSync(filePath));
  return hash.digest("hex");
}

function createRunManifest({
  root,
  jobId,
  preset,
  options,
  args,
  inputPath,
  outputDirectory,
  atomContacts,
  atomContactUnions = [],
  msa,
  startedAt,
  metadata,
  executable = "boltzui-predict"
}) {
  const resolved = serializableOptions(options);
  const runtime = metadata || runtimeMetadata(root);
  return {
    schema_version: 3,
    job_id: jobId,
    boltzui_git_commit: runtime.boltzui_git_commit || null,
    boltzui_git_dirty: Boolean(runtime.boltzui_git_dirty),
    boltz_version: runtime.boltz_version || "unknown",
    selected_preset: preset,
    resolved_prediction_parameters: resolved,
    command: {
      executable,
      arguments: [...args]
    },
    input_file: path.basename(inputPath),
    input_path: path.relative(root, inputPath).split(path.sep).join("/"),
    input_sha256: sha256File(inputPath),
    seed: resolved.seed,
    model: resolved.model,
    sampling_steps: resolved.sampling_steps,
    recycling_steps: resolved.recycling_steps,
    diffusion_samples: resolved.diffusion_samples,
    step_scale: resolved.step_scale,
    use_potentials: resolved.use_potentials,
    msa,
    start_time: startedAt,
    completion_time: null,
    exit_status: "running",
    exit_code: null,
    signal: null,
    failure_reason: null,
    output_directory: outputDirectory,
    atom_contact_constraints: atomContacts,
    atom_contact_union_constraints: atomContactUnions
  };
}

function completeRunManifest(manifest, job) {
  return {
    ...manifest,
    completion_time: job.endedAt,
    exit_status: job.status,
    exit_code: job.exitCode,
    signal: job.signal,
    failure_reason: job.failureReason || null
  };
}

async function writeJson(filePath, value) {
  await fsp.mkdir(path.dirname(filePath), { recursive: true });
  const temporary = `${filePath}.tmp`;
  await fsp.writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  await fsp.rename(temporary, filePath);
}

module.exports = {
  completeRunManifest,
  createRunManifest,
  runtimeMetadata,
  sha256File,
  writeJson
};
