const $ = (selector) => document.querySelector(selector);

let nextId = 1;

const builderState = {
  polymers: [],
  contacts: []
};

const DEFAULT_LIGAND_SMILES = "N[C@@H](Cc1ccc(O)cc1)C(=O)O";

const YAML_TASK_PRESETS = {
  structure: {
    filename: "structure_prediction.yaml",
    polymers: [{ type: "protein", ids: "A", sequence: "M", msaMode: "auto" }]
  },
  complex: {
    filename: "multimer_prediction.yaml",
    polymers: [
      { type: "protein", ids: "A", sequence: "M", msaMode: "auto" },
      { type: "protein", ids: "B", sequence: "M", msaMode: "auto" }
    ]
  },
  ligand: {
    filename: "protein_ligand.yaml",
    polymers: [{ type: "protein", ids: "A", sequence: "M", msaMode: "auto" }],
    ligand: { enabled: true, ids: "B", source: "smiles", value: DEFAULT_LIGAND_SMILES }
  },
  affinity: {
    filename: "affinity_prediction.yaml",
    polymers: [{ type: "protein", ids: "A", sequence: "M", msaMode: "auto" }],
    ligand: { enabled: true, ids: "B", source: "smiles", value: DEFAULT_LIGAND_SMILES },
    affinity: { enabled: true, binder: "B" }
  },
  pocket: {
    filename: "pocket_prediction.yaml",
    polymers: [{ type: "protein", ids: "A", sequence: "M", msaMode: "auto" }],
    ligand: { enabled: true, ids: "B", source: "ccd", value: "ATP" },
    pocket: { enabled: true, binder: "B", distance: "6", force: false, contacts: "A:45\nA:68" }
  },
  contacts: {
    filename: "contact_constraints.yaml",
    polymers: [
      { type: "protein", ids: "A", sequence: "M", msaMode: "auto" },
      { type: "protein", ids: "B", sequence: "M", msaMode: "auto" }
    ],
    contacts: [
      { token1: "A:45", token2: "B:67", distance: "6", force: false }
    ]
  },
  template: {
    filename: "template_prediction.yaml",
    polymers: [{ type: "protein", ids: "A", sequence: "M", msaMode: "auto" }],
    template: { enabled: true, format: "cif", path: "./template.cif", chainIds: "A" }
  }
};

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
  if (!response.ok) throw new Error(data.error || "Request failed.");
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

function createUid(prefix) {
  const uid = `${prefix}-${nextId}`;
  nextId += 1;
  return uid;
}

function chainIdFromIndex(index) {
  let value = Math.max(0, index);
  let id = "";
  do {
    id = String.fromCharCode(65 + (value % 26)) + id;
    value = Math.floor(value / 26) - 1;
  } while (value >= 0);
  return id;
}

function createPolymer(overrides = {}) {
  return {
    uid: createUid("polymer"),
    type: "protein",
    ids: "A",
    sequence: "M",
    msaMode: "auto",
    msaPath: "",
    cyclic: false,
    modifications: "",
    ...overrides
  };
}

function createContact(overrides = {}) {
  return {
    uid: createUid("contact"),
    token1: "A:45",
    token2: "B:67",
    distance: "6",
    force: false,
    ...overrides
  };
}

function setFieldValue(id, value) {
  const element = $(`#${id}`);
  if (!element) return;
  if (element.type === "checkbox") {
    element.checked = Boolean(value);
  } else {
    element.value = value ?? "";
  }
}

function fieldValue(id) {
  const element = $(`#${id}`);
  if (!element) return "";
  return element.type === "checkbox" ? element.checked : String(element.value || "");
}

function setDraftName(name) {
  const value = name || "new_prediction.yaml";
  setFieldValue("new-input-name", value);
  const summary = $("#yaml-summary-name");
  if (summary) {
    summary.textContent = value;
    summary.title = value;
  }
}

function parseIdList(value) {
  return String(value || "")
    .split(/[,\s]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function cleanSequence(value) {
  return String(value || "").replace(/\s+/g, "").toUpperCase();
}

function yamlScalar(value) {
  const text = String(value ?? "").trim();
  if (!text) return "''";
  if (/^[A-Za-z0-9_./:-]+$/.test(text)) return text;
  return `'${text.replaceAll("'", "''")}'`;
}

function yamlIdValue(ids, fallback = "A") {
  const values = ids.length ? ids : [fallback];
  if (values.length === 1) return yamlScalar(values[0]);
  return `[${values.map(yamlScalar).join(", ")}]`;
}

function yamlCcdValue(value) {
  const ccds = parseIdList(value);
  if (ccds.length > 1) return `[${ccds.map(yamlScalar).join(", ")}]`;
  return yamlScalar(ccds[0] || "");
}

function formatNumberForYaml(value, fallback = 6) {
  const number = Number(value);
  const safe = Number.isFinite(number) ? number : fallback;
  return Number.isInteger(safe) ? String(safe) : String(Number(safe.toFixed(3)));
}

function readDistanceValue(value, label, warnings) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    warnings.push(`${label} must be a number; using 6.`);
    return "6";
  }
  if (number < 4 || number > 20) {
    warnings.push(`${label} is usually supported between 4 and 20 Angstrom.`);
  }
  return formatNumberForYaml(number, 6);
}

function parseModificationLines(text, warnings, label) {
  return String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.replace(/^\[|\]$/g, "").split(/[:,\s]+/).filter(Boolean);
      const position = parts.length >= 3 ? parts[1] : parts[0];
      const ccd = parts.length >= 3 ? parts[2] : parts[1];
      if (!/^\d+$/.test(position || "") || !ccd) {
        warnings.push(`${label} modification "${line}" should look like 12:MSE.`);
        return null;
      }
      return { position: Number(position), ccd };
    })
    .filter(Boolean);
}

function parseTokenSpec(value) {
  const parts = String(value || "").replace(/^\[|\]$/g, "").split(/[:,\s]+/).filter(Boolean);
  if (parts.length < 2) return null;
  return { chain: parts[0], token: parts[1] };
}

function yamlToken(token) {
  const residueOrAtom = /^\d+$/.test(token.token) ? token.token : yamlScalar(token.token);
  return `[${yamlScalar(token.chain)}, ${residueOrAtom}]`;
}

function parseAtomSpec(value) {
  const parts = String(value || "").replace(/^\[|\]$/g, "").split(/[:,\s]+/).filter(Boolean);
  if (parts.length < 3 || !/^\d+$/.test(parts[1])) return null;
  return { chain: parts[0], residue: Number(parts[1]), atom: parts[2] };
}

function yamlAtom(atom) {
  return `[${yamlScalar(atom.chain)}, ${atom.residue}, ${yamlScalar(atom.atom)}]`;
}

function appendPolymerYaml(lines, polymer, index, warnings, usedIds) {
  const type = polymer.type || "protein";
  const ids = parseIdList(polymer.ids);
  const sequence = cleanSequence(polymer.sequence);
  const fallbackId = String.fromCharCode(65 + (index % 26));
  const label = `Polymer ${index + 1}`;

  if (!ids.length) warnings.push(`${label} needs at least one chain ID.`);
  if (!sequence) warnings.push(`${label} sequence is empty.`);

  lines.push(`  - ${type}:`);
  lines.push(`      id: ${yamlIdValue(ids, fallbackId)}`);
  lines.push(`      sequence: ${yamlScalar(sequence)}`);
  usedIds.push(...(ids.length ? ids : [fallbackId]));

  if (type === "protein") {
    if (polymer.msaMode === "empty") {
      lines.push("      msa: empty");
    } else if (polymer.msaMode === "custom") {
      if (!String(polymer.msaPath || "").trim()) warnings.push(`${label} custom MSA path is empty.`);
      lines.push(`      msa: ${yamlScalar(polymer.msaPath)}`);
    }
  }

  if (polymer.cyclic) lines.push("      cyclic: true");

  const modifications = parseModificationLines(polymer.modifications, warnings, label);
  if (modifications.length) {
    lines.push("      modifications:");
    for (const mod of modifications) {
      lines.push("        - position: " + mod.position);
      lines.push("          ccd: " + yamlScalar(mod.ccd));
    }
  }
}

function buildYamlFromBuilder() {
  const warnings = [];
  const lines = ["version: 1", "sequences:"];
  const usedIds = [];
  const features = [];
  let entityCount = 0;

  if (!builderState.polymers.length) {
    warnings.push("At least one polymer is required.");
    builderState.polymers.push(createPolymer());
    renderPolymers();
  }

  builderState.polymers.forEach((polymer, index) => {
    appendPolymerYaml(lines, polymer, index, warnings, usedIds);
    entityCount += 1;
  });

  const ligandEnabled = fieldValue("yaml-ligand-enabled");
  const ligandIds = parseIdList(fieldValue("yaml-ligand-id"));
  const ligandSource = fieldValue("yaml-ligand-source") || "smiles";
  const ligandValue = fieldValue("yaml-ligand-value").trim();
  if (ligandEnabled) {
    if (!ligandIds.length) warnings.push("Ligand needs at least one chain ID.");
    if (!ligandValue) warnings.push("Ligand value is empty.");
    lines.push("  - ligand:");
    lines.push(`      id: ${yamlIdValue(ligandIds, "B")}`);
    lines.push(ligandSource === "ccd"
      ? `      ccd: ${yamlCcdValue(ligandValue)}`
      : `      smiles: ${yamlScalar(ligandValue)}`);
    usedIds.push(...(ligandIds.length ? ligandIds : ["B"]));
    entityCount += 1;
    features.push("ligand");
  }

  const constraints = [];
  if (fieldValue("yaml-bond-enabled")) {
    const atom1 = parseAtomSpec(fieldValue("yaml-bond-atom1"));
    const atom2 = parseAtomSpec(fieldValue("yaml-bond-atom2"));
    if (!atom1 || !atom2) {
      warnings.push("Covalent bond atoms should look like A:145:SG.");
    } else {
      constraints.push("  - bond:", `      atom1: ${yamlAtom(atom1)}`, `      atom2: ${yamlAtom(atom2)}`);
      features.push("bond");
    }
  }

  if (fieldValue("yaml-pocket-enabled")) {
    const binder = fieldValue("yaml-pocket-binder").trim() || ligandIds[0] || "B";
    if (!usedIds.includes(binder)) warnings.push(`Pocket binder "${binder}" is not one of the current entity IDs.`);
    const contacts = String(fieldValue("yaml-pocket-contacts") || "")
      .split(/\r?\n/)
      .map((line) => parseTokenSpec(line))
      .filter(Boolean);
    if (!contacts.length) warnings.push("Pocket contacts are empty.");
    constraints.push("  - pocket:");
    constraints.push(`      binder: ${yamlScalar(binder)}`);
    constraints.push(`      contacts: [${contacts.map(yamlToken).join(", ")}]`);
    constraints.push(`      max_distance: ${readDistanceValue(fieldValue("yaml-pocket-distance"), "Pocket max distance", warnings)}`);
    constraints.push(`      force: ${fieldValue("yaml-pocket-force") ? "true" : "false"}`);
    features.push("pocket");
  }

  builderState.contacts.forEach((contact, index) => {
    const token1 = parseTokenSpec(contact.token1);
    const token2 = parseTokenSpec(contact.token2);
    const label = `Contact ${index + 1}`;
    if (!token1 || !token2) {
      warnings.push(`${label} tokens should look like A:45 or B:C1.`);
      return;
    }
    constraints.push("  - contact:");
    constraints.push(`      token1: ${yamlToken(token1)}`);
    constraints.push(`      token2: ${yamlToken(token2)}`);
    constraints.push(`      max_distance: ${readDistanceValue(contact.distance, `${label} max distance`, warnings)}`);
    constraints.push(`      force: ${contact.force ? "true" : "false"}`);
    features.push(`contact ${index + 1}`);
  });

  if (constraints.length) {
    lines.push("constraints:");
    lines.push(...constraints);
  }

  if (fieldValue("yaml-template-enabled")) {
    const templatePath = fieldValue("yaml-template-path").trim();
    const templateFormat = fieldValue("yaml-template-format") || "cif";
    const chainIds = parseIdList(fieldValue("yaml-template-chain-ids"));
    const templateIds = parseIdList(fieldValue("yaml-template-template-ids"));
    if (!templatePath) warnings.push("Template path is empty.");
    if (!chainIds.length) warnings.push("Template target chain IDs are empty.");

    lines.push("templates:");
    lines.push(`  - ${templateFormat}: ${yamlScalar(templatePath || `./template.${templateFormat}`)}`);
    if (chainIds.length) lines.push(`    chain_id: ${yamlIdValue(chainIds, "A")}`);
    if (templateIds.length) lines.push(`    template_id: ${yamlIdValue(templateIds, "A1")}`);
    if (fieldValue("yaml-template-force")) {
      lines.push("    force: true");
      lines.push(`    threshold: ${formatNumberForYaml(fieldValue("yaml-template-threshold"), 2)}`);
    }
    features.push("template");
  }

  if (fieldValue("yaml-affinity-enabled")) {
    const binder = fieldValue("yaml-affinity-binder").trim() || ligandIds[0] || "B";
    if (!ligandEnabled) warnings.push("Affinity requires a ligand entity.");
    if (ligandIds.length > 1) warnings.push("Affinity binder must be a single ligand chain, not multiple copies.");
    if (ligandSource === "ccd" && parseIdList(ligandValue).length > 1) warnings.push("Affinity does not support multi-residue CCD ligands.");
    if (!usedIds.includes(binder)) warnings.push(`Affinity binder "${binder}" is not one of the current entity IDs.`);
    lines.push("properties:");
    lines.push("  - affinity:");
    lines.push(`      binder: ${yamlScalar(binder)}`);
    features.push("affinity");
  }

  const yaml = `${lines.join("\n")}\n`;
  const shortFeatures = features.slice(0, 4).join(", ");
  const extra = features.length > 4 ? ` +${features.length - 4} more` : "";
  const summary = `${entityCount} ${entityCount === 1 ? "entity" : "entities"}${features.length ? ` - ${shortFeatures}${extra}` : ""}`;
  return { yaml, warnings, summary };
}

function renderYamlBuilderStatus(result) {
  const root = $("#yaml-builder-status");
  if (!root) return;
  const hasWarnings = result.warnings.length > 0;
  const warnings = result.warnings.slice(0, 5)
    .map((warning) => `<li>${escapeHtml(warning)}</li>`)
    .join("");
  root.innerHTML = `
    <div class="builder-status-row">
      <span class="builder-status-dot ${hasWarnings ? "warn" : "ok"}"></span>
      <div>
        <strong>${hasWarnings ? `${result.warnings.length} check${result.warnings.length === 1 ? "" : "s"}` : "Ready"}</strong>
        <em>${escapeHtml(result.summary)}</em>
      </div>
    </div>
    ${warnings ? `<ul>${warnings}</ul>` : ""}
  `;
}

function polymerCard(polymer, index) {
  const proteinHidden = polymer.type !== "protein" ? " hidden" : "";
  const customHidden = polymer.type !== "protein" || polymer.msaMode !== "custom" ? " hidden" : "";
  const canRemove = builderState.polymers.length > 1;
  return `
    <article class="repeat-card polymer-card" data-uid="${polymer.uid}">
      <div class="repeat-card-heading">
        <h4>Polymer ${index + 1}</h4>
        <button class="ghost-button repeat-remove-button" data-action="remove-polymer" type="button" ${canRemove ? "" : "disabled"}>Remove</button>
      </div>
      <div class="builder-grid repeat-grid">
        <label class="field">
          <span>Type</span>
          <select data-polymer-field="type">
            <option value="protein"${polymer.type === "protein" ? " selected" : ""}>Protein</option>
            <option value="dna"${polymer.type === "dna" ? " selected" : ""}>DNA</option>
            <option value="rna"${polymer.type === "rna" ? " selected" : ""}>RNA</option>
          </select>
        </label>
        <label class="field">
          <span>Chain ID(s)</span>
          <input data-polymer-field="ids" type="text" value="${escapeHtml(polymer.ids)}" placeholder="A or A, B">
        </label>
        <label class="field builder-span">
          <span>Sequence</span>
          <textarea class="sequence-input" data-polymer-field="sequence" spellcheck="false">${escapeHtml(polymer.sequence)}</textarea>
        </label>
        <label class="field protein-dynamic-field"${proteinHidden}>
          <span>MSA mode</span>
          <select data-polymer-field="msaMode">
            <option value="auto"${polymer.msaMode === "auto" ? " selected" : ""}>MSA server</option>
            <option value="empty"${polymer.msaMode === "empty" ? " selected" : ""}>Single sequence</option>
            <option value="custom"${polymer.msaMode === "custom" ? " selected" : ""}>Custom MSA</option>
          </select>
        </label>
        <label class="field msa-path-dynamic-field"${customHidden}>
          <span>MSA path</span>
          <input data-polymer-field="msaPath" type="text" value="${escapeHtml(polymer.msaPath)}" placeholder="./examples/msa/seq1.a3m">
        </label>
        <label class="toggle-field">
          <span>Cyclic polymer</span>
          <span class="switch">
            <input data-polymer-field="cyclic" type="checkbox"${polymer.cyclic ? " checked" : ""}>
            <span class="slider"></span>
          </span>
        </label>
        <label class="field builder-span">
          <span>Modifications</span>
          <textarea class="mini-textarea" data-polymer-field="modifications" spellcheck="false" placeholder="12:MSE">${escapeHtml(polymer.modifications)}</textarea>
        </label>
      </div>
    </article>
  `;
}

function renderPolymers() {
  const root = $("#polymer-list");
  root.innerHTML = builderState.polymers.map(polymerCard).join("");
}

function contactCard(contact, index) {
  return `
    <article class="repeat-card contact-card" data-uid="${contact.uid}">
      <div class="repeat-card-heading">
        <h4>Contact ${index + 1}</h4>
        <button class="ghost-button repeat-remove-button" data-action="remove-contact" type="button">Remove</button>
      </div>
      <div class="builder-grid repeat-grid contact-repeat-grid">
        <label class="field">
          <span>Token 1</span>
          <input data-contact-field="token1" type="text" value="${escapeHtml(contact.token1)}" placeholder="A:45">
        </label>
        <label class="field">
          <span>Token 2</span>
          <input data-contact-field="token2" type="text" value="${escapeHtml(contact.token2)}" placeholder="B:C1">
        </label>
        <label class="field">
          <span>Max distance</span>
          <input data-contact-field="distance" type="number" min="4" max="20" step="0.1" value="${escapeHtml(contact.distance)}">
        </label>
        <label class="toggle-field">
          <span>Force contact</span>
          <span class="switch">
            <input data-contact-field="force" type="checkbox"${contact.force ? " checked" : ""}>
            <span class="slider"></span>
          </span>
        </label>
      </div>
    </article>
  `;
}

function renderContacts() {
  const root = $("#contact-list");
  if (!builderState.contacts.length) {
    root.innerHTML = `<div class="repeat-empty">No contact constraints added.</div>`;
    return;
  }
  root.innerHTML = builderState.contacts.map(contactCard).join("");
}

function updateYamlBuilderVisibility() {
  const ligandEnabled = fieldValue("yaml-ligand-enabled");
  document.querySelectorAll(".ligand-fields").forEach((element) => {
    element.hidden = !ligandEnabled;
  });

  const ligandSource = fieldValue("yaml-ligand-source") || "smiles";
  const ligandLabel = $("#yaml-ligand-value-label");
  const ligandValue = $("#yaml-ligand-value");
  if (ligandLabel) ligandLabel.textContent = ligandSource === "ccd" ? "CCD code(s)" : "SMILES";
  if (ligandValue) ligandValue.placeholder = ligandSource === "ccd" ? "ATP or SAH" : "CC1=CC=CC=C1";

  const thresholdField = $("#yaml-template-threshold")?.closest(".field");
  if (thresholdField) thresholdField.hidden = !fieldValue("yaml-template-force");
}

function generateYamlFromBuilder({ silent = false } = {}) {
  updateYamlBuilderVisibility();
  const result = buildYamlFromBuilder();
  $("#input-editor").value = result.yaml;
  renderYamlBuilderStatus(result);
  if (!silent) showToast(result.warnings.length ? "YAML generated with checks." : "YAML generated.");
  return result;
}

const syncYamlFromBuilder = debounce(() => generateYamlFromBuilder({ silent: true }), 90);

function applyYamlPreset(profileName, { silent = true } = {}) {
  const preset = YAML_TASK_PRESETS[profileName] || YAML_TASK_PRESETS.structure;
  setDraftName(preset.filename);

  builderState.polymers = (preset.polymers || YAML_TASK_PRESETS.structure.polymers).map((polymer) => createPolymer(polymer));
  builderState.contacts = (preset.contacts || []).map((contact) => createContact(contact));
  renderPolymers();
  renderContacts();

  setFieldValue("yaml-ligand-enabled", Boolean(preset.ligand?.enabled));
  setFieldValue("yaml-ligand-id", preset.ligand?.ids || "B");
  setFieldValue("yaml-ligand-source", preset.ligand?.source || "smiles");
  setFieldValue("yaml-ligand-value", preset.ligand?.value || DEFAULT_LIGAND_SMILES);

  setFieldValue("yaml-affinity-enabled", Boolean(preset.affinity?.enabled));
  setFieldValue("yaml-affinity-binder", preset.affinity?.binder || "B");

  setFieldValue("yaml-pocket-enabled", Boolean(preset.pocket?.enabled));
  setFieldValue("yaml-pocket-binder", preset.pocket?.binder || "B");
  setFieldValue("yaml-pocket-distance", preset.pocket?.distance || "6");
  setFieldValue("yaml-pocket-force", Boolean(preset.pocket?.force));
  setFieldValue("yaml-pocket-contacts", preset.pocket?.contacts || "");

  setFieldValue("yaml-bond-enabled", Boolean(preset.bond?.enabled));
  setFieldValue("yaml-bond-atom1", preset.bond?.atom1 || "A:145:SG");
  setFieldValue("yaml-bond-atom2", preset.bond?.atom2 || "B:1:C1");

  setFieldValue("yaml-template-enabled", Boolean(preset.template?.enabled));
  setFieldValue("yaml-template-format", preset.template?.format || "cif");
  setFieldValue("yaml-template-path", preset.template?.path || "./template.cif");
  setFieldValue("yaml-template-chain-ids", preset.template?.chainIds || "A");
  setFieldValue("yaml-template-template-ids", preset.template?.templateIds || "");
  setFieldValue("yaml-template-force", Boolean(preset.template?.force));
  setFieldValue("yaml-template-threshold", preset.template?.threshold || "2");

  generateYamlFromBuilder({ silent });
}

function updatePolymerFromElement(element) {
  const card = element.closest(".polymer-card");
  if (!card) return;
  const polymer = builderState.polymers.find((item) => item.uid === card.dataset.uid);
  if (!polymer) return;
  const field = element.dataset.polymerField;
  polymer[field] = element.type === "checkbox" ? element.checked : element.value;
  if (field === "type" || field === "msaMode") renderPolymers();
  syncYamlFromBuilder();
}

function updateContactFromElement(element) {
  const card = element.closest(".contact-card");
  if (!card) return;
  const contact = builderState.contacts.find((item) => item.uid === card.dataset.uid);
  if (!contact) return;
  const field = element.dataset.contactField;
  contact[field] = element.type === "checkbox" ? element.checked : element.value;
  syncYamlFromBuilder();
}

function bindRepeatLists() {
  $("#add-polymer-button").addEventListener("click", () => {
    builderState.polymers.push(createPolymer({ ids: chainIdFromIndex(builderState.polymers.length) }));
    renderPolymers();
    generateYamlFromBuilder({ silent: true });
  });

  $("#add-contact-button").addEventListener("click", () => {
    builderState.contacts.push(createContact());
    renderContacts();
    generateYamlFromBuilder({ silent: true });
  });

  $("#polymer-list").addEventListener("input", (event) => {
    if (event.target.dataset.polymerField) updatePolymerFromElement(event.target);
  });
  $("#polymer-list").addEventListener("change", (event) => {
    if (event.target.dataset.polymerField) updatePolymerFromElement(event.target);
  });
  $("#polymer-list").addEventListener("click", (event) => {
    if (event.target.dataset.action !== "remove-polymer") return;
    const card = event.target.closest(".polymer-card");
    if (!card || builderState.polymers.length <= 1) return;
    builderState.polymers = builderState.polymers.filter((item) => item.uid !== card.dataset.uid);
    renderPolymers();
    generateYamlFromBuilder({ silent: true });
  });

  $("#contact-list").addEventListener("input", (event) => {
    if (event.target.dataset.contactField) updateContactFromElement(event.target);
  });
  $("#contact-list").addEventListener("change", (event) => {
    if (event.target.dataset.contactField) updateContactFromElement(event.target);
  });
  $("#contact-list").addEventListener("click", (event) => {
    if (event.target.dataset.action !== "remove-contact") return;
    const card = event.target.closest(".contact-card");
    if (!card) return;
    builderState.contacts = builderState.contacts.filter((item) => item.uid !== card.dataset.uid);
    renderContacts();
    generateYamlFromBuilder({ silent: true });
  });
}

async function saveInput() {
  try {
    const data = await api("/api/inputs", {
      method: "POST",
      body: JSON.stringify({
        name: $("#new-input-name").value,
        content: $("#input-editor").value
      })
    });
    const savedStatus = $("#saved-input-status");
    if (savedStatus) savedStatus.textContent = `Saved: ${data.input.path}`;
    showToast("Input saved.");
  } catch (error) {
    showToast(error.message);
  }
}

async function loadWorkspace() {
  try {
    const data = await api("/api/state");
    const workspace = $("#workspace-pill");
    if (workspace) {
      workspace.textContent = data.workspace;
      workspace.title = "Copy workspace path";
      workspace.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(data.workspace);
          showToast("Workspace path copied.");
        } catch (error) {
          showToast(error.message);
        }
      });
    }
  } catch (error) {
    showToast(error.message);
  }
}

function bindBuilderPage() {
  const profile = $("#yaml-profile");
  const initialProfile = new URLSearchParams(window.location.search).get("profile");
  if (initialProfile && YAML_TASK_PRESETS[initialProfile]) profile.value = initialProfile;

  bindRepeatLists();
  profile.addEventListener("change", () => applyYamlPreset(profile.value, { silent: true }));
  document.querySelectorAll("[data-yaml-control]").forEach((element) => {
    if (element.id === "yaml-profile") return;
    const eventName = element.tagName === "SELECT" || element.type === "checkbox" ? "change" : "input";
    element.addEventListener(eventName, () => {
      updateYamlBuilderVisibility();
      syncYamlFromBuilder();
    });
  });

  $("#generate-yaml-button").addEventListener("click", () => generateYamlFromBuilder());
  $("#reset-yaml-builder").addEventListener("click", () => applyYamlPreset(profile.value, { silent: false }));
  $("#save-input-button").addEventListener("click", saveInput);
  $("#new-input-name").addEventListener("input", () => {
    const name = $("#new-input-name").value || "new_prediction.yaml";
    $("#yaml-summary-name").textContent = name;
    $("#yaml-summary-name").title = name;
  });

  applyYamlPreset(profile.value, { silent: true });
}

bindBuilderPage();
loadWorkspace();
