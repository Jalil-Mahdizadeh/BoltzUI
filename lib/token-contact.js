"use strict";

const { buildChainIndex } = require("./atom-contact");

class TokenContactValidationError extends Error {
  constructor(issues) {
    super(issues.join("\n"));
    this.name = "TokenContactValidationError";
    this.issues = issues;
  }
}

function documentHasTokenContacts(document) {
  return (Array.isArray(document.constraints) ? document.constraints : []).some(
    (constraint) => constraint
      && typeof constraint === "object"
      && Object.prototype.hasOwnProperty.call(constraint, "contact")
  );
}

function normalizeSelector(value, label, issues) {
  if (typeof value === "number") {
    if (Number.isInteger(value) && value > 0) return value;
    issues.push(`${label} must be a positive residue index or a nonempty atom name.`);
    return null;
  }
  if (typeof value !== "string") {
    issues.push(`${label} must be a positive residue index or a nonempty atom name.`);
    return null;
  }
  const selector = value.trim();
  if (!selector) {
    issues.push(`${label} must be a positive residue index or a nonempty atom name.`);
    return null;
  }
  return /^\d+$/.test(selector) && Number(selector) > 0 ? Number(selector) : selector;
}

function normalizeEndpoint(spec, label, issues) {
  if (!Array.isArray(spec) || spec.length !== 2) {
    issues.push(`${label} must be [CHAIN_ID, RES_IDX/ATOM_NAME].`);
    return null;
  }
  const chain = String(spec[0] ?? "").trim();
  if (!chain) issues.push(`${label} chain ID must be nonempty.`);
  const token = normalizeSelector(spec[1], `${label} selector`, issues);
  return chain && token !== null ? { chain, token } : null;
}

function endpointLabel(endpoint) {
  return `${endpoint.chain}:${endpoint.token}`;
}

function canonicalPair(endpoint1, endpoint2) {
  return [endpointLabel(endpoint1), endpointLabel(endpoint2)].sort().join("|");
}

function validateResolvedEndpoint(endpoint, chains, issues) {
  const chain = chains.get(endpoint.chain);
  if (!chain) {
    issues.push(`Unable to resolve token-contact endpoint ${endpointLabel(endpoint)}: chain does not exist in sequences.`);
    return;
  }
  if (chain.polymer) {
    if (!Number.isInteger(endpoint.token) || endpoint.token < 1) {
      issues.push(`Unable to resolve token-contact endpoint ${endpointLabel(endpoint)}: polymer tokens require a positive residue index.`);
    } else if (Number.isInteger(chain.length) && endpoint.token > chain.length) {
      issues.push(`Unable to resolve token-contact endpoint ${endpointLabel(endpoint)}: residue exceeds chain length ${chain.length}.`);
    }
  } else if (typeof endpoint.token !== "string") {
    issues.push(`Unable to resolve token-contact endpoint ${endpointLabel(endpoint)}: ligand tokens require an atom name.`);
  }
}

function validateTokenContacts(document, options = {}) {
  const issues = [];
  const chains = buildChainIndex(document);
  const contacts = [];
  const seen = new Map();
  const constraints = Array.isArray(document.constraints) ? document.constraints : [];
  const validateChains = options.validateChains !== false;
  let contactNumber = 0;

  for (const wrapper of constraints) {
    if (!wrapper || typeof wrapper !== "object" || Array.isArray(wrapper)
      || !Object.prototype.hasOwnProperty.call(wrapper, "contact")) continue;
    contactNumber += 1;
    const item = wrapper.contact;
    const prefix = `contact ${contactNumber}`;
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      issues.push(`${prefix} must be a mapping.`);
      continue;
    }

    const endpoint1 = normalizeEndpoint(item.token1, `${prefix} token1`, issues);
    const endpoint2 = normalizeEndpoint(item.token2, `${prefix} token2`, issues);
    const maxDistance = Number(item.max_distance);
    if (!Number.isFinite(maxDistance)) {
      issues.push(`${prefix} max_distance must be finite.`);
    } else if (maxDistance < 4 || maxDistance > 20) {
      issues.push(`${prefix} max_distance must be between 4.0 and 20.0 Angstrom.`);
    }
    if (item.force !== undefined && typeof item.force !== "boolean") {
      issues.push(`${prefix} force must be true or false when specified.`);
    }
    if (!endpoint1 || !endpoint2) continue;

    if (endpointLabel(endpoint1) === endpointLabel(endpoint2)) {
      issues.push(`${prefix} endpoints are identical (${endpointLabel(endpoint1)}).`);
    }
    if (validateChains) {
      validateResolvedEndpoint(endpoint1, chains, issues);
      validateResolvedEndpoint(endpoint2, chains, issues);
    }

    const key = canonicalPair(endpoint1, endpoint2);
    if (Number.isFinite(maxDistance)) {
      if (seen.has(key)) {
        const previous = seen.get(key);
        if (previous === maxDistance) {
          issues.push(`Duplicate contact constraint for ${key.replace("|", " <-> ")}.`);
        } else {
          issues.push(`Conflicting duplicate contact constraint for ${key.replace("|", " <-> ")}: max_distance ${previous} versus ${maxDistance}.`);
        }
      } else {
        seen.set(key, maxDistance);
      }
    }

    contacts.push({
      chain1: endpoint1.chain,
      token1: endpoint1.token,
      chain2: endpoint2.chain,
      token2: endpoint2.token,
      max_distance: maxDistance,
      force: item.force === true
    });
  }

  if (issues.length) throw new TokenContactValidationError(issues);
  return { chains, contacts };
}

module.exports = {
  TokenContactValidationError,
  documentHasTokenContacts,
  validateTokenContacts
};
