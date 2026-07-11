"use strict";

const fs = require("node:fs");
const path = require("node:path");
const YAML = require("yaml");

class AtomContactValidationError extends Error {
  constructor(issues) {
    super(issues.join("\n"));
    this.name = "AtomContactValidationError";
    this.issues = issues;
  }
}

function parseInputText(text, extension = ".yaml") {
  try {
    const parsed = extension.toLowerCase() === ".json" ? JSON.parse(text) : YAML.parse(text);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (error) {
    throw new AtomContactValidationError([`Unable to parse input: ${error.message}`]);
  }
}

function parseInputFile(filePath) {
  const extension = path.extname(filePath).toLowerCase();
  if (![".yaml", ".yml", ".json"].includes(extension)) return {};
  return parseInputText(fs.readFileSync(filePath, "utf8"), extension);
}

function entityIds(value) {
  const ids = Array.isArray(value) ? value : [value];
  return ids.map((id) => String(id ?? "").trim()).filter(Boolean);
}

function sequenceLength(value) {
  return typeof value === "string" ? value.replace(/\s+/g, "").length : null;
}

function buildChainIndex(document) {
  const chains = new Map();
  for (const entry of Array.isArray(document.sequences) ? document.sequences : []) {
    if (!entry || typeof entry !== "object") continue;
    for (const type of ["protein", "rna", "dna", "ligand"]) {
      const entity = entry[type];
      if (!entity || typeof entity !== "object") continue;
      for (const id of entityIds(entity.id)) {
        chains.set(id, {
          id,
          type,
          polymer: type !== "ligand",
          length: type === "ligand" ? null : sequenceLength(entity.sequence),
          msa: entity.msa
        });
      }
    }
  }
  return chains;
}

function endpointLabel(endpoint) {
  return `${endpoint.chain}:${endpoint.residue}:${endpoint.atom}`;
}

function normalizeEndpoint(spec, label, issues) {
  if (!Array.isArray(spec) || spec.length !== 3) {
    issues.push(`${label} must be [CHAIN_ID, RES_IDX, ATOM_NAME].`);
    return null;
  }
  const chain = String(spec[0] ?? "").trim();
  const residue = Number(spec[1]);
  const atom = String(spec[2] ?? "").trim();
  if (!chain) issues.push(`${label} chain ID must be nonempty.`);
  if (!Number.isInteger(residue) || residue < 1) issues.push(`${label} residue index must be a positive integer.`);
  if (!atom) issues.push(`${label} atom name must be nonempty.`);
  return { chain, residue, atom };
}

function canonicalPair(endpoint1, endpoint2) {
  return [endpointLabel(endpoint1), endpointLabel(endpoint2)].sort().join("|");
}

function validateAtomContacts(document, options = {}) {
  const issues = [];
  const chains = buildChainIndex(document);
  const restraints = [];
  const seen = new Map();
  const constraints = Array.isArray(document.constraints) ? document.constraints : [];

  for (let index = 0; index < constraints.length; index += 1) {
    const wrapper = constraints[index];
    if (!wrapper || typeof wrapper !== "object" || !Object.prototype.hasOwnProperty.call(wrapper, "atom_contact")) continue;
    const item = wrapper.atom_contact;
    const prefix = `atom_contact ${index + 1}`;
    if (!item || typeof item !== "object") {
      issues.push(`${prefix} must be a mapping.`);
      continue;
    }

    const endpoint1 = normalizeEndpoint(item.atom1, `${prefix} atom1`, issues);
    const endpoint2 = normalizeEndpoint(item.atom2, `${prefix} atom2`, issues);
    const maxDistance = Number(item.max_distance);
    if (!Number.isFinite(maxDistance) || maxDistance <= 0) {
      issues.push(`${prefix} max_distance must be finite and positive.`);
    } else if (maxDistance < 2 || maxDistance > 20) {
      issues.push(`${prefix} max_distance must be between 2.0 and 20.0 Angstrom.`);
    }
    if (item.force !== true) {
      issues.push(`${prefix} requires force: true for inference-time potential guidance.`);
    }

    if (!endpoint1 || !endpoint2) continue;
    for (const endpoint of [endpoint1, endpoint2]) {
      const chain = chains.get(endpoint.chain);
      if (!chain) {
        issues.push(`Unable to resolve atom-contact endpoint ${endpointLabel(endpoint)}: chain does not exist in sequences.`);
      } else if (chain.polymer && Number.isInteger(chain.length) && endpoint.residue > chain.length) {
        issues.push(`Unable to resolve atom-contact endpoint ${endpointLabel(endpoint)}: residue exceeds chain length ${chain.length}.`);
      }
    }
    if (endpointLabel(endpoint1) === endpointLabel(endpoint2)) {
      issues.push(`${prefix} endpoints are identical (${endpointLabel(endpoint1)}).`);
    }

    if (Number.isFinite(maxDistance) && maxDistance > 0) {
      const key = canonicalPair(endpoint1, endpoint2);
      if (seen.has(key)) {
        const previous = seen.get(key);
        if (previous.maxDistance === maxDistance) {
          issues.push(`Duplicate atom_contact restraint for ${key.replace("|", " <-> ")}.`);
        } else {
          issues.push(`Conflicting duplicate atom_contact restraint for ${key.replace("|", " <-> ")}: max_distance ${previous.maxDistance} versus ${maxDistance}.`);
        }
      } else {
        seen.set(key, { maxDistance, index });
      }
    }

    restraints.push({
      chain1: endpoint1.chain,
      residue1: endpoint1.residue,
      atom1: endpoint1.atom,
      chain2: endpoint2.chain,
      residue2: endpoint2.residue,
      atom2: endpoint2.atom,
      max_distance: maxDistance,
      force: item.force === true
    });
  }

  if (restraints.length > 0 && options.usePotentials !== true) {
    issues.push("Atom-pair upper-distance restraints require --use_potentials for inference-time guidance.");
  }
  if (issues.length) throw new AtomContactValidationError(issues);
  return { chains, restraints };
}

function inputMsaSummary(document, options) {
  const modes = new Set();
  for (const chain of buildChainIndex(document).values()) {
    if (chain.type !== "protein") continue;
    if (chain.msa === "empty") modes.add("empty");
    else if (typeof chain.msa === "string" && chain.msa.trim()) modes.add("custom");
    else modes.add("auto");
  }
  const inputModes = [...modes].sort();
  const usesServer = modes.has("auto") && options.use_msa_server;
  let mode = "not_applicable";
  if (inputModes.length === 1 && inputModes[0] !== "auto") mode = inputModes[0];
  else if (inputModes.length > 1) mode = "mixed";
  else if (usesServer) mode = "server";
  else if (inputModes.length === 1) mode = "input";
  return {
    mode,
    input_modes: inputModes,
    use_msa_server: usesServer,
    server_url: usesServer ? options.msa_server_url || null : null
  };
}

module.exports = {
  AtomContactValidationError,
  buildChainIndex,
  endpointLabel,
  inputMsaSummary,
  parseInputFile,
  parseInputText,
  validateAtomContacts
};
