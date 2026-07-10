const $ = (selector) => document.querySelector(selector);

let nextId = 1;

const builderState = {
  polymers: [],
  ligands: [],
  contacts: [],
  atomContacts: [],
  bonds: []
};

const DEFAULT_LIGAND_SMILES = "N[C@@H](Cc1ccc(O)cc1)C(=O)O";
const POLYMER_TYPES = new Set(["protein", "dna", "rna"]);

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
    ligands: [{ ids: "B", source: "smiles", value: DEFAULT_LIGAND_SMILES }]
  },
  affinity: {
    filename: "affinity_prediction.yaml",
    polymers: [{ type: "protein", ids: "A", sequence: "M", msaMode: "auto" }],
    ligands: [{ ids: "B", source: "smiles", value: DEFAULT_LIGAND_SMILES }],
    affinity: { enabled: true, binder: "B" }
  },
  pocket: {
    filename: "pocket_prediction.yaml",
    polymers: [{ type: "protein", ids: "A", sequence: "M", msaMode: "auto" }],
    ligands: [{ ids: "B", source: "ccd", value: "ATP" }],
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

function createLigand(overrides = {}) {
  const { enabled, ...values } = overrides;
  return {
    uid: createUid("ligand"),
    ids: "B",
    source: "smiles",
    value: DEFAULT_LIGAND_SMILES,
    ...values
  };
}

function presetLigands(preset) {
  if (Array.isArray(preset.ligands)) return preset.ligands;
  if (preset.ligand?.enabled) return [preset.ligand];
  return [];
}

function presetBonds(preset) {
  if (Array.isArray(preset.bonds)) return preset.bonds;
  if (preset.bond?.enabled) return [preset.bond];
  return [];
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

function createAtomContact(overrides = {}) {
  return {
    uid: createUid("atom-contact"),
    atom1: "A:145:NZ",
    atom2: "B:37:OD1",
    distance: "3.5",
    force: true,
    ...overrides
  };
}

function createBond(overrides = {}) {
  const { enabled, ...values } = overrides;
  return {
    uid: createUid("bond"),
    atom1: "A:145:SG",
    atom2: "B:1:C1",
    ...values
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

function readAtomContactDistanceValue(value, label, warnings) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    warnings.push(`${label} must be a finite number; atom_contact card was not emitted.`);
    return null;
  }
  if (number < 2 || number > 20) {
    warnings.push(`${label} must be between 2.0 and 20.0 Angstrom; atom_contact card was not emitted.`);
    return null;
  }
  return formatNumberForYaml(number, 3.5);
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
  if (parts.length !== 2) return null;
  return { chain: parts[0], token: parts[1] };
}

function splitTopLevelComma(value) {
  const text = String(value || "");
  const items = [];
  let current = "";
  let depth = 0;
  let quote = "";

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quote) {
      current += char;
      if (char === quote) quote = "";
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      current += char;
      continue;
    }
    if (char === "[") depth += 1;
    if (char === "]") depth -= 1;
    if (char === "," && depth === 0) {
      items.push(current.trim());
      current = "";
      continue;
    }
    current += char;
  }

  if (current.trim()) items.push(current.trim());
  return items;
}

function stripYamlQuotes(value) {
  const text = String(value ?? "").trim();
  if ((text.startsWith("'") && text.endsWith("'")) || (text.startsWith('"') && text.endsWith('"'))) {
    const inner = text.slice(1, -1);
    return text.startsWith("'") ? inner.replaceAll("''", "'") : inner.replaceAll('\\"', '"');
  }
  return text;
}

function parseInlineYamlValue(value) {
  const text = stripYamlQuotes(value);
  if (text.startsWith("[") && text.endsWith("]")) {
    return splitTopLevelComma(text.slice(1, -1)).map(parseInlineYamlValue);
  }
  if (/^(true|false)$/i.test(text)) return text.toLowerCase() === "true";
  return text;
}

function yamlValueAsList(value) {
  const parsed = parseInlineYamlValue(value);
  return Array.isArray(parsed) ? parsed.map((item) => Array.isArray(item) ? item.join(":") : String(item)) : [String(parsed)];
}

function yamlValueAsText(value) {
  return yamlValueAsList(value).filter(Boolean).join(", ");
}

function yamlTokenAsField(value) {
  const parsed = parseInlineYamlValue(value);
  if (Array.isArray(parsed) && parsed.length >= 2) return `${parsed[0]}:${parsed[1]}`;
  return stripYamlQuotes(value);
}

function yamlAtomAsField(value) {
  const parsed = parseInlineYamlValue(value);
  if (Array.isArray(parsed) && parsed.length >= 3) return `${parsed[0]}:${parsed[1]}:${parsed[2]}`;
  return stripYamlQuotes(value);
}

function yamlContactListAsField(value) {
  const parsed = parseInlineYamlValue(value);
  if (!Array.isArray(parsed)) return stripYamlQuotes(value);
  return parsed
    .filter((item) => Array.isArray(item) && item.length >= 2)
    .map((item) => `${item[0]}:${item[1]}`)
    .join("\n");
}

function boolFromYamlValue(value) {
  return parseInlineYamlValue(value) === true;
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

  const ligandRecords = [];
  builderState.ligands.forEach((ligand, index) => {
    const fallbackId = chainIdFromIndex(builderState.polymers.length + index);
    const ligandIds = parseIdList(ligand.ids);
    const resolvedIds = ligandIds.length ? ligandIds : [fallbackId || "B"];
    const ligandSource = ligand.source === "ccd" ? "ccd" : "smiles";
    const ligandValue = String(ligand.value || "").trim();
    const label = `Ligand ${index + 1}`;
    if (!ligandIds.length) warnings.push(`${label} needs at least one chain ID.`);
    if (!ligandValue) warnings.push(`${label} value is empty.`);
    const duplicateIds = resolvedIds.filter((id) => usedIds.includes(id));
    if (duplicateIds.length) warnings.push(`${label} chain ID "${duplicateIds[0]}" is already used.`);
    lines.push("  - ligand:");
    lines.push(`      id: ${yamlIdValue(resolvedIds, fallbackId || "B")}`);
    lines.push(ligandSource === "ccd"
      ? `      ccd: ${yamlCcdValue(ligandValue)}`
      : `      smiles: ${yamlScalar(ligandValue)}`);
    usedIds.push(...resolvedIds);
    ligandRecords.push({ ids: resolvedIds, source: ligandSource, value: ligandValue, label });
    entityCount += 1;
    features.push(builderState.ligands.length === 1 ? "ligand" : `ligand ${index + 1}`);
  });
  const ligandIds = ligandRecords.flatMap((ligand) => ligand.ids);
  const firstLigandId = ligandIds[0] || "";

  const constraints = [];

  if (fieldValue("yaml-pocket-enabled")) {
    const binder = fieldValue("yaml-pocket-binder").trim() || firstLigandId || "B";
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

  if (builderState.atomContacts.length) {
    warnings.push("atom_contact constraints require force: true and prediction with --use_potentials.");
  }
  builderState.atomContacts.forEach((atomContact, index) => {
    const atom1 = parseAtomSpec(atomContact.atom1);
    const atom2 = parseAtomSpec(atomContact.atom2);
    const label = `Atom contact ${index + 1}`;
    const distance = readAtomContactDistanceValue(atomContact.distance, `${label} max distance`, warnings);
    if (!atom1 || !atom2) {
      warnings.push(`${label} atoms should look like A:145:NZ.`);
      return;
    }
    if (!distance) return;
    if (!atomContact.force) {
      warnings.push(`${label} requires force: true; atom_contact card was not emitted.`);
      return;
    }
    constraints.push("  - atom_contact:");
    constraints.push(`      atom1: ${yamlAtom(atom1)}`);
    constraints.push(`      atom2: ${yamlAtom(atom2)}`);
    constraints.push(`      max_distance: ${distance}`);
    constraints.push("      force: true");
    features.push(`atom_contact ${index + 1}`);
  });

  builderState.bonds.forEach((bond, index) => {
    const atom1 = parseAtomSpec(bond.atom1);
    const atom2 = parseAtomSpec(bond.atom2);
    const label = `Bond ${index + 1}`;
    if (!atom1 || !atom2) {
      warnings.push(`${label} atoms should look like A:145:SG.`);
      return;
    }
    constraints.push("  - bond:");
    constraints.push(`      atom1: ${yamlAtom(atom1)}`);
    constraints.push(`      atom2: ${yamlAtom(atom2)}`);
    features.push(`bond ${index + 1}`);
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
    const binder = fieldValue("yaml-affinity-binder").trim() || firstLigandId || "B";
    const binderLigand = ligandRecords.find((ligand) => ligand.ids.includes(binder));
    const matchingCopies = binderLigand
      ? ligandRecords
        .filter((ligand) => ligand.source === binderLigand.source && ligand.value === binderLigand.value)
        .flatMap((ligand) => ligand.ids)
      : [];
    if (!ligandRecords.length) warnings.push("Affinity requires a ligand entity.");
    if (binderLigand?.ids.length > 1 || matchingCopies.length > 1) {
      warnings.push("Affinity binder must resolve to one ligand copy. For affinity, use a unique ligand chain/value for the binder.");
    }
    if (binderLigand?.source === "ccd" && parseIdList(binderLigand.value).length > 1) {
      warnings.push("Affinity does not support multi-residue CCD ligands.");
    }
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
          <span class="field-label-row">
            <span>Modifications</span>
            <span
              class="field-help"
              tabindex="0"
              role="img"
              aria-label="Modifications use one based positions and CCD component codes from the Boltz cache."
              data-tooltip="Optional CCD substitutions, one per line: position:CCD. Positions are 1-based. Use protein CCDs for protein positions, RNA CCDs for RNA positions, and DNA CCDs for DNA positions. Examples: 12:MSE, 24:SEP, 8:PSU. The CCD code must exist in /opt/boltz-cache/mols."
            >?</span>
          </span>
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

function ligandCard(ligand, index) {
  const isCcd = ligand.source === "ccd";
  return `
    <article class="repeat-card ligand-card" data-uid="${ligand.uid}">
      <div class="repeat-card-heading">
        <h4>Ligand ${index + 1}</h4>
        <button class="ghost-button repeat-remove-button" data-action="remove-ligand" type="button">Remove</button>
      </div>
      <div class="builder-grid repeat-grid ligand-repeat-grid">
        <label class="field">
          <span>Chain ID(s)</span>
          <input data-ligand-field="ids" type="text" value="${escapeHtml(ligand.ids)}" placeholder="B or B, C">
        </label>
        <label class="field">
          <span>Source</span>
          <select data-ligand-field="source">
            <option value="smiles"${!isCcd ? " selected" : ""}>SMILES</option>
            <option value="ccd"${isCcd ? " selected" : ""}>CCD</option>
          </select>
        </label>
        <label class="field builder-span">
          <span data-ligand-value-label>${isCcd ? "CCD code(s)" : "SMILES"}</span>
          <input data-ligand-field="value" type="text" value="${escapeHtml(ligand.value)}" placeholder="${isCcd ? "ATP or ATP, MG" : "CC1=CC=CC=C1"}">
        </label>
      </div>
    </article>
  `;
}

function renderLigands() {
  const root = $("#ligand-list");
  if (!root) return;
  if (!builderState.ligands.length) {
    root.innerHTML = `<div class="repeat-empty">No ligands added.</div>`;
    return;
  }
  root.innerHTML = builderState.ligands.map(ligandCard).join("");
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

function atomContactCard(atomContact, index) {
  return `
    <article class="repeat-card atom-contact-card" data-uid="${atomContact.uid}">
      <div class="repeat-card-heading">
        <h4>Atom contact ${index + 1}</h4>
        <button class="ghost-button repeat-remove-button" data-action="remove-atom-contact" type="button">Remove</button>
      </div>
      <div class="builder-grid repeat-grid atom-contact-repeat-grid">
        <label class="field">
          <span>Atom 1</span>
          <input data-atom-contact-field="atom1" type="text" value="${escapeHtml(atomContact.atom1)}" placeholder="A:145:NZ">
        </label>
        <label class="field">
          <span>Atom 2</span>
          <input data-atom-contact-field="atom2" type="text" value="${escapeHtml(atomContact.atom2)}" placeholder="B:37:OD1">
        </label>
        <label class="field">
          <span>Max distance</span>
          <input data-atom-contact-field="distance" type="number" min="2" max="20" step="0.1" value="${escapeHtml(atomContact.distance)}">
        </label>
        <label class="toggle-field">
          <span>Force contact</span>
          <span class="switch">
            <input data-atom-contact-field="force" type="checkbox"${atomContact.force ? " checked" : ""}>
            <span class="slider"></span>
          </span>
        </label>
      </div>
    </article>
  `;
}

function renderAtomContacts() {
  const root = $("#atom-contact-list");
  if (!root) return;
  if (!builderState.atomContacts.length) {
    root.innerHTML = `<div class="repeat-empty">No atom contact constraints added.</div>`;
    return;
  }
  root.innerHTML = builderState.atomContacts.map(atomContactCard).join("");
}

function bondCard(bond, index) {
  return `
    <article class="repeat-card bond-card" data-uid="${bond.uid}">
      <div class="repeat-card-heading">
        <h4>Bond ${index + 1}</h4>
        <button class="ghost-button repeat-remove-button" data-action="remove-bond" type="button">Remove</button>
      </div>
      <div class="builder-grid repeat-grid bond-repeat-grid">
        <label class="field">
          <span>Atom 1</span>
          <input data-bond-field="atom1" type="text" value="${escapeHtml(bond.atom1)}" placeholder="A:145:SG">
        </label>
        <label class="field">
          <span>Atom 2</span>
          <input data-bond-field="atom2" type="text" value="${escapeHtml(bond.atom2)}" placeholder="B:1:C1">
        </label>
      </div>
    </article>
  `;
}

function renderBonds() {
  const root = $("#bond-list");
  if (!builderState.bonds.length) {
    root.innerHTML = `<div class="repeat-empty">No bond constraints added.</div>`;
    return;
  }
  root.innerHTML = builderState.bonds.map(bondCard).join("");
}

function updateYamlBuilderVisibility() {
  document.querySelectorAll(".ligand-card").forEach((card) => {
    const source = card.querySelector("[data-ligand-field='source']")?.value || "smiles";
    const label = card.querySelector("[data-ligand-value-label]");
    const value = card.querySelector("[data-ligand-field='value']");
    if (label) label.textContent = source === "ccd" ? "CCD code(s)" : "SMILES";
    if (value) value.placeholder = source === "ccd" ? "ATP or ATP, MG" : "CC1=CC=CC=C1";
  });

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
  builderState.ligands = presetLigands(preset).map((ligand, index) => createLigand({
    ids: ligand.ids || chainIdFromIndex((preset.polymers || YAML_TASK_PRESETS.structure.polymers).length + index),
    source: ligand.source || "smiles",
    value: ligand.value || DEFAULT_LIGAND_SMILES
  }));
  builderState.contacts = (preset.contacts || []).map((contact) => createContact(contact));
  builderState.atomContacts = (preset.atomContacts || []).map((atomContact) => createAtomContact(atomContact));
  builderState.bonds = presetBonds(preset).map((bond) => createBond(bond));
  renderPolymers();
  renderLigands();
  renderContacts();
  renderAtomContacts();
  renderBonds();

  setFieldValue("yaml-affinity-enabled", Boolean(preset.affinity?.enabled));
  setFieldValue("yaml-affinity-binder", preset.affinity?.binder || "B");

  setFieldValue("yaml-pocket-enabled", Boolean(preset.pocket?.enabled));
  setFieldValue("yaml-pocket-binder", preset.pocket?.binder || "B");
  setFieldValue("yaml-pocket-distance", preset.pocket?.distance || "6");
  setFieldValue("yaml-pocket-force", Boolean(preset.pocket?.force));
  setFieldValue("yaml-pocket-contacts", preset.pocket?.contacts || "");

  setFieldValue("yaml-template-enabled", Boolean(preset.template?.enabled));
  setFieldValue("yaml-template-format", preset.template?.format || "cif");
  setFieldValue("yaml-template-path", preset.template?.path || "./template.cif");
  setFieldValue("yaml-template-chain-ids", preset.template?.chainIds || "A");
  setFieldValue("yaml-template-template-ids", preset.template?.templateIds || "");
  setFieldValue("yaml-template-force", Boolean(preset.template?.force));
  setFieldValue("yaml-template-threshold", preset.template?.threshold || "2");

  generateYamlFromBuilder({ silent });
}

function yamlLineIndent(line) {
  return (String(line).match(/^\s*/) || [""])[0].length;
}

function yamlSectionLines(text, sectionName) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const sectionStart = lines.findIndex((line) => (
    yamlLineIndent(line) === 0 && new RegExp(`^${sectionName}:\\s*$`).test(line.trim())
  ));
  if (sectionStart === -1) return [];

  const section = [];
  for (let index = sectionStart + 1; index < lines.length; index += 1) {
    const line = lines[index];
    if (line.trim() && yamlLineIndent(line) === 0 && /^[A-Za-z_][\w-]*:\s*/.test(line.trim())) break;
    section.push(line);
  }
  return section;
}

function splitYamlItems(sectionLines) {
  const items = [];
  let itemIndent = null;
  let current = null;

  for (const line of sectionLines) {
    if (!line.trim()) {
      if (current) current.push(line);
      continue;
    }

    const trimmed = line.trim();
    const indent = yamlLineIndent(line);
    if (trimmed.startsWith("- ")) {
      if (itemIndent === null) itemIndent = indent;
      if (indent === itemIndent) {
        if (current) items.push(current);
        current = [line];
        continue;
      }
    }

    if (current) current.push(line);
  }

  if (current) items.push(current);
  return items;
}

function yamlItemHeader(itemLines) {
  const header = itemLines[0]?.trim().match(/^-\s+([A-Za-z_][\w-]*):\s*(.*)$/);
  if (!header) return null;
  return { key: header[1], value: header[2] || "" };
}

function parseYamlItemMapping(itemLines) {
  const map = {};
  for (let index = 1; index < itemLines.length; index += 1) {
    const line = itemLines[index];
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || trimmed.startsWith("- ")) continue;
    const match = trimmed.match(/^([A-Za-z_][\w-]*):(?:\s*(.*))?$/);
    if (!match) continue;

    const key = match[1];
    const value = match[2] || "";
    if (value !== "") {
      map[key] = value;
      continue;
    }

    const baseIndent = yamlLineIndent(line);
    const listValues = [];
    for (let childIndex = index + 1; childIndex < itemLines.length; childIndex += 1) {
      const childLine = itemLines[childIndex];
      const childTrimmed = childLine.trim();
      if (!childTrimmed || childTrimmed.startsWith("#")) continue;
      if (yamlLineIndent(childLine) <= baseIndent) break;
      if (!childTrimmed.startsWith("- ")) continue;
      const listValue = childTrimmed.replace(/^-\s+/, "").trim();
      if (listValue) listValues.push(listValue);
    }
    if (listValues.length) map[key] = `[${listValues.join(", ")}]`;
  }
  return map;
}

function parseYamlModifications(itemLines) {
  const modifications = [];
  const start = itemLines.findIndex((line) => line.trim() === "modifications:");
  if (start === -1) return "";

  const baseIndent = yamlLineIndent(itemLines[start]);
  let current = null;
  for (const line of itemLines.slice(start + 1)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (yamlLineIndent(line) <= baseIndent) break;

    const position = trimmed.match(/^-\s+position:\s*(.+)$/);
    if (position) {
      if (current?.position && current?.ccd) modifications.push(current);
      current = { position: stripYamlQuotes(position[1]), ccd: "" };
      continue;
    }

    const ccd = trimmed.match(/^ccd:\s*(.+)$/);
    if (ccd && current) current.ccd = stripYamlQuotes(ccd[1]);
  }
  if (current?.position && current?.ccd) modifications.push(current);

  return modifications.map((item) => `${item.position}:${item.ccd}`).join("\n");
}

function parseYamlSequences(text, parsed) {
  for (const item of splitYamlItems(yamlSectionLines(text, "sequences"))) {
    const header = yamlItemHeader(item);
    if (!header) continue;

    const map = parseYamlItemMapping(item);
    if (POLYMER_TYPES.has(header.key)) {
      const msa = map.msa ? stripYamlQuotes(map.msa) : "";
      const msaMode = msa ? (msa.toLowerCase() === "empty" ? "empty" : "custom") : "auto";
      parsed.polymers.push({
        type: header.key,
        ids: yamlValueAsText(map.id || "A"),
        sequence: stripYamlQuotes(map.sequence || ""),
        msaMode,
        msaPath: msaMode === "custom" ? msa : "",
        cyclic: boolFromYamlValue(map.cyclic),
        modifications: parseYamlModifications(item)
      });
      continue;
    }

    if (header.key === "ligand") {
      const source = map.ccd !== undefined ? "ccd" : "smiles";
      parsed.ligands.push({
        ids: yamlValueAsText(map.id || "B"),
        source,
        value: source === "ccd" ? yamlValueAsText(map.ccd || "") : stripYamlQuotes(map.smiles || "")
      });
      continue;
    }

    parsed.warnings.push(`Unsupported sequence entity "${header.key}" was left out of builder fields.`);
  }
}

function parseYamlConstraints(text, parsed) {
  for (const item of splitYamlItems(yamlSectionLines(text, "constraints"))) {
    const header = yamlItemHeader(item);
    if (!header) continue;

    const map = parseYamlItemMapping(item);
    if (header.key === "contact") {
      parsed.contacts.push({
        token1: yamlTokenAsField(map.token1 || "A:45"),
        token2: yamlTokenAsField(map.token2 || "B:67"),
        distance: stripYamlQuotes(map.max_distance || "6"),
        force: boolFromYamlValue(map.force)
      });
      continue;
    }

    if (header.key === "pocket") {
      parsed.pocket = {
        enabled: true,
        binder: stripYamlQuotes(map.binder || "B"),
        contacts: yamlContactListAsField(map.contacts || ""),
        distance: stripYamlQuotes(map.max_distance || "6"),
        force: boolFromYamlValue(map.force)
      };
      continue;
    }

    if (header.key === "atom_contact") {
      parsed.atomContacts.push({
        atom1: yamlAtomAsField(map.atom1 || "A:145:NZ"),
        atom2: yamlAtomAsField(map.atom2 || "B:37:OD1"),
        distance: stripYamlQuotes(map.max_distance || "3.5"),
        force: boolFromYamlValue(map.force)
      });
      continue;
    }

    if (header.key === "bond") {
      parsed.bonds.push({
        atom1: yamlAtomAsField(map.atom1 || "A:145:SG"),
        atom2: yamlAtomAsField(map.atom2 || "B:1:C1")
      });
      continue;
    }

    parsed.warnings.push(`Unsupported constraint "${header.key}" was left out of builder fields.`);
  }
}

function parseYamlTemplates(text, parsed) {
  const items = splitYamlItems(yamlSectionLines(text, "templates"));
  if (!items.length) return;

  const header = yamlItemHeader(items[0]);
  if (!header) return;
  const map = parseYamlItemMapping(items[0]);
  const format = ["cif", "pdb"].includes(header.key) ? header.key : "cif";
  parsed.template = {
    enabled: true,
    format,
    path: stripYamlQuotes(header.value || map[format] || `./template.${format}`),
    chainIds: yamlValueAsText(map.chain_id || "A"),
    templateIds: yamlValueAsText(map.template_id || ""),
    force: boolFromYamlValue(map.force),
    threshold: stripYamlQuotes(map.threshold || "2")
  };
  if (items.length > 1) parsed.warnings.push("Only the first template is editable in the builder.");
}

function parseYamlProperties(text, parsed) {
  for (const item of splitYamlItems(yamlSectionLines(text, "properties"))) {
    const header = yamlItemHeader(item);
    if (!header) continue;
    const map = parseYamlItemMapping(item);
    if (header.key === "affinity") {
      parsed.affinity = { enabled: true, binder: stripYamlQuotes(map.binder || "B") };
    } else {
      parsed.warnings.push(`Unsupported property "${header.key}" was left out of builder fields.`);
    }
  }
}

function parseBuilderYaml(text) {
  const parsed = {
    polymers: [],
    ligands: [],
    contacts: [],
    atomContacts: [],
    bonds: [],
    affinity: null,
    pocket: null,
    template: null,
    warnings: []
  };
  parseYamlSequences(text, parsed);
  parseYamlConstraints(text, parsed);
  parseYamlTemplates(text, parsed);
  parseYamlProperties(text, parsed);
  return parsed;
}

function profileFromParsedYaml(parsed) {
  if (parsed.affinity?.enabled) return "affinity";
  if (parsed.pocket?.enabled) return "pocket";
  if (parsed.contacts.length || parsed.atomContacts.length || parsed.bonds.length) return "contacts";
  if (parsed.template?.enabled) return "template";
  if (parsed.ligands.length) return "ligand";
  if (parsed.polymers.length > 1) return "complex";
  return "structure";
}

function setBuilderSectionOpen(sectionName, open) {
  const section = document.querySelector(`.builder-section[data-section="${sectionName}"]`);
  if (section) section.open = Boolean(open);
}

function openSectionsForLoadedYaml(parsed) {
  document.querySelectorAll(".builder-section").forEach((section) => {
    section.open = false;
  });
  setBuilderSectionOpen("polymer", parsed.polymers.length > 0);
  setBuilderSectionOpen("ligand", parsed.ligands.length > 0);
  setBuilderSectionOpen("affinity", parsed.affinity?.enabled);
  setBuilderSectionOpen("pocket", parsed.pocket?.enabled);
  setBuilderSectionOpen("contact-constraints", parsed.contacts.length > 0);
  setBuilderSectionOpen("atom-contact-constraints", parsed.atomContacts.length > 0);
  setBuilderSectionOpen("bond-constraints", parsed.bonds.length > 0);
  setBuilderSectionOpen("template", parsed.template?.enabled);
}

function applyParsedYamlToBuilder(parsed, filename, { preserveEditor = false } = {}) {
  setDraftName(filename);
  setFieldValue("yaml-profile", profileFromParsedYaml(parsed));

  const polymers = parsed.polymers.length
    ? parsed.polymers
    : [{ type: "protein", ids: "A", sequence: "M", msaMode: "auto" }];
  builderState.polymers = polymers.map((polymer, index) => createPolymer({
    ids: polymer.ids || chainIdFromIndex(index),
    sequence: polymer.sequence || "M",
    type: polymer.type || "protein",
    msaMode: polymer.msaMode || "auto",
    msaPath: polymer.msaPath || "",
    cyclic: Boolean(polymer.cyclic),
    modifications: polymer.modifications || ""
  }));
  builderState.ligands = parsed.ligands.map((ligand, index) => createLigand({
    ids: ligand.ids || chainIdFromIndex(builderState.polymers.length + index),
    source: ligand.source || "smiles",
    value: ligand.value || DEFAULT_LIGAND_SMILES
  }));
  builderState.contacts = parsed.contacts.map((contact) => createContact(contact));
  builderState.atomContacts = parsed.atomContacts.map((atomContact) => createAtomContact(atomContact));
  builderState.bonds = parsed.bonds.map((bond) => createBond(bond));
  renderPolymers();
  renderLigands();
  renderContacts();
  renderAtomContacts();
  renderBonds();

  setFieldValue("yaml-affinity-enabled", Boolean(parsed.affinity?.enabled));
  setFieldValue("yaml-affinity-binder", parsed.affinity?.binder || "B");

  setFieldValue("yaml-pocket-enabled", Boolean(parsed.pocket?.enabled));
  setFieldValue("yaml-pocket-binder", parsed.pocket?.binder || "B");
  setFieldValue("yaml-pocket-distance", parsed.pocket?.distance || "6");
  setFieldValue("yaml-pocket-force", Boolean(parsed.pocket?.force));
  setFieldValue("yaml-pocket-contacts", parsed.pocket?.contacts || "");

  setFieldValue("yaml-template-enabled", Boolean(parsed.template?.enabled));
  setFieldValue("yaml-template-format", parsed.template?.format || "cif");
  setFieldValue("yaml-template-path", parsed.template?.path || "./template.cif");
  setFieldValue("yaml-template-chain-ids", parsed.template?.chainIds || "A");
  setFieldValue("yaml-template-template-ids", parsed.template?.templateIds || "");
  setFieldValue("yaml-template-force", Boolean(parsed.template?.force));
  setFieldValue("yaml-template-threshold", parsed.template?.threshold || "2");

  openSectionsForLoadedYaml(parsed);
  const result = preserveEditor
    ? buildYamlFromBuilder()
    : generateYamlFromBuilder({ silent: true });
  renderYamlBuilderStatus({
    ...result,
    warnings: parsed.warnings.length ? [...parsed.warnings, ...result.warnings] : result.warnings
  });
}

function filenameFromPath(relativePath) {
  return String(relativePath || "").split(/[\\/]/).filter(Boolean).pop() || "loaded_input.yaml";
}

function upsertExistingYamlOption(input) {
  const select = $("#existing-yaml-select");
  if (!select || !input?.path || !/\.ya?ml$/i.test(input.path)) return;
  let option = Array.from(select.options).find((item) => item.value === input.path);
  if (!option) {
    option = new Option(input.path.replace(/^workspace\/inputs\//, ""), input.path);
    select.appendChild(option);
  }
  option.textContent = input.path.replace(/^workspace\/inputs\//, "");
  option.title = input.path;
}

function populateExistingYamlSelect(inputs = []) {
  const select = $("#existing-yaml-select");
  if (!select) return;
  const selected = select.value;
  select.innerHTML = "";
  select.appendChild(new Option("Start new input", ""));
  inputs
    .filter((input) => /\.ya?ml$/i.test(input.path || input.name || ""))
    .sort((a, b) => String(a.path).localeCompare(String(b.path)))
    .forEach(upsertExistingYamlOption);
  if (selected && Array.from(select.options).some((option) => option.value === selected)) {
    select.value = selected;
  }
}

async function loadExistingYaml(relativePath) {
  if (!relativePath) return;
  try {
    const response = await fetch(`/api/file?path=${encodeURIComponent(relativePath)}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Failed to load ${relativePath}.`);
    const text = await response.text();
    const parsed = parseBuilderYaml(text);
    const filename = filenameFromPath(relativePath);

    $("#input-editor").value = text.endsWith("\n") ? text : `${text}\n`;
    setDraftName(filename);
    if (!parsed.polymers.length && !parsed.ligands.length) {
      renderYamlBuilderStatus({
        warnings: ["No supported sequence entities were found. The YAML is loaded in the editor only."],
        summary: "Manual YAML loaded"
      });
      showToast("YAML loaded in editor.");
      return;
    }

    applyParsedYamlToBuilder(parsed, filename, { preserveEditor: true });
    const savedStatus = $("#saved-input-status");
    if (savedStatus) savedStatus.textContent = `Loaded: ${relativePath}`;
    showToast(parsed.warnings.length ? "YAML loaded with parser notes." : "YAML loaded.");
  } catch (error) {
    showToast(error.message);
  }
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

function updateLigandFromElement(element) {
  const card = element.closest(".ligand-card");
  if (!card) return;
  const ligand = builderState.ligands.find((item) => item.uid === card.dataset.uid);
  if (!ligand) return;
  const field = element.dataset.ligandField;
  ligand[field] = element.value;
  if (field === "source") renderLigands();
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

function updateAtomContactFromElement(element) {
  const card = element.closest(".atom-contact-card");
  if (!card) return;
  const atomContact = builderState.atomContacts.find((item) => item.uid === card.dataset.uid);
  if (!atomContact) return;
  const field = element.dataset.atomContactField;
  atomContact[field] = element.type === "checkbox" ? element.checked : element.value;
  syncYamlFromBuilder();
}

function updateBondFromElement(element) {
  const card = element.closest(".bond-card");
  if (!card) return;
  const bond = builderState.bonds.find((item) => item.uid === card.dataset.uid);
  if (!bond) return;
  bond[element.dataset.bondField] = element.value;
  syncYamlFromBuilder();
}

function bindRepeatLists() {
  $("#add-polymer-button").addEventListener("click", () => {
    builderState.polymers.push(createPolymer({ ids: chainIdFromIndex(builderState.polymers.length) }));
    renderPolymers();
    generateYamlFromBuilder({ silent: true });
  });

  $("#add-ligand-button").addEventListener("click", () => {
    builderState.ligands.push(createLigand({ ids: chainIdFromIndex(builderState.polymers.length + builderState.ligands.length) }));
    renderLigands();
    generateYamlFromBuilder({ silent: true });
  });

  $("#add-contact-button").addEventListener("click", () => {
    builderState.contacts.push(createContact());
    renderContacts();
    generateYamlFromBuilder({ silent: true });
  });

  $("#add-atom-contact-button").addEventListener("click", () => {
    builderState.atomContacts.push(createAtomContact());
    renderAtomContacts();
    generateYamlFromBuilder({ silent: true });
  });

  $("#add-bond-button").addEventListener("click", () => {
    builderState.bonds.push(createBond());
    renderBonds();
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

  $("#ligand-list").addEventListener("input", (event) => {
    if (event.target.dataset.ligandField) updateLigandFromElement(event.target);
  });
  $("#ligand-list").addEventListener("change", (event) => {
    if (event.target.dataset.ligandField) updateLigandFromElement(event.target);
  });
  $("#ligand-list").addEventListener("click", (event) => {
    if (event.target.dataset.action !== "remove-ligand") return;
    const card = event.target.closest(".ligand-card");
    if (!card) return;
    builderState.ligands = builderState.ligands.filter((item) => item.uid !== card.dataset.uid);
    renderLigands();
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

  $("#atom-contact-list").addEventListener("input", (event) => {
    if (event.target.dataset.atomContactField) updateAtomContactFromElement(event.target);
  });
  $("#atom-contact-list").addEventListener("change", (event) => {
    if (event.target.dataset.atomContactField) updateAtomContactFromElement(event.target);
  });
  $("#atom-contact-list").addEventListener("click", (event) => {
    if (event.target.dataset.action !== "remove-atom-contact") return;
    const card = event.target.closest(".atom-contact-card");
    if (!card) return;
    builderState.atomContacts = builderState.atomContacts.filter((item) => item.uid !== card.dataset.uid);
    renderAtomContacts();
    generateYamlFromBuilder({ silent: true });
  });

  $("#bond-list").addEventListener("input", (event) => {
    if (event.target.dataset.bondField) updateBondFromElement(event.target);
  });
  $("#bond-list").addEventListener("change", (event) => {
    if (event.target.dataset.bondField) updateBondFromElement(event.target);
  });
  $("#bond-list").addEventListener("click", (event) => {
    if (event.target.dataset.action !== "remove-bond") return;
    const card = event.target.closest(".bond-card");
    if (!card) return;
    builderState.bonds = builderState.bonds.filter((item) => item.uid !== card.dataset.uid);
    renderBonds();
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
    upsertExistingYamlOption(data.input);
    setFieldValue("existing-yaml-select", data.input.path);
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
    populateExistingYamlSelect(data.inputs || []);
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
  $("#existing-yaml-select").addEventListener("change", () => {
    const selected = fieldValue("existing-yaml-select");
    if (selected) loadExistingYaml(selected);
  });
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
