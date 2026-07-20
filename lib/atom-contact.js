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

function documentHasAtomContacts(document) {
  return (Array.isArray(document.constraints) ? document.constraints : []).some(
    (constraint) => constraint
      && typeof constraint === "object"
      && (
        Object.prototype.hasOwnProperty.call(constraint, "atom_contact")
        || Object.prototype.hasOwnProperty.call(constraint, "atom_contact_union")
      )
  );
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
  let valid = true;
  if (!chain) {
    issues.push(`${label} chain ID must be nonempty.`);
    valid = false;
  }
  if (!Number.isInteger(residue) || residue < 1) {
    issues.push(`${label} residue index must be a positive integer.`);
    valid = false;
  }
  if (!atom) {
    issues.push(`${label} atom name must be nonempty.`);
    valid = false;
  }
  if (!valid) return null;
  return { chain, residue, atom };
}

function canonicalPair(endpoint1, endpoint2) {
  return [endpointLabel(endpoint1), endpointLabel(endpoint2)].sort().join("|");
}

function normalizeAtomContact(item, prefix, issues) {
  if (!item || typeof item !== "object" || Array.isArray(item)) {
    issues.push(`${prefix} must be a mapping.`);
    return null;
  }

  const endpoint1 = normalizeEndpoint(item.atom1, `${prefix} atom1`, issues);
  const endpoint2 = normalizeEndpoint(item.atom2, `${prefix} atom2`, issues);
  const maxDistance = Number(item.max_distance);
  if (!Number.isFinite(maxDistance) || maxDistance <= 0) {
    issues.push(`${prefix} max_distance must be finite and positive.`);
  } else if (maxDistance < 2 || maxDistance > 20) {
    issues.push(`${prefix} max_distance must be between 2.0 and 20.0 Angstrom.`);
  }
  if (item.force !== undefined && item.force !== true) {
    issues.push(`${prefix} force must be true when specified.`);
  }
  if (!endpoint1 || !endpoint2) return null;
  if (endpointLabel(endpoint1) === endpointLabel(endpoint2)) {
    issues.push(`${prefix} endpoints are identical (${endpointLabel(endpoint1)}).`);
  }

  return {
    chain1: endpoint1.chain,
    residue1: endpoint1.residue,
    atom1: endpoint1.atom,
    chain2: endpoint2.chain,
    residue2: endpoint2.residue,
    atom2: endpoint2.atom,
    max_distance: maxDistance,
    force: item.force === true
  };
}

function validateResolvedEndpoints(restraint, chains, issues) {
  for (const endpoint of [
    { chain: restraint.chain1, residue: restraint.residue1, atom: restraint.atom1 },
    { chain: restraint.chain2, residue: restraint.residue2, atom: restraint.atom2 }
  ]) {
    const chain = chains.get(endpoint.chain);
    if (!chain) {
      issues.push(`Unable to resolve atom-contact endpoint ${endpointLabel(endpoint)}: chain does not exist in sequences.`);
    } else if (chain.polymer && Number.isInteger(chain.length) && endpoint.residue > chain.length) {
      issues.push(`Unable to resolve atom-contact endpoint ${endpointLabel(endpoint)}: residue exceeds chain length ${chain.length}.`);
    }
  }
}

function normalizedPair(restraint) {
  return canonicalPair(
    { chain: restraint.chain1, residue: restraint.residue1, atom: restraint.atom1 },
    { chain: restraint.chain2, residue: restraint.residue2, atom: restraint.atom2 }
  );
}

function validateAtomContactConstraints(document, options = {}) {
  const issues = [];
  const chains = buildChainIndex(document);
  const restraints = [];
  const unionGroups = [];
  const seenExact = new Map();
  const constraints = Array.isArray(document.constraints) ? document.constraints : [];
  const validateChains = options.validateChains !== false;
  let exactNumber = 0;
  let unionNumber = 0;

  for (let index = 0; index < constraints.length; index += 1) {
    const wrapper = constraints[index];
    if (!wrapper || typeof wrapper !== "object" || Array.isArray(wrapper)) continue;

    if (Object.prototype.hasOwnProperty.call(wrapper, "atom_contact")) {
      exactNumber += 1;
      const item = wrapper.atom_contact;
      const prefix = `atom_contact ${exactNumber}`;
      const restraint = normalizeAtomContact(item, prefix, issues);
      if (!restraint) continue;
      if (item.force !== true) {
        issues.push(`${prefix} requires force: true for inference-time potential guidance.`);
      }
      if (validateChains) validateResolvedEndpoints(restraint, chains, issues);

      if (Number.isFinite(restraint.max_distance) && restraint.max_distance > 0) {
        const key = normalizedPair(restraint);
        if (seenExact.has(key)) {
          const previous = seenExact.get(key);
          if (previous.maxDistance === restraint.max_distance) {
            issues.push(`Duplicate atom_contact restraint for ${key.replace("|", " <-> ")}.`);
          } else {
            issues.push(`Conflicting duplicate atom_contact restraint for ${key.replace("|", " <-> ")}: max_distance ${previous.maxDistance} versus ${restraint.max_distance}.`);
          }
        } else {
          seenExact.set(key, { maxDistance: restraint.max_distance, index });
        }
      }
      restraints.push(restraint);
      continue;
    }

    if (!Object.prototype.hasOwnProperty.call(wrapper, "atom_contact_union")) continue;
    unionNumber += 1;
    const item = wrapper.atom_contact_union;
    const prefix = `atom_contact_union ${unionNumber}`;
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      issues.push(`${prefix} must be a mapping.`);
      continue;
    }
    if (item.force !== true) {
      issues.push(`${prefix} requires force: true for inference-time potential guidance.`);
    }
    if (!Array.isArray(item.alternatives) || item.alternatives.length < 2) {
      issues.push(`${prefix} alternatives must contain at least two atom-contact alternatives.`);
      continue;
    }

    const alternatives = [];
    const seenAlternatives = new Map();
    for (let alternativeIndex = 0; alternativeIndex < item.alternatives.length; alternativeIndex += 1) {
      const alternativePrefix = `${prefix} alternative ${alternativeIndex + 1}`;
      const rawAlternative = item.alternatives[alternativeIndex];
      if (!rawAlternative || typeof rawAlternative !== "object" || Array.isArray(rawAlternative)) {
        issues.push(`${alternativePrefix} must be a mapping.`);
        continue;
      }
      const alternative = normalizeAtomContact(
        { ...rawAlternative, force: true },
        alternativePrefix,
        issues
      );
      if (!alternative) continue;
      if (validateChains) validateResolvedEndpoints(alternative, chains, issues);
      const key = normalizedPair(alternative);
      if (seenAlternatives.has(key)) {
        issues.push(
          `Duplicate ${prefix} alternative for ${key.replace("|", " <-> ")}; `
          + `alternatives ${seenAlternatives.get(key)} and ${alternativeIndex + 1} resolve to the same exact pair.`
        );
      } else {
        seenAlternatives.set(key, alternativeIndex + 1);
      }
      alternatives.push({
        ...alternative,
        alternative_index: alternativeIndex + 1
      });
    }
    unionGroups.push({
      group_index: unionNumber,
      force: item.force === true,
      alternatives
    });
  }

  if (issues.length) throw new AtomContactValidationError(issues);
  return { chains, restraints, unionGroups };
}

function validateAtomContacts(document, options = {}) {
  return validateAtomContactConstraints(document, options);
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
  documentHasAtomContacts,
  endpointLabel,
  inputMsaSummary,
  parseInputFile,
  parseInputText,
  validateAtomContactConstraints,
  validateAtomContacts
};
