const http = require("node:http");
const fs = require("node:fs");
const fsp = require("node:fs/promises");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { randomUUID } = require("node:crypto");
const EventEmitter = require("node:events");
const {
  documentHasAtomContacts,
  inputMsaSummary,
  parseInputFile,
  parseInputText,
  validateAtomContacts
} = require("./lib/atom-contact");
const { validateTokenContacts } = require("./lib/token-contact");
const { analyzePostprocessEligibility } = require("./lib/postprocess-eligibility");
const {
  DEFAULT_PRESET,
  optionSchema,
  publicPresets,
  resolvePredictionOptions
} = require("./lib/prediction-config");
const { completeRunManifest, createRunManifest, writeJson } = require("./lib/run-manifest");
const { writeRestraintReport } = require("./lib/restraint-report");

const ROOT = process.cwd();
const HOST = process.env.HOST || "0.0.0.0";
const PORT = Number(process.env.PORT || 5173);
const DATA_WORKSPACE_RELATIVE = "workspace";
const INPUTS_RELATIVE = `${DATA_WORKSPACE_RELATIVE}/inputs`;
const RESULTS_RELATIVE = `${DATA_WORKSPACE_RELATIVE}/results`;
const INPUT_DIR = path.join(ROOT, INPUTS_RELATIVE);
const RESULTS_DIR = path.join(ROOT, RESULTS_RELATIVE);
const STATE_DIR = path.join(ROOT, ".boltz-ui");
const JOB_DIR = path.join(STATE_DIR, "jobs");

const INPUT_EXTENSIONS = new Set([".yaml", ".yml", ".json", ".fasta", ".fa", ".faa"]);
const STRUCTURE_EXTENSIONS = new Set([".pdb", ".cif", ".mmcif"]);
const TEXT_EXTENSIONS = new Set([".txt", ".log", ".json", ".yaml", ".yml", ".csv", ".pdb", ".cif", ".mmcif", ".fa", ".faa", ".fasta", ".sh", ".md"]);
const SKIP_DIRS = new Set([".git", ".boltz", ".boltz-ui", "graphify-out", "node_modules"]);

const jobs = new Map();
const inputDescriptionCache = new Map();
const jobEvents = new EventEmitter();
const MSA_SERVER_DEPENDENT_OPTIONS = new Set([
  "msa_server_url",
  "msa_pairing_strategy",
  "msa_server_username",
  "msa_server_password",
  "api_key_header",
  "api_key_value"
]);

function sendJson(res, status, data) {
  const payload = JSON.stringify(data);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store"
  });
  res.end(payload);
}

function sendText(res, status, text, contentType = "text/plain; charset=utf-8") {
  res.writeHead(status, {
    "content-type": contentType,
    "cache-control": "no-store"
  });
  res.end(text);
}

function isInside(child, parent) {
  const relative = path.relative(parent, child);
  return relative === "" || (!!relative && !relative.startsWith("..") && !path.isAbsolute(relative));
}

function safeResolve(relativePath) {
  if (typeof relativePath !== "string" || !relativePath.trim()) {
    throw new Error("A workspace-relative path is required.");
  }
  const cleaned = relativePath.replace(/\0/g, "").replace(/^[/\\]+/, "");
  const resolved = path.resolve(ROOT, cleaned);
  if (!isInside(resolved, ROOT)) {
    throw new Error(`Path escapes workspace: ${relativePath}`);
  }
  return resolved;
}

function toPosix(relativePath) {
  return relativePath.split(path.sep).join("/");
}

function toRelative(absPath) {
  return toPosix(path.relative(ROOT, absPath));
}

async function ensureDataWorkspace() {
  await fsp.mkdir(INPUT_DIR, { recursive: true });
  await fsp.mkdir(RESULTS_DIR, { recursive: true });
}

async function openLocalPath(relativePath = ".") {
  const target = safeResolve(relativePath || ".");
  const stat = await fsp.stat(target);
  const browseTarget = stat.isDirectory() ? target : path.dirname(target);
  let command = "xdg-open";
  const args = [browseTarget];

  if (process.platform === "win32") {
    command = "explorer.exe";
  } else if (process.platform === "darwin") {
    command = "open";
  }

  const child = spawn(command, args, {
    detached: true,
    stdio: "ignore"
  });
  child.unref();
  return toRelative(browseTarget) || ".";
}

function quoteArg(value) {
  const text = String(value);
  if (/^[A-Za-z0-9_./:@%=+,-]+$/.test(text)) {
    return text;
  }
  return JSON.stringify(text);
}

function objectHasLigandEntity(value) {
  if (Array.isArray(value)) return value.some(objectHasLigandEntity);
  if (!value || typeof value !== "object") return false;
  return Object.entries(value).some(([key, child]) => key === "ligand" || key === "ligands" || objectHasLigandEntity(child));
}

function inputHasLigandEntity(dataPath) {
  const extension = path.extname(dataPath).toLowerCase();
  if (![".yaml", ".yml", ".json"].includes(extension)) return false;

  try {
    const text = fs.readFileSync(dataPath, "utf8");
    if (extension === ".json") {
      return objectHasLigandEntity(JSON.parse(text));
    }
    const uncommented = text
      .split(/\r?\n/)
      .filter((line) => !line.trimStart().startsWith("#"))
      .join("\n");
    return /(^|\n)\s*-\s*ligand\s*:/i.test(uncommented);
  } catch {
    return false;
  }
}

function inputCreationTime(stats) {
  const milliseconds = Number(stats.birthtimeMs) > 0 ? stats.birthtimeMs : stats.mtimeMs;
  return new Date(milliseconds).toISOString();
}

async function describeInputFile(dataPath, { inspect = true } = {}) {
  const extension = path.extname(dataPath).toLowerCase();
  const stats = await fsp.stat(dataPath);
  const base = {
    path: toRelative(dataPath),
    name: path.basename(dataPath),
    size: stats.size,
    createdAt: inputCreationTime(stats)
  };
  if (!inspect) return base;

  const signature = `${stats.size}:${stats.mtimeMs}`;
  const cached = inputDescriptionCache.get(dataPath);
  if (cached?.signature === signature) return { ...base, ...cached.details };

  let document = null;
  if ([".yaml", ".yml", ".json"].includes(extension)) {
    try {
      document = parseInputFile(dataPath);
    } catch {
      document = null;
    }
  }
  const details = {
    hasLigand: document ? objectHasLigandEntity(document) : inputHasLigandEntity(dataPath),
    hasAtomContact: document ? documentHasAtomContacts(document) : false,
    postprocessEligibility: inputPostprocessEligibility(dataPath, document)
  };
  inputDescriptionCache.set(dataPath, { signature, details });
  return { ...base, ...details };
}

function sortInputFilesNewestFirst(inputs) {
  return inputs.sort((a, b) => (
    Date.parse(b.createdAt) - Date.parse(a.createdAt)
    || a.name.localeCompare(b.name)
    || a.path.localeCompare(b.path)
  ));
}

function inputPostprocessEligibility(dataPath, parsedDocument = null) {
  const extension = path.extname(dataPath).toLowerCase();
  if (![".yaml", ".yml", ".json"].includes(extension)) {
    return { eligible: true, reason: null };
  }
  try {
    return analyzePostprocessEligibility(parsedDocument || parseInputFile(dataPath));
  } catch (error) {
    const detail = String(error.message || "the file could not be parsed").split("\n")[0];
    return {
      eligible: false,
      reason: `Hydrogen addition and energy minimization are unavailable because this input could not be inspected: ${detail}`
    };
  }
}

function appendPredictOptions(args, options, secretMode = "include", context = {}) {
  for (const option of optionSchema) {
    if (MSA_SERVER_DEPENDENT_OPTIONS.has(option.key) && !options.use_msa_server) {
      continue;
    }
    if (option.dependsOn && !options[option.dependsOn]) {
      continue;
    }
    if (option.requiresLigand && !context.hasLigand) {
      continue;
    }
    if (option.secret && secretMode === "omit") continue;
    const value = options[option.key];
    if (option.type === "bool") {
      if (value) args.push(option.flag);
      continue;
    }
    if (value !== "") {
      args.push(option.flag);
      args.push(secretMode === "mask" && option.secret ? "[hidden]" : value);
    }
  }
}

function predictArgs(dataPath, options, secretMode, dataArg, context = {}) {
  const args = ["predict", dataArg];
  appendPredictOptions(args, options, secretMode, context);
  return args;
}

function displayPath(absolutePath) {
  return isInside(absolutePath, ROOT) ? toRelative(absolutePath) : absolutePath;
}

function resultDirectoryFor(dataPath, options) {
  const outputRoot = path.isAbsolute(options.out_dir)
    ? options.out_dir
    : path.resolve(ROOT, options.out_dir);
  const inputName = path.basename(dataPath, path.extname(dataPath));
  return path.join(outputRoot, `boltz_results_${inputName}`);
}

function preparePrediction(payload) {
  const dataPath = safeResolve(payload.data);
  const stat = fs.statSync(dataPath);
  if (!stat.isFile()) throw new Error("Input data path must be a file.");

  const document = parseInputFile(dataPath);
  const { restraints, unionGroups } = validateAtomContacts(document);
  const { contacts: tokenContacts } = validateTokenContacts(document);
  const hasAtomContacts = restraints.length > 0 || unionGroups.length > 0;
  const requestedPreset = payload.preset || (payload.options ? "custom" : DEFAULT_PRESET);
  const { preset, options } = resolvePredictionOptions(
    payload.options || {},
    requestedPreset,
    { hasAtomContacts }
  );
  const context = { hasLigand: inputHasLigandEntity(dataPath) };
  const postprocessEligibility = inputPostprocessEligibility(dataPath, document);
  if ((options.addh || options.addh_energy_min) && !postprocessEligibility.eligible) {
    throw new Error(postprocessEligibility.reason);
  }
  const args = predictArgs(dataPath, options, "include", dataPath, context);
  const maskedArgs = predictArgs(dataPath, options, "mask", dataPath, context);
  const manifestArgs = predictArgs(dataPath, options, "omit", dataPath, context);
  const resultDirectory = resultDirectoryFor(dataPath, options);
  return {
    executable: "boltzui-predict",
    args,
    maskedArgs,
    manifestArgs,
    env: { ...process.env },
    command: `boltzui-predict ${args.map(quoteArg).join(" ")}`,
    maskedCommand: `boltzui-predict ${maskedArgs.map(quoteArg).join(" ")}`,
    data: toRelative(dataPath),
    dataPath,
    document,
    options,
    preset,
    atomContacts: restraints,
    atomContactUnions: unionGroups,
    tokenContacts,
    msa: inputMsaSummary(document, options),
    resultDirectory,
    outputDirectory: displayPath(resultDirectory)
  };
}

function buildBoltzCommand(payload, { maskSecrets = false } = {}) {
  const prediction = preparePrediction(payload);
  return {
    ...prediction,
    args: maskSecrets ? prediction.maskedArgs : prediction.args,
    command: maskSecrets ? prediction.maskedCommand : prediction.command
  };
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const text = Buffer.concat(chunks).toString("utf8");
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    throw new Error("Request body must be valid JSON.");
  }
}

async function walkFiles(dir, output = []) {
  const entries = await fsp.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name.startsWith(".") || SKIP_DIRS.has(entry.name)) continue;

    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      await walkFiles(fullPath, output);
    } else if (entry.isFile()) {
      output.push(fullPath);
    }
  }
  return output;
}

async function listInputFiles({ inspect = true } = {}) {
  await ensureDataWorkspace();
  const files = await walkFiles(INPUT_DIR);
  const inputs = await Promise.all(files
    .filter((file) => INPUT_EXTENSIONS.has(path.extname(file).toLowerCase()))
    .filter((file) => !["package.json", "package-lock.json"].includes(path.basename(file).toLowerCase()))
    .map((file) => describeInputFile(file, { inspect })));
  return sortInputFilesNewestFirst(inputs);
}

async function findFiles(dir, predicate, limit = 1500, output = []) {
  if (output.length >= limit) return output;
  let entries = [];
  try {
    entries = await fsp.readdir(dir, { withFileTypes: true });
  } catch {
    return output;
  }
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      await findFiles(fullPath, predicate, limit, output);
    } else if (entry.isFile() && predicate(fullPath)) {
      output.push(fullPath);
      if (output.length >= limit) break;
    }
  }
  return output;
}

function numericMetric(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

async function readJsonIfPresent(filePath) {
  try {
    return JSON.parse(await fsp.readFile(filePath, "utf8"));
  } catch {
    return null;
  }
}

function modelIndexFromName(file) {
  const match = path.basename(file).match(/model_(\d+)/);
  return match ? Number(match[1]) : null;
}

async function summarizeResultDir(dir) {
  const predictionsDir = path.join(dir, "predictions");
  const structureFiles = await findFiles(predictionsDir, (file) => STRUCTURE_EXTENSIONS.has(path.extname(file).toLowerCase()));
  const confidenceFiles = await findFiles(predictionsDir, (file) => path.basename(file).startsWith("confidence_") && path.extname(file).toLowerCase() === ".json");
  const paeFiles = await findFiles(predictionsDir, (file) => path.basename(file).startsWith("pae_"));
  const pdeFiles = await findFiles(predictionsDir, (file) => path.basename(file).startsWith("pde_"));
  const plddtFiles = await findFiles(predictionsDir, (file) => path.basename(file).startsWith("plddt_"));

  const structureByModel = new Map(structureFiles.map((file) => [modelIndexFromName(file), file]));
  const originalModels = [];
  for (const confidenceFile of confidenceFiles) {
    let metrics = {};
    try {
      metrics = JSON.parse(await fsp.readFile(confidenceFile, "utf8"));
    } catch {
      metrics = {};
    }
    const index = modelIndexFromName(confidenceFile);
    originalModels.push({
      index,
      selectionKey: `${index}:original`,
      variant: "original",
      auditModel: index === null ? null : `model_${index}`,
      confidencePath: toRelative(confidenceFile),
      structurePath: structureByModel.has(index) ? toRelative(structureByModel.get(index)) : null,
      confidenceScore: numericMetric(metrics.confidence_score),
      ptm: numericMetric(metrics.ptm),
      iptm: numericMetric(metrics.iptm),
      complexPlddt: numericMetric(metrics.complex_plddt),
      complexPde: numericMetric(metrics.complex_pde)
    });
  }

  originalModels.sort((a, b) => {
    if (a.index === null && b.index === null) return a.confidencePath.localeCompare(b.confidencePath);
    if (a.index === null) return 1;
    if (b.index === null) return -1;
    return a.index - b.index;
  });

  const bestModel = originalModels.reduce((best, model) => {
    if (model.confidenceScore === null) return best;
    if (!best || model.confidenceScore > best.confidenceScore) return model;
    return best;
  }, null);

  let manifest = null;
  const manifestPath = path.join(dir, "processed", "manifest.json");
  try {
    manifest = JSON.parse(await fsp.readFile(manifestPath, "utf8"));
  } catch {
    manifest = null;
  }

  const runManifestFile = path.join(dir, "boltzui_run.json");
  const restraintReportFile = path.join(dir, "contact_restraints.json");
  const legacyRestraintReportFile = path.join(dir, "atom_contact_restraints.json");
  const postprocessReportFile = path.join(dir, "boltzui_postprocess.json");
  const runManifest = await readJsonIfPresent(runManifestFile);
  const currentRestraintReport = await readJsonIfPresent(restraintReportFile);
  const restraintReport = currentRestraintReport
    || await readJsonIfPresent(legacyRestraintReportFile);
  const resolvedRestraintReportFile = currentRestraintReport
    ? restraintReportFile
    : legacyRestraintReportFile;
  const postprocessReport = await readJsonIfPresent(postprocessReportFile);
  const models = [...originalModels];
  if (Array.isArray(postprocessReport?.models)) {
    for (const processed of postprocessReport.models) {
      if (processed?.status !== "succeeded" || typeof processed.output !== "string") continue;
      const outputPath = path.resolve(dir, processed.output);
      if (!isInside(outputPath, dir) || !STRUCTURE_EXTENSIONS.has(path.extname(outputPath).toLowerCase())) continue;
      try {
        if (!(await fsp.stat(outputPath)).isFile()) continue;
      } catch {
        continue;
      }
      const index = Number.isInteger(processed.model_index) ? processed.model_index : modelIndexFromName(outputPath);
      const original = originalModels.find((model) => model.index === index) || {};
      const variant = postprocessReport.mode === "addh_energy_min" ? "addh_energy_min" : "addh";
      models.push({
        ...original,
        index,
        selectionKey: `${index}:${variant}`,
        variant,
        auditModel: index === null ? null : `model_${index}_${variant}`,
        structurePath: toRelative(outputPath),
        postprocess: processed
      });
    }
  }
  models.sort((a, b) => {
    if (a.index !== b.index) return (a.index ?? Number.MAX_SAFE_INTEGER) - (b.index ?? Number.MAX_SAFE_INTEGER);
    const rank = { original: 0, addh: 1, addh_energy_min: 2 };
    return (rank[a.variant] ?? 9) - (rank[b.variant] ?? 9);
  });

  const stats = await fsp.stat(dir);
  return {
    name: path.basename(dir),
    path: toRelative(dir),
    modifiedAt: stats.mtime.toISOString(),
    structures: models.filter((model) => model.structurePath).length,
    confidenceFiles: confidenceFiles.length,
    paeFiles: paeFiles.length,
    pdeFiles: pdeFiles.length,
    plddtFiles: plddtFiles.length,
    bestModel,
    models,
    manifest,
    runManifest,
    runManifestPath: runManifest ? toRelative(runManifestFile) : null,
    restraintReport,
    restraintReportPath: restraintReport ? toRelative(resolvedRestraintReportFile) : null,
    postprocessReport,
    postprocessReportPath: postprocessReport ? toRelative(postprocessReportFile) : null
  };
}

async function listResults() {
  await ensureDataWorkspace();
  const entries = await fsp.readdir(RESULTS_DIR, { withFileTypes: true });
  const dirs = entries
    .filter((entry) => entry.isDirectory() && entry.name.startsWith("boltz_results_"))
    .map((entry) => path.join(RESULTS_DIR, entry.name));
  const summaries = await Promise.all(dirs.map(summarizeResultDir));
  return summaries.sort((a, b) => new Date(b.modifiedAt) - new Date(a.modifiedAt));
}

function publicJob(job, includeLogs = false) {
  const summary = {
    id: job.id,
    status: job.status,
    startedAt: job.startedAt,
    endedAt: job.endedAt,
    exitCode: job.exitCode,
    signal: job.signal,
    command: job.command,
    data: job.data,
    preset: job.preset,
    failureReason: job.failureReason || null,
    logPath: job.logPath ? toRelative(job.logPath) : null,
    manifestPath: job.manifestPath ? displayPath(job.manifestPath) : null,
    restraintReportPath: job.restraintReportPath ? displayPath(job.restraintReportPath) : null
  };
  if (includeLogs) summary.logs = job.logs;
  return summary;
}

function addLog(job, chunk) {
  const text = String(chunk).replace(/\r\n/g, "\n");
  if (!text) return;
  const failureMatch = text.match(/(Failed to process[^\n]*|Skipping\. Error:[^\n]*|tarfile\.ReadError[^\n]*)/i);
  if (failureMatch) {
    job.detectedFailure = true;
    job.failureReason = failureMatch[1].trim();
  }
  const lines = text.split("\n");
  for (const line of lines) {
    if (!line && lines.length > 1) continue;
    job.logs.push(line);
  }
  if (job.logs.length > 2500) {
    job.logs.splice(0, job.logs.length - 2500);
  }
  fs.appendFile(job.logPath, text, () => {});
  jobEvents.emit(job.id, { type: "log", data: { text } });
}

async function startJob(payload) {
  await fsp.mkdir(JOB_DIR, { recursive: true });
  await ensureDataWorkspace();
  const prediction = preparePrediction(payload);
  const id = `${new Date().toISOString().replace(/[:.]/g, "-")}-${randomUUID().slice(0, 8)}`;
  const logPath = path.join(JOB_DIR, `${id}.log`);
  const manifestStagingPath = path.join(JOB_DIR, `${id}.manifest.json`);
  const job = {
    id,
    status: "running",
    startedAt: new Date().toISOString(),
    endedAt: null,
    exitCode: null,
    signal: null,
    command: prediction.maskedCommand,
    data: prediction.data,
    preset: prediction.preset,
    options: prediction.options,
    atomContacts: prediction.atomContacts,
    atomContactUnions: prediction.atomContactUnions,
    tokenContacts: prediction.tokenContacts,
    resultDirectory: prediction.resultDirectory,
    manifestStagingPath,
    manifestPath: null,
    restraintReportPath: null,
    detectedFailure: false,
    failureReason: null,
    logPath,
    logs: []
  };
  job.manifest = createRunManifest({
    root: ROOT,
    jobId: id,
    preset: prediction.preset,
    options: prediction.options,
    args: prediction.manifestArgs,
    inputPath: prediction.dataPath,
    outputDirectory: prediction.outputDirectory,
    atomContacts: prediction.atomContacts,
    atomContactUnions: prediction.atomContactUnions,
    tokenContacts: prediction.tokenContacts,
    msa: prediction.msa,
    startedAt: job.startedAt,
    executable: prediction.executable
  });
  jobs.set(id, job);
  await fsp.writeFile(logPath, "", "utf8");
  await writeJson(manifestStagingPath, job.manifest);
  addLog(job, `${job.startedAt} ${job.command}\n`);

  const child = spawn(prediction.executable, prediction.args, {
    cwd: ROOT,
    env: prediction.env,
    windowsHide: true
  });
  job.child = child;
  job.pid = child.pid;

  child.stdout.on("data", (chunk) => addLog(job, chunk));
  child.stderr.on("data", (chunk) => addLog(job, chunk));
  child.on("error", (error) => {
    job.status = "failed";
    job.failureReason = `Process error: ${error.message}`;
    addLog(job, `\nProcess error: ${error.message}\n`);
  });
  child.on("close", async (code, signal) => {
    if (job.status === "stopping") {
      job.status = "stopped";
    } else if (job.status !== "failed") {
      job.status = code === 0 && !job.detectedFailure ? "succeeded" : "failed";
    }
    job.exitCode = code;
    job.signal = signal;
    job.endedAt = new Date().toISOString();
    if (job.detectedFailure && code === 0) {
      addLog(job, "\nBoltz reported an input-processing failure even though the process exited with code 0.\n");
    }
    addLog(job, `\nExited with code ${code}${signal ? ` (${signal})` : ""}.\n`);
    try {
      if (job.atomContacts.length > 0 || job.atomContactUnions.length > 0 || job.tokenContacts.length > 0) {
        const audit = await writeRestraintReport(
          job.resultDirectory,
          job.atomContacts,
          job.atomContactUnions,
          job.tokenContacts
        );
        job.restraintReportPath = audit.reportPath;
      }
    } catch (error) {
      job.status = "failed";
      job.failureReason = `Restraint report generation failed: ${error.message}`;
      addLog(job, `\n${job.failureReason}\n`);
    }
    try {
      job.manifest.structure_postprocessing = await readJsonIfPresent(
        path.join(job.resultDirectory, "boltzui_postprocess.json")
      );
      job.manifest = completeRunManifest(job.manifest, job);
      job.manifestPath = path.join(job.resultDirectory, "boltzui_run.json");
      await writeJson(job.manifestStagingPath, job.manifest);
      await writeJson(job.manifestPath, job.manifest);
    } catch (error) {
      job.status = "failed";
      job.failureReason = `Run manifest finalization failed: ${error.message}`;
      addLog(job, `\n${job.failureReason}\n`);
    }
    jobEvents.emit(job.id, { type: "status", data: publicJob(job) });
  });

  return publicJob(job, true);
}

async function stopJob(id) {
  const job = jobs.get(id);
  if (!job) throw new Error("Job not found.");
  if (!job.child || job.status !== "running") return publicJob(job, true);
  job.status = "stopping";
  addLog(job, "\nStopping job...\n");
  job.child.kill("SIGTERM");
  jobEvents.emit(job.id, { type: "status", data: publicJob(job) });
  return publicJob(job, true);
}

function streamJobEvents(req, res, id) {
  const job = jobs.get(id);
  if (!job) {
    sendJson(res, 404, { error: "Job not found." });
    return;
  }

  res.writeHead(200, {
    "content-type": "text/event-stream; charset=utf-8",
    "cache-control": "no-cache, no-transform",
    connection: "keep-alive"
  });

  const send = (type, data) => {
    res.write(`event: ${type}\n`);
    res.write(`data: ${JSON.stringify(data)}\n\n`);
  };

  send("status", publicJob(job));

  const listener = (event) => send(event.type, event.data);
  jobEvents.on(id, listener);
  req.on("close", () => jobEvents.off(id, listener));
}

function contentType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const map = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon"
  };
  return map[ext] || "application/octet-stream";
}

async function serveStatic(urlPath, res) {
  const publicRoot = path.join(ROOT, "public");
  const requested = urlPath === "/" ? "/index.html" : urlPath;
  const decoded = decodeURIComponent(requested);
  const fullPath = path.resolve(publicRoot, decoded.replace(/^[/\\]+/, ""));
  if (!isInside(fullPath, publicRoot)) {
    sendJson(res, 403, { error: "Forbidden." });
    return;
  }
  try {
    const stat = await fsp.stat(fullPath);
    if (!stat.isFile()) throw new Error("Not a file.");
    res.writeHead(200, {
      "content-type": contentType(fullPath),
      "cache-control": "no-store"
    });
    fs.createReadStream(fullPath).pipe(res);
  } catch {
    sendJson(res, 404, { error: "Not found." });
  }
}

async function handleApi(req, res, url) {
  if (req.method === "GET" && url.pathname === "/api/state") {
    await ensureDataWorkspace();
    const includeInputs = url.searchParams.get("inputs") !== "0";
    const [inputs, results] = await Promise.all([
      includeInputs ? listInputFiles() : Promise.resolve(null),
      listResults()
    ]);
    sendJson(res, 200, {
      workspace: ROOT,
      options: optionSchema,
      presets: publicPresets(),
      defaultPreset: DEFAULT_PRESET,
      inputs,
      results,
      jobs: Array.from(jobs.values()).map((job) => publicJob(job))
    });
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/inputs") {
    const inspect = url.searchParams.get("details") !== "0";
    sendJson(res, 200, { workspace: ROOT, inputs: await listInputFiles({ inspect }) });
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/results") {
    sendJson(res, 200, { results: await listResults() });
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/command") {
    const payload = await readBody(req);
    const command = buildBoltzCommand(payload, { maskSecrets: true });
    sendJson(res, 200, {
      command: command.command,
      data: command.data,
      preset: command.preset,
      options: command.options
    });
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/atom-constraints/parse") {
    const payload = await readBody(req);
    const extension = String(payload.filename || "").toLowerCase().endsWith(".json")
      ? ".json"
      : ".yaml";
    const document = parseInputText(String(payload.content || ""), extension);
    const { restraints, unionGroups } = validateAtomContacts(document, { validateChains: false });
    sendJson(res, 200, {
      exact: restraints.map((restraint) => ({
        atom1: `${restraint.chain1}:${restraint.residue1}:${restraint.atom1}`,
        atom2: `${restraint.chain2}:${restraint.residue2}:${restraint.atom2}`,
        distance: String(restraint.max_distance),
        force: restraint.force
      })),
      unions: unionGroups.map((group) => ({
        force: group.force,
        alternatives: group.alternatives.map((alternative) => ({
          atom1: `${alternative.chain1}:${alternative.residue1}:${alternative.atom1}`,
          atom2: `${alternative.chain2}:${alternative.residue2}:${alternative.atom2}`,
          distance: String(alternative.max_distance)
        }))
      }))
    });
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/token-constraints/parse") {
    const payload = await readBody(req);
    const extension = String(payload.filename || "").toLowerCase().endsWith(".json")
      ? ".json"
      : ".yaml";
    const document = parseInputText(String(payload.content || ""), extension);
    if (!Array.isArray(document.constraints)) {
      throw new Error("Token constraint YAML must contain a top-level constraints list.");
    }
    const { contacts } = validateTokenContacts(document, { validateChains: false });
    sendJson(res, 200, {
      constraintCount: document.constraints.length,
      contacts: contacts.map((contact) => ({
        token1: `${contact.chain1}:${contact.token1}`,
        token2: `${contact.chain2}:${contact.token2}`,
        distance: String(contact.max_distance),
        force: contact.force
      }))
    });
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/jobs") {
    sendJson(res, 200, { jobs: Array.from(jobs.values()).map((job) => publicJob(job)) });
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/jobs") {
    const payload = await readBody(req);
    const job = await startJob(payload);
    sendJson(res, 201, { job });
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/open-path") {
    const payload = await readBody(req);
    const opened = await openLocalPath(payload.path || ".");
    sendJson(res, 200, { opened });
    return;
  }

  const jobMatch = url.pathname.match(/^\/api\/jobs\/([^/]+)(?:\/(events|stop))?$/);
  if (jobMatch) {
    const id = jobMatch[1];
    const action = jobMatch[2];
    if (req.method === "GET" && !action) {
      const job = jobs.get(id);
      if (!job) return sendJson(res, 404, { error: "Job not found." });
      return sendJson(res, 200, { job: publicJob(job, true) });
    }
    if (req.method === "GET" && action === "events") {
      return streamJobEvents(req, res, id);
    }
    if (req.method === "POST" && action === "stop") {
      const job = await stopJob(id);
      return sendJson(res, 200, { job });
    }
  }

  if (req.method === "GET" && url.pathname === "/api/file") {
    const relative = url.searchParams.get("path") || "";
    const fullPath = safeResolve(relative);
    const stat = await fsp.stat(fullPath);
    if (!stat.isFile()) return sendJson(res, 404, { error: "Not found." });
    const ext = path.extname(fullPath).toLowerCase();
    const type = TEXT_EXTENSIONS.has(ext) ? `text/plain; charset=utf-8` : "application/octet-stream";
    res.writeHead(200, {
      "content-type": type,
      "content-length": stat.size,
      "cache-control": "no-store"
    });
    fs.createReadStream(fullPath).pipe(res);
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/inputs") {
    const payload = await readBody(req);
    const name = String(payload.name || "").trim();
    if (!/^[A-Za-z0-9_.-]+\.(ya?ml|json|fasta|fa|faa)$/i.test(name)) {
      throw new Error("Input file name must be a simple YAML, JSON, or FASTA name.");
    }
    await ensureDataWorkspace();
    const target = path.resolve(INPUT_DIR, name);
    if (!isInside(target, INPUT_DIR)) throw new Error("Input file path escapes the input workspace.");
    await fsp.writeFile(target, String(payload.content || ""), "utf8");
    const input = await describeInputFile(target);
    sendJson(res, 201, {
      input
    });
    return;
  }

  sendJson(res, 404, { error: "API route not found." });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || `${HOST}:${PORT}`}`);
  try {
    if (url.pathname.startsWith("/api/")) {
      await handleApi(req, res, url);
      return;
    }
    await serveStatic(url.pathname, res);
  } catch (error) {
    sendJson(res, 400, { error: error.message || "Request failed." });
  }
});

if (require.main === module) {
  server.listen(PORT, HOST, async () => {
    await fsp.mkdir(JOB_DIR, { recursive: true });
    console.log(`Boltz UI listening at http://${HOST}:${PORT}`);
    console.log(`Workspace: ${ROOT}`);
  });
}

module.exports = {
  buildBoltzCommand,
  describeInputFile,
  listInputFiles,
  preparePrediction,
  sortInputFilesNewestFirst,
  summarizeResultDir
};
