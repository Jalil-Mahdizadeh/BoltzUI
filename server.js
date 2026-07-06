const http = require("node:http");
const fs = require("node:fs");
const fsp = require("node:fs/promises");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { randomUUID } = require("node:crypto");
const EventEmitter = require("node:events");

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

const optionSchema = [
  { key: "out_dir", flag: "--out_dir", label: "Output directory", type: "path", group: "Paths & checkpoints", default: RESULTS_RELATIVE, placeholder: RESULTS_RELATIVE },
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
  { key: "max_msa_seqs", flag: "--max_msa_seqs", label: "Max MSA sequences", type: "int", group: "MSA settings", subgroup: "MSA limits", default: "2048", min: 1 },
  { key: "subsample_msa", flag: "--subsample_msa", label: "Subsample MSA", type: "bool", group: "MSA settings", subgroup: "MSA limits", default: true },
  { key: "num_subsampled_msa", flag: "--num_subsampled_msa", label: "Subsampled MSA count", type: "int", group: "MSA settings", subgroup: "MSA limits", default: "2048", min: 1 },

  { key: "output_format", flag: "--output_format", label: "Output format", type: "select", group: "Output", default: "pdb", choices: ["pdb", "mmcif"] },
  { key: "write_full_pae", flag: "--write_full_pae", label: "Write full PAE", type: "bool", group: "Output", default: true },
  { key: "write_full_pde", flag: "--write_full_pde", label: "Write full PDE", type: "bool", group: "Output", default: false },
  { key: "write_embeddings", flag: "--write_embeddings", label: "Write embeddings", type: "bool", group: "Output", default: false },
  { key: "override", flag: "--override", label: "Override existing", type: "bool", group: "Output", default: false },

  { key: "num_workers", flag: "--num_workers", label: "Data workers", type: "int", group: "Compute", default: "0", min: 0 },
  { key: "preprocessing_threads", flag: "--preprocessing-threads", label: "Preprocessing threads", type: "int", group: "Compute", default: "1", min: 1 },
  { key: "no_kernels", flag: "--no_kernels", label: "Disable kernels", type: "bool", group: "Compute", default: true },

  { key: "affinity_mw_correction", flag: "--affinity_mw_correction", label: "Affinity MW correction", type: "bool", group: "Affinity", default: false },
  { key: "sampling_steps_affinity", flag: "--sampling_steps_affinity", label: "Affinity sampling steps", type: "int", group: "Affinity", default: "200", min: 1 },
  { key: "diffusion_samples_affinity", flag: "--diffusion_samples_affinity", label: "Affinity diffusion samples", type: "int", group: "Affinity", default: "5", min: 1 }
];

const jobs = new Map();
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
      continue;
    }
    normalized[option.key] = normalizeScalar(hasValue ? inputOptions[option.key] : option.default, option);
  }
  return normalized;
}

function appendPredictOptions(args, options, maskSecrets) {
  for (const option of optionSchema) {
    if (MSA_SERVER_DEPENDENT_OPTIONS.has(option.key) && !options.use_msa_server) {
      continue;
    }
    const value = options[option.key];
    if (option.type === "bool") {
      if (value) args.push(option.flag);
      continue;
    }
    if (value !== "") {
      args.push(option.flag);
      args.push(maskSecrets && option.secret ? "[hidden]" : value);
    }
  }
}

function predictArgs(dataPath, options, maskSecrets, dataArg) {
  const args = ["predict", dataArg];
  appendPredictOptions(args, options, maskSecrets);
  return args;
}

function buildBoltzCommand(payload, { maskSecrets = false } = {}) {
  const dataPath = safeResolve(payload.data);
  const stat = fs.statSync(dataPath);
  if (!stat.isFile()) throw new Error("Input data path must be a file.");

  const options = normalizeOptions(payload.options || {});
  const args = predictArgs(dataPath, options, maskSecrets, dataPath);
  const command = `boltz ${args.map(quoteArg).join(" ")}`;
  return {
    executable: "boltz",
    args,
    env: { ...process.env },
    command,
    data: toRelative(dataPath)
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

async function listInputFiles() {
  await ensureDataWorkspace();
  const files = await walkFiles(INPUT_DIR);
  return files
    .filter((file) => INPUT_EXTENSIONS.has(path.extname(file).toLowerCase()))
    .filter((file) => !["package.json", "package-lock.json"].includes(path.basename(file).toLowerCase()))
    .map((file) => ({ path: toRelative(file), name: path.basename(file), size: fs.statSync(file).size }))
    .sort((a, b) => a.path.localeCompare(b.path));
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
  const models = [];
  for (const confidenceFile of confidenceFiles) {
    let metrics = {};
    try {
      metrics = JSON.parse(await fsp.readFile(confidenceFile, "utf8"));
    } catch {
      metrics = {};
    }
    const index = modelIndexFromName(confidenceFile);
    models.push({
      index,
      confidencePath: toRelative(confidenceFile),
      structurePath: structureByModel.has(index) ? toRelative(structureByModel.get(index)) : null,
      confidenceScore: numericMetric(metrics.confidence_score),
      ptm: numericMetric(metrics.ptm),
      iptm: numericMetric(metrics.iptm),
      complexPlddt: numericMetric(metrics.complex_plddt),
      complexPde: numericMetric(metrics.complex_pde)
    });
  }

  models.sort((a, b) => {
    if (a.index === null && b.index === null) return a.confidencePath.localeCompare(b.confidencePath);
    if (a.index === null) return 1;
    if (b.index === null) return -1;
    return a.index - b.index;
  });

  const bestModel = models.reduce((best, model) => {
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

  const stats = await fsp.stat(dir);
  return {
    name: path.basename(dir),
    path: toRelative(dir),
    modifiedAt: stats.mtime.toISOString(),
    structures: structureFiles.length,
    confidenceFiles: confidenceFiles.length,
    paeFiles: paeFiles.length,
    pdeFiles: pdeFiles.length,
    plddtFiles: plddtFiles.length,
    bestModel,
    models,
    manifest
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
    failureReason: job.failureReason || null,
    logPath: job.logPath ? toRelative(job.logPath) : null
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
  const realCommand = buildBoltzCommand(payload, { maskSecrets: false });
  const maskedCommand = buildBoltzCommand(payload, { maskSecrets: true });
  const id = `${new Date().toISOString().replace(/[:.]/g, "-")}-${randomUUID().slice(0, 8)}`;
  const logPath = path.join(JOB_DIR, `${id}.log`);
  const job = {
    id,
    status: "running",
    startedAt: new Date().toISOString(),
    endedAt: null,
    exitCode: null,
    signal: null,
    command: maskedCommand.command,
    data: realCommand.data,
    detectedFailure: false,
    failureReason: null,
    logPath,
    logs: []
  };
  jobs.set(id, job);
  await fsp.writeFile(logPath, "", "utf8");
  addLog(job, `${job.startedAt} ${job.command}\n`);

  const child = spawn(realCommand.executable, realCommand.args, {
    cwd: ROOT,
    env: realCommand.env,
    windowsHide: true
  });
  job.child = child;
  job.pid = child.pid;

  child.stdout.on("data", (chunk) => addLog(job, chunk));
  child.stderr.on("data", (chunk) => addLog(job, chunk));
  child.on("error", (error) => {
    job.status = "failed";
    job.endedAt = new Date().toISOString();
    addLog(job, `\nProcess error: ${error.message}\n`);
    jobEvents.emit(job.id, { type: "status", data: publicJob(job) });
  });
  child.on("close", (code, signal) => {
    if (job.status === "stopping") {
      job.status = "stopped";
    } else {
      job.status = code === 0 && !job.detectedFailure ? "succeeded" : "failed";
    }
    job.exitCode = code;
    job.signal = signal;
    job.endedAt = new Date().toISOString();
    if (job.detectedFailure && code === 0) {
      addLog(job, "\nBoltz reported an input-processing failure even though the process exited with code 0.\n");
    }
    addLog(job, `\nExited with code ${code}${signal ? ` (${signal})` : ""}.\n`);
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
    sendJson(res, 200, {
      workspace: ROOT,
      options: optionSchema,
      inputs: await listInputFiles(),
      results: await listResults(),
      jobs: Array.from(jobs.values()).map((job) => publicJob(job))
    });
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/results") {
    sendJson(res, 200, { results: await listResults() });
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/command") {
    const payload = await readBody(req);
    const command = buildBoltzCommand(payload, { maskSecrets: true });
    sendJson(res, 200, { command: command.command, data: command.data });
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
    sendJson(res, 201, { input: { path: toRelative(target), name: path.basename(target), size: fs.statSync(target).size } });
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

server.listen(PORT, HOST, async () => {
  await fsp.mkdir(JOB_DIR, { recursive: true });
  console.log(`Boltz UI listening at http://${HOST}:${PORT}`);
  console.log(`Workspace: ${ROOT}`);
});
