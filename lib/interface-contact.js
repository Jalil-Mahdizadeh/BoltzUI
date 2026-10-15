"use strict";

const { buildChainIndex } = require("./atom-contact");

class InterfaceContactValidationError extends Error {
  constructor(issues) {
    super(issues.join("\n"));
    this.name = "InterfaceContactValidationError";
    this.issues = issues;
  }
}

function documentHasInterfaceContacts(document) {
  return (Array.isArray(document.constraints) ? document.constraints : []).some(
    (constraint) => constraint
      && typeof constraint === "object"
      && Object.prototype.hasOwnProperty.call(constraint, "interface_contact")
  );
}

function normalizePatch(value, label, issues) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    issues.push(`${label} must be a mapping with chain and residues.`);
    return null;
  }
  const chain = String(value.chain ?? "").trim();
  if (!chain) issues.push(`${label} chain must be nonempty.`);
  if (!Array.isArray(value.residues) || value.residues.length === 0) {
    issues.push(`${label} residues must be a nonempty list of positive residue indices.`);
    return null;
  }
  const residues = [];
  const seen = new Set();
  value.residues.forEach((rawResidue, index) => {
    const residue = Number(rawResidue);
    if (!Number.isInteger(residue) || residue < 1) {
      issues.push(`${label} residue ${index + 1} must be a positive integer.`);
      return;
    }
    if (seen.has(residue)) {
      issues.push(`${label} contains duplicate residue ${residue}.`);
      return;
    }
    seen.add(residue);
    residues.push(residue);
  });
  return chain && residues.length ? { chain, residues } : null;
}

function patchLabel(patch) {
  return `${patch.chain}:[${[...patch.residues].sort((a, b) => a - b).join(",")}]`;
}

function canonicalInterface(patch1, patch2) {
  return [patchLabel(patch1), patchLabel(patch2)].sort().join("|");
}

function sameChainSequenceNeighbors(residue1, residue2, chain) {
  const delta = Math.abs(residue1 - residue2);
  return delta <= 1 || (
    chain?.cyclic === true
    && Number.isInteger(chain.length)
    && chain.length - delta <= 1
  );
}

function residuesWithoutEligibleTarget(sourceResidues, targetResidues, chain) {
  return sourceResidues.filter((source) => (
    !targetResidues.some((target) => !sameChainSequenceNeighbors(source, target, chain))
  ));
}

function validateResolvedPatch(patch, label, chains, issues) {
  const chain = chains.get(patch.chain);
  if (!chain) {
    issues.push(`${label} chain ${patch.chain} does not exist in sequences.`);
    return;
  }
  if (chain.type !== "protein") {
    issues.push(`${label} chain ${patch.chain} must be a protein chain for CSP-derived interface guidance.`);
    return;
  }
  if (Number.isInteger(chain.length)) {
    for (const residue of patch.residues) {
      if (residue > chain.length) {
        issues.push(`${label} residue ${patch.chain}:${residue} exceeds chain length ${chain.length}.`);
      }
    }
  }
}

function validateInterfaceContacts(document, options = {}) {
  const issues = [];
  const chains = buildChainIndex(document);
  const interfaces = [];
  const constraints = Array.isArray(document.constraints) ? document.constraints : [];
  const excludedBonds = constraints.flatMap((constraint) => {
    const bond = constraint?.bond;
    if (!Array.isArray(bond?.atom1) || !Array.isArray(bond?.atom2)) return [];
    return [{ atom1: bond.atom1, atom2: bond.atom2 }];
  });
  const validateChains = options.validateChains !== false;
  const seen = new Map();
  let interfaceNumber = 0;

  for (const wrapper of constraints) {
    if (!wrapper || typeof wrapper !== "object" || Array.isArray(wrapper)
      || !Object.prototype.hasOwnProperty.call(wrapper, "interface_contact")) continue;
    interfaceNumber += 1;
    const item = wrapper.interface_contact;
    const prefix = `interface_contact ${interfaceNumber}`;
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      issues.push(`${prefix} must be a mapping.`);
      continue;
    }

    const patch1 = normalizePatch(item.patch1, `${prefix} patch1`, issues);
    const patch2 = normalizePatch(item.patch2, `${prefix} patch2`, issues);
    const maxDistance = Number(item.max_distance);
    if (!Number.isFinite(maxDistance)) {
      issues.push(`${prefix} max_distance must be finite.`);
    } else if (maxDistance < 4 || maxDistance > 20) {
      issues.push(`${prefix} max_distance must be between 4.0 and 20.0 Angstrom.`);
    }
    if (item.force !== undefined && typeof item.force !== "boolean") {
      issues.push(`${prefix} force must be true or false when specified.`);
    }
    if (!patch1 || !patch2) continue;

    if (patch1.chain === patch2.chain) {
      const chain = chains.get(patch1.chain);
      const overlap = patch1.residues.filter((residue) => patch2.residues.includes(residue));
      if (overlap.length) {
        issues.push(
          `${prefix} same-chain patches must be disjoint; overlapping residues: ${overlap.join(", ")}.`
        );
      }
      const patch1WithoutTarget = residuesWithoutEligibleTarget(
        patch1.residues,
        patch2.residues,
        chain
      );
      const patch2WithoutTarget = residuesWithoutEligibleTarget(
        patch2.residues,
        patch1.residues,
        chain
      );
      if (patch1WithoutTarget.length || patch2WithoutTarget.length) {
        const details = [
          patch1WithoutTarget.length ? `patch1: ${patch1WithoutTarget.join(", ")}` : "",
          patch2WithoutTarget.length ? `patch2: ${patch2WithoutTarget.join(", ")}` : ""
        ].filter(Boolean).join("; ");
        issues.push(
          `${prefix} every active residue must have a non-neighbor residue in the `
          + `opposite patch; residues without an eligible target: ${details}.`
        );
      }
    }
    if (validateChains) {
      validateResolvedPatch(patch1, `${prefix} patch1`, chains, issues);
      validateResolvedPatch(patch2, `${prefix} patch2`, chains, issues);
    }

    const key = canonicalInterface(patch1, patch2);
    if (seen.has(key)) {
      issues.push(
        `Duplicate interface_contact constraint for ${key.replace("|", " <-> ")} `
        + `(constraints ${seen.get(key)} and ${interfaceNumber}).`
      );
    } else {
      seen.set(key, interfaceNumber);
    }
    const cyclicPeriods = {};
    for (const patch of [patch1, patch2]) {
      const chain = chains.get(patch.chain);
      if (chain?.cyclic === true && Number.isInteger(chain.length)) {
        cyclicPeriods[patch.chain] = chain.length;
      }
    }
    interfaces.push({
      interface_index: interfaceNumber,
      patch1,
      patch2,
      max_distance: maxDistance,
      force: item.force === true,
      ...(excludedBonds.length ? { excluded_bonds: excludedBonds } : {}),
      ...(Object.keys(cyclicPeriods).length ? { cyclic_periods: cyclicPeriods } : {})
    });
  }

  if (issues.length) throw new InterfaceContactValidationError(issues);
  return { chains, interfaces };
}

module.exports = {
  InterfaceContactValidationError,
  documentHasInterfaceContacts,
  validateInterfaceContacts
};
