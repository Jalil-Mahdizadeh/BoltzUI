const state = {
  schema: [],
  options: {},
  inputs: [],
  results: [],
  jobs: [],
  selectedResult: null,
  selectedModelIndex: null,
  selectedJob: null,
  workspace: "",
  eventSource: null,
  viewer: null,
  currentStructureText: null,
  currentStructurePath: null
};

const $ = (selector) => document.querySelector(selector);

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timeout);
  showToast.timeout = setTimeout(() => {
    toast.hidden = true;
  }, 3600);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "content-type": "application/json" },
    ...options
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  return data;
}

function debounce(fn, delay) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function defaultsFromSchema(schema) {
  return schema.reduce((acc, option) => {
    acc[option.key] = option.type === "bool"
      ? Boolean(option.default)
      : option.default === undefined ? "" : String(option.default);
    return acc;
  }, {});
}

function groupOptions(schema) {
  const groups = new Map();
  for (const option of schema) {
    if (!groups.has(option.group)) groups.set(option.group, []);
    groups.get(option.group).push(option);
  }
  return groups;
}

function formatNumber(value, digits = 3) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "-";
}

function formatDate(value) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return "-";
  }
}

function metric(label, value) {
  return `<div class="metric"><strong>${formatNumber(value)}</strong><span>${label}</span></div>`;
}

function basename(filePath) {
  return String(filePath || "").split(/[\\/]/).pop() || "model";
}

function fileStem(filePath) {
  return basename(filePath).replace(/\.[^.]+$/, "");
}

function selectedInputPath() {
  return $("#input-file")?.value || "";
}

function resultsForSelectedInput() {
  const inputPath = selectedInputPath();
  if (!inputPath) return [];
  const expectedName = `boltz_results_${fileStem(inputPath)}`.toLowerCase();
  return state.results.filter((result) => String(result.name || "").toLowerCase() === expectedName);
}

function clamp(value, min = 0, max = 1) {
  return Math.min(max, Math.max(min, value));
}

function normalizeScore(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return 0;
  return clamp(value > 1.5 ? value / 100 : value);
}

function scoreCell(value) {
  const pct = Math.round(normalizeScore(value) * 100);
  return `
    <div class="score-cell">
      <span>${formatNumber(value)}</span>
      <div class="score-track"><i class="score-fill" style="width: ${pct}%"></i></div>
    </div>
  `;
}

function setFileLink(selector, filePath) {
  const link = $(selector);
  if (!link) return;
  if (!filePath) {
    link.href = "#";
    link.classList.add("disabled");
    link.removeAttribute("title");
    return;
  }
  link.href = `/api/file?path=${encodeURIComponent(filePath)}`;
  link.title = filePath;
  link.classList.remove("disabled");
}

function modelLabel(model) {
  if (!model) return "None";
  if (model.index === null || model.index === undefined) {
    return basename(model.structurePath || model.confidencePath).replace(/\.(pdb|cif|mmcif|json)$/i, "");
  }
  return `model ${model.index}`;
}

function currentResult() {
  const results = resultsForSelectedInput();
  if (!results.length) {
    state.selectedResult = null;
    return null;
  }
  if (!state.selectedResult || !results.some((result) => result.path === state.selectedResult)) {
    state.selectedResult = results[0].path;
  }
  return results.find((result) => result.path === state.selectedResult) || results[0];
}

function currentModel(result = currentResult()) {
  if (!result || !result.models || !result.models.length) return null;
  if (state.selectedModelIndex !== null) {
    const selected = result.models.find((model) => String(model.index) === String(state.selectedModelIndex));
    if (selected) return selected;
  }
  return result.bestModel || result.models[0];
}

function latestJob() {
  return state.jobs.find((job) => job.status === "running")
    || state.jobs.find((job) => job.id === state.selectedJob)
    || state.jobs[0]
    || null;
}

function renderOverview() {
  const job = latestJob();
  const selectedInput = selectedInputPath();
  const visibleResults = resultsForSelectedInput();
  const structureCount = visibleResults.reduce((total, result) => total + (result.structures || 0), 0);

  const metricInput = $("#metric-input");
  metricInput.textContent = selectedInput ? basename(selectedInput) : "-";
  metricInput.title = selectedInput || "";
  $("#metric-input-detail").textContent = selectedInput
    ? "Selected input"
    : "Choose or save an input";
  $("#metric-results").textContent = String(visibleResults.length);
  $("#metric-results-detail").textContent = `${structureCount} structures`;
  const runState = $("#metric-run-state");
  const runDetail = $("#metric-run-detail");
  runState.textContent = job ? job.status : "Idle";
  runDetail.textContent = job ? basename(job.data || job.id) : "Ready";
  runDetail.title = job ? (job.data || job.id) : "";
}

function renderInputs() {
  const select = $("#input-file");
  const previous = select.value;
  select.innerHTML = "";
  for (const file of state.inputs) {
    const option = document.createElement("option");
    option.value = file.path;
    option.textContent = file.path;
    option.title = file.path;
    select.appendChild(option);
  }
  if (previous && state.inputs.some((file) => file.path === previous)) {
    select.value = previous;
  }
  $("#input-count").textContent = select.value ? "1 input" : "No input";
  select.title = select.value || "";
  const selectedInputPill = $("#selected-input-pill");
  selectedInputPill.textContent = select.value ? basename(select.value) : "None";
  selectedInputPill.title = select.value || "";
  $("#selected-input-meta").textContent = select.value ? "Ready" : "Waiting";
  renderOverview();
}

function renderSegmented(option, value) {
  const wrapper = document.createElement("div");
  wrapper.className = "field";
  const label = document.createElement("span");
  label.textContent = option.label;
  wrapper.appendChild(label);

  const segmented = document.createElement("div");
  segmented.className = "segmented";
  for (const choice of option.choices) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `segment-button${value === choice ? " active" : ""}`;
    button.textContent = choice;
    button.addEventListener("click", () => {
      state.options[option.key] = choice;
      renderOptionGroups();
      renderOverview();
      updateCommandPreview();
    });
    segmented.appendChild(button);
  }
  wrapper.appendChild(segmented);
  return wrapper;
}

function renderOptionField(option) {
  const value = state.options[option.key];
  if (option.type === "bool") {
    const label = document.createElement("label");
    label.className = "toggle-field";
    const text = document.createElement("span");
    text.textContent = option.label;
    const toggle = document.createElement("span");
    toggle.className = "switch";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = Boolean(value);
    input.addEventListener("change", () => {
      state.options[option.key] = input.checked;
      renderOverview();
      updateCommandPreview();
    });
    const slider = document.createElement("span");
    slider.className = "slider";
    toggle.append(input, slider);
    label.append(text, toggle);
    return label;
  }

  if (option.type === "select" && option.choices && option.choices.length <= 3) {
    return renderSegmented(option, value);
  }

  const label = document.createElement("label");
  label.className = "field";
  const text = document.createElement("span");
  text.textContent = option.label;
  const input = option.type === "select" ? document.createElement("select") : document.createElement("input");

  if (option.type === "select") {
    for (const choice of option.choices) {
      const item = document.createElement("option");
      item.value = choice;
      item.textContent = choice;
      input.appendChild(item);
    }
  } else {
    input.type = option.type === "password" ? "password" : option.type === "int" || option.type === "float" ? "number" : "text";
    if (option.type === "float") input.step = "any";
    if (option.type === "int") input.step = "1";
    if (option.min !== undefined) input.min = option.min;
    if (option.defaultDisplay) {
      input.placeholder = `Default: ${option.defaultDisplay}`;
    } else if (option.placeholder) {
      input.placeholder = option.placeholder;
    }
  }

  input.value = value || "";
  input.autocomplete = "off";
  input.addEventListener("input", () => {
    state.options[option.key] = input.value;
    renderOverview();
    updateCommandPreview();
  });

  label.append(text, input);
  if (option.defaultDisplay) {
    const note = document.createElement("em");
    note.className = "field-default";
    note.textContent = `Default: ${option.defaultDisplay}`;
    label.appendChild(note);
  }
  return label;
}

function createOptionGrid(options) {
  const grid = document.createElement("div");
  grid.className = "option-grid";
  for (const option of options) {
    grid.appendChild(renderOptionField(option));
  }
  return grid;
}

function renderOptionGroups() {
  const root = $("#option-groups");
  root.innerHTML = "";
  const groups = groupOptions(state.schema);
  for (const [name, options] of groups.entries()) {
    const details = document.createElement("details");
    details.className = "option-section";
    const summary = document.createElement("summary");
    const title = document.createElement("h3");
    title.textContent = name;
    const count = document.createElement("span");
    count.className = "muted";
    count.textContent = `${options.length} flags`;
    summary.append(title, count);
    const subgroups = new Map();
    for (const option of options) {
      const subgroup = option.subgroup || "";
      if (!subgroups.has(subgroup)) subgroups.set(subgroup, []);
      subgroups.get(subgroup).push(option);
    }
    details.appendChild(summary);
    if (subgroups.size === 1 && subgroups.has("")) {
      details.appendChild(createOptionGrid(options));
    } else {
      const subgroupRoot = document.createElement("div");
      subgroupRoot.className = "option-subsections";
      for (const [subgroupName, subgroupOptions] of subgroups.entries()) {
        const subgroupDetails = document.createElement("details");
        subgroupDetails.className = "option-subsection";
        const subgroupSummary = document.createElement("summary");
        const subgroupTitle = document.createElement("h4");
        subgroupTitle.textContent = subgroupName || name;
        const subgroupCount = document.createElement("span");
        subgroupCount.className = "muted";
        subgroupCount.textContent = `${subgroupOptions.length} flags`;
        subgroupSummary.append(subgroupTitle, subgroupCount);
        subgroupDetails.append(subgroupSummary, createOptionGrid(subgroupOptions));
        subgroupRoot.appendChild(subgroupDetails);
      }
      details.appendChild(subgroupRoot);
    }
    root.appendChild(details);
  }
}

function payloadFromForm() {
  return {
    data: $("#input-file").value,
    options: state.options
  };
}

const updateCommandPreview = debounce(async () => {
  const preview = $("#command-preview");
  renderOverview();
  if (!$("#input-file").value) {
    preview.textContent = "Select an input file.";
    return;
  }
  try {
    const data = await api("/api/command", {
      method: "POST",
      body: JSON.stringify(payloadFromForm())
    });
    preview.textContent = data.command;
  } catch (error) {
    preview.textContent = error.message;
  }
}, 140);

function renderResultSelectors() {
  const resultSelect = $("#result-select");
  const modelSelect = $("#model-select");
  const results = resultsForSelectedInput();
  resultSelect.innerHTML = "";
  modelSelect.innerHTML = "";

  if (!results.length) {
    state.selectedResult = null;
    state.selectedModelIndex = null;
    resultSelect.appendChild(new Option(selectedInputPath() ? "No results for input" : "No input selected", ""));
    modelSelect.appendChild(new Option("No models", ""));
    resultSelect.title = "";
    modelSelect.title = "";
    return;
  }

  if (!state.selectedResult || !results.some((result) => result.path === state.selectedResult)) {
    state.selectedResult = results[0].path;
  }
  for (const result of results) {
    const option = new Option(result.name, result.path);
    option.title = result.path;
    resultSelect.appendChild(option);
  }
  resultSelect.value = state.selectedResult;
  resultSelect.title = state.selectedResult || "";

  const result = currentResult();
  const model = currentModel(result);
  for (const item of result.models || []) {
    const option = new Option(modelLabel(item), String(item.index));
    option.title = item.structurePath || item.confidencePath || modelLabel(item);
    modelSelect.appendChild(option);
  }
  if (model) {
    state.selectedModelIndex = model.index;
    modelSelect.value = String(model.index);
    modelSelect.title = model.structurePath || model.confidencePath || modelLabel(model);
  } else {
    modelSelect.title = "";
  }
}

function renderResults() {
  renderResultSelectors();
  renderResultCards();
  renderModelTable();
  renderSelectedStructure();
  renderOverview();
}

function renderResultCards() {
  const root = $("#results-list");
  const results = resultsForSelectedInput();
  root.innerHTML = "";
  if (!results.length) {
    root.innerHTML = `<div class="result-item"><div class="muted">${selectedInputPath() ? "No result folder found for the selected input." : "Select an input file to show matching results."}</div></div>`;
    return;
  }

  for (const result of results) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = `result-item${state.selectedResult === result.path ? " active" : ""}`;
    const best = result.bestModel;
    item.innerHTML = `
      <div class="result-top">
        <div>
          <div class="result-name">${escapeHtml(result.name)}</div>
          <div class="muted">${result.structures} structures - ${result.confidenceFiles} confidence files</div>
        </div>
        <span class="badge">${best ? `best ${escapeHtml(modelLabel(best))}` : "waiting"}</span>
      </div>
      <div class="metric-grid">
        ${metric("confidence", best && best.confidenceScore)}
        ${metric("pTM", best && best.ptm)}
        ${metric("pLDDT", best && best.complexPlddt)}
      </div>
    `;
    item.addEventListener("click", () => {
      state.selectedResult = result.path;
      state.selectedModelIndex = null;
      renderResults();
    });
    root.appendChild(item);
  }
}

function renderModelTable() {
  const body = $("#model-table");
  const result = currentResult();
  const model = currentModel(result);
  body.innerHTML = "";

  if (!result || !result.models || !result.models.length) {
    body.innerHTML = `<tr><td colspan="5">No confidence files found.</td></tr>`;
    $("#selected-model-pill").textContent = "None";
    $("#selected-model-meta").textContent = "No structure";
    setFileLink("#structure-file-link", null);
    setFileLink("#confidence-file-link", null);
    return;
  }

  for (const item of result.models) {
    const row = document.createElement("tr");
    if (model && String(model.index) === String(item.index)) row.className = "active";
    row.innerHTML = `
      <td><button class="model-row-button" type="button">${escapeHtml(modelLabel(item))}</button></td>
      <td>${scoreCell(item.confidenceScore)}</td>
      <td>${scoreCell(item.ptm)}</td>
      <td>${scoreCell(item.complexPlddt)}</td>
      <td>${formatNumber(item.complexPde)}</td>
    `;
    row.querySelector("button").addEventListener("click", () => {
      state.selectedModelIndex = item.index;
      renderResults();
    });
    body.appendChild(row);
  }

  $("#selected-model-pill").textContent = modelLabel(model);
  $("#selected-model-meta").textContent = model && model.structurePath
    ? `confidence ${formatNumber(model.confidenceScore)}`
    : "No structure";
  setFileLink("#structure-file-link", model && model.structurePath);
  setFileLink("#confidence-file-link", model && model.confidencePath);
}

async function renderSelectedStructure() {
  const result = currentResult();
  const model = currentModel(result);
  $("#selected-input-pill").textContent = $("#input-file").value ? basename($("#input-file").value) : "None";
  $("#selected-input-meta").textContent = $("#input-file").value ? "Ready" : "Waiting";

  if (!result || !model || !model.structurePath) {
    clearViewer("No PDB structure selected.");
    return;
  }

  try {
    const response = await fetch(`/api/file?path=${encodeURIComponent(model.structurePath)}`);
    if (!response.ok) throw new Error("Could not load structure.");
    const text = await response.text();
    draw3DStructure(text, model.structurePath);
  } catch (error) {
    clearViewer(error.message);
  }
}

function clearViewer(message) {
  const element = $("#structure-viewer");
  const empty = $("#viewer-empty");
  updateConfidenceLegend();
  element.innerHTML = "";
  state.viewer = null;
  state.currentStructureText = null;
  state.currentStructurePath = null;
  empty.textContent = message;
  empty.hidden = false;
}

function chainColor(atom) {
  const palette = [0x63c7f8, 0x2dd4bf, 0xf0b84b, 0xef725f, 0x98cf5f, 0xf37d98, 0xc6b7ff];
  const chain = String(atom.chain || atom.chainID || "A");
  const code = chain.split("").reduce((total, char) => total + char.charCodeAt(0), 0);
  return palette[code % palette.length];
}

function confidenceColor(atom) {
  const value = Number(atom.b || atom.bfactor || atom.tempFactor || 0);
  if (value >= 90) return 0x2dd4bf;
  if (value >= 70) return 0x98cf5f;
  if (value >= 50) return 0xf0b84b;
  return 0xef725f;
}

function colorStyle(kind) {
  const mode = $("#color-mode-select")?.value || "spectrum";
  if (mode === "chain") return { colorfunc: chainColor };
  if (mode === "confidence") return { colorfunc: confidenceColor };
  if (kind === "cartoon") return { color: "spectrum" };
  if (kind === "stick") return { colorscheme: "cyanCarbon" };
  return { color: 0x63c7f8 };
}

function updateConfidenceLegend() {
  const legend = $("#confidence-legend");
  if (!legend) return;
  legend.hidden = ($("#color-mode-select")?.value || "spectrum") !== "confidence";
}

function applyViewerStyle(resetView = false) {
  updateConfidenceLegend();
  const viewer = state.viewer;
  if (!viewer) return;
  const representation = $("#representation-select")?.value || "cartoon";
  const cartoon = { ...colorStyle("cartoon"), style: "oval", thickness: 0.28 };
  const stick = { ...colorStyle("stick"), radius: 0.15 };
  const line = { ...colorStyle("line"), linewidth: 1.2 };

  if (representation === "stick") {
    viewer.setStyle({}, { stick });
  } else if (representation === "line") {
    viewer.setStyle({}, { line });
  } else if (representation === "cartoon-stick") {
    viewer.setStyle({}, { cartoon });
    viewer.setStyle({ hetflag: true }, { stick });
  } else {
    viewer.setStyle({}, { cartoon });
    viewer.setStyle({ hetflag: true }, { stick });
  }

  if (resetView) viewer.zoomTo();
  viewer.render();
}

function draw3DStructure(text, structurePath) {
  const element = $("#structure-viewer");
  const empty = $("#viewer-empty");
  const mol3d = window.$3Dmol || window["3Dmol"];
  if (!mol3d || !mol3d.createViewer) {
    clearViewer("3Dmol viewer did not load.");
    return;
  }

  element.innerHTML = "";
  empty.hidden = true;
  const viewer = mol3d.createViewer(element, {
    backgroundColor: "#070a11",
    antialias: true
  });
  state.viewer = viewer;
  state.currentStructureText = text;
  state.currentStructurePath = structurePath;
  const format = structurePath.toLowerCase().endsWith(".pdb") ? "pdb" : "cif";
  viewer.addModel(text, format);
  applyViewerStyle(true);
}

function renderJobs() {
  const root = $("#jobs-list");
  root.innerHTML = "";
  if (!state.jobs.length) {
    root.innerHTML = `<div class="job-item"><div class="muted">No jobs started in this server session.</div></div>`;
    renderRunBanner(null);
    return;
  }

  if (!state.selectedJob) state.selectedJob = latestJob()?.id || state.jobs[0].id;
  for (const job of state.jobs) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = `job-item${state.selectedJob === job.id ? " active" : ""}`;
    item.innerHTML = `
      <div class="job-top">
        <div>
          <div class="job-name">${escapeHtml(job.data || job.id)}</div>
          <div class="muted">boltz predict</div>
        </div>
        <span class="badge ${escapeHtml(job.status)}">${escapeHtml(job.status)}</span>
      </div>
    `;
    item.addEventListener("click", async () => {
      state.selectedJob = job.id;
      renderJobs();
      await loadJob(job.id);
      connectJobEvents(job.id);
    });
    root.appendChild(item);
  }
  renderRunBanner(latestJob());
}

function renderRunBanner(job) {
  const banner = $("#run-banner");
  banner.className = `run-banner run-banner-${job ? job.status : "idle"}`;
  $("#run-banner-title").textContent = job ? job.status : "Idle";
  if (!job) {
    $("#run-banner-detail").textContent = "No active Boltz run.";
    $("#stop-button").disabled = true;
    return;
  }
  const started = job.startedAt ? `Started ${formatDate(job.startedAt)}` : "Session job";
  const ended = job.endedAt ? ` - ended ${formatDate(job.endedAt)}` : "";
  const failure = job.failureReason ? ` - ${job.failureReason}` : "";
  $("#run-banner-detail").textContent = `${job.data || job.id} - ${started}${ended}${failure}`;
  $("#stop-button").disabled = job.status !== "running";
}

async function loadJob(id) {
  const data = await api(`/api/jobs/${id}`);
  $("#job-log").textContent = (data.job.logs || []).join("\n") || "No log output yet.";
  renderRunBanner(data.job);
}

function connectJobEvents(id) {
  if (state.eventSource) state.eventSource.close();
  const source = new EventSource(`/api/jobs/${id}/events`);
  state.eventSource = source;
  source.addEventListener("log", (event) => {
    const data = JSON.parse(event.data);
    const log = $("#job-log");
    log.textContent += data.text;
    log.scrollTop = log.scrollHeight;
  });
  source.addEventListener("status", async (event) => {
    const data = JSON.parse(event.data);
    const index = state.jobs.findIndex((job) => job.id === data.id);
    if (index >= 0) state.jobs[index] = data;
    renderJobs();
    renderOverview();
    if (["succeeded", "failed", "stopped"].includes(data.status)) {
      source.close();
      await refreshResults();
    }
  });
}

async function refreshAll() {
  const data = await api("/api/state");
  state.schema = data.options;
  state.options = Object.keys(state.options).length ? state.options : defaultsFromSchema(data.options);
  state.inputs = data.inputs;
  state.results = data.results;
  state.jobs = data.jobs;
  state.workspace = data.workspace;

  $("#workspace-pill").textContent = data.workspace;
  $("#workspace-pill").title = "Copy workspace path";
  $("#input-section").open = false;

  renderInputs();
  renderOptionGroups();
  renderResults();
  renderJobs();
  renderOverview();
  updateCommandPreview();
}

async function refreshResults() {
  const data = await api("/api/results");
  state.results = data.results;
  renderResults();
}

function updateSidebarToggle() {
  const shell = $(".studio-shell");
  const button = $("#sidebar-toggle");
  const collapsed = shell.classList.contains("sidebar-collapsed");
  button.title = collapsed ? "Expand sidebar" : "Collapse sidebar";
  button.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
  button.setAttribute("aria-expanded", String(!collapsed));
}

function updateFullscreenButton() {
  const button = $("#viewer-fullscreen-button");
  const panel = $("#structure-panel");
  if (!button || !panel) return;
  button.textContent = document.fullscreenElement === panel ? "Exit full screen" : "Full screen";
}

async function togglePreviewFullscreen() {
  const panel = $("#structure-panel");
  if (!panel || !panel.requestFullscreen) {
    showToast("Full screen is not available in this browser.");
    return;
  }
  try {
    if (document.fullscreenElement === panel) {
      await document.exitFullscreen();
    } else {
      await panel.requestFullscreen();
    }
    updateFullscreenButton();
    setTimeout(() => applyViewerStyle(false), 80);
  } catch (error) {
    showToast(error.message);
  }
}

function bindEvents() {
  $("#sidebar-toggle").addEventListener("click", () => {
    $(".studio-shell").classList.toggle("sidebar-collapsed");
    updateSidebarToggle();
  });
  $("#workspace-pill").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(state.workspace || $("#workspace-pill").textContent);
      showToast("Workspace path copied.");
    } catch (error) {
      showToast(error.message);
    }
  });
  $("#refresh-button").addEventListener("click", () => refreshAll().catch((error) => showToast(error.message)));
  $("#input-file").addEventListener("change", () => {
    state.selectedResult = null;
    state.selectedModelIndex = null;
    renderInputs();
    renderResults();
    updateCommandPreview();
  });
  $("#representation-select").addEventListener("change", () => applyViewerStyle(false));
  $("#color-mode-select").addEventListener("change", () => applyViewerStyle(false));
  $("#reset-view-button").addEventListener("click", () => applyViewerStyle(true));
  $("#viewer-fullscreen-button").addEventListener("click", togglePreviewFullscreen);
  document.addEventListener("fullscreenchange", updateFullscreenButton);
  $("#result-select").addEventListener("change", () => {
    state.selectedResult = $("#result-select").value;
    state.selectedModelIndex = null;
    renderResults();
  });
  $("#model-select").addEventListener("change", () => {
    state.selectedModelIndex = $("#model-select").value;
    renderResults();
  });

  $("#copy-command").addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    await navigator.clipboard.writeText($("#command-preview").textContent);
    showToast("Command copied.");
  });

  $("#run-button").addEventListener("click", async () => {
    try {
      const data = await api("/api/jobs", {
        method: "POST",
        body: JSON.stringify(payloadFromForm())
      });
      state.jobs.unshift(data.job);
      state.selectedJob = data.job.id;
      renderJobs();
      renderOverview();
      $("#job-log").textContent = (data.job.logs || []).join("\n");
      connectJobEvents(data.job.id);
    } catch (error) {
      showToast(error.message);
    }
  });

  $("#stop-button").addEventListener("click", async () => {
    if (!state.selectedJob) return;
    try {
      const data = await api(`/api/jobs/${state.selectedJob}/stop`, { method: "POST", body: "{}" });
      const index = state.jobs.findIndex((job) => job.id === data.job.id);
      if (index >= 0) state.jobs[index] = data.job;
      renderJobs();
    } catch (error) {
      showToast(error.message);
    }
  });

  const saveInputButton = $("#save-input-button");
  if (saveInputButton) {
    saveInputButton.addEventListener("click", async () => {
      try {
        const data = await api("/api/inputs", {
          method: "POST",
          body: JSON.stringify({
            name: $("#new-input-name").value,
            content: $("#input-editor").value
          })
        });
        state.inputs.push(data.input);
        renderInputs();
        $("#input-file").value = data.input.path;
        state.selectedResult = null;
        state.selectedModelIndex = null;
        renderInputs();
        renderResults();
        updateCommandPreview();
        showToast("Input saved.");
      } catch (error) {
        showToast(error.message);
      }
    });
  }

  const newInputName = $("#new-input-name");
  if (newInputName) {
    newInputName.addEventListener("input", () => {
      const name = newInputName.value || "new_prediction.yaml";
      $("#yaml-summary-name").textContent = name;
      $("#yaml-summary-name").title = name;
    });
  }

  for (const tab of document.querySelectorAll(".tab")) {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((item) => item.classList.remove("active"));
      tab.classList.add("active");
      $(`#${tab.dataset.tab}-panel`).classList.add("active");
    });
  }
}

bindEvents();
updateSidebarToggle();
updateFullscreenButton();
updateConfidenceLegend();
refreshAll().catch((error) => showToast(error.message));
