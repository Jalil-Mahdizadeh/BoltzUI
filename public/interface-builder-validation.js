(function initializeInterfaceBuilderValidation(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.InterfaceBuilderValidation = api;
  }
}(typeof globalThis !== "undefined" ? globalThis : this, () => {
  "use strict";

  function parseIds(value) {
    return String(value || "")
      .split(/[,\s]+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function sequenceLength(value) {
    return String(value || "").replace(/\s+/g, "").length;
  }

  function buildPolymerChainIndex(polymers) {
    const chains = new Map();
    for (const polymer of Array.isArray(polymers) ? polymers : []) {
      for (const id of parseIds(polymer?.ids)) {
        if (chains.has(id)) {
          chains.get(id).ambiguous = true;
          continue;
        }
        chains.set(id, {
          id,
          type: polymer?.type || "protein",
          length: sequenceLength(polymer?.sequence),
          ambiguous: false
        });
      }
    }
    return chains;
  }

  function validateInterfacePatch(chainValue, residues, label, chainIndex) {
    const issues = [];
    const chainId = String(chainValue || "").trim();
    if (!chainId) {
      issues.push(`${label} chain ID must be nonempty.`);
      return issues;
    }
    const chain = chainIndex.get(chainId);
    if (!chain) {
      issues.push(`${label} chain "${chainId}" does not exist among the current polymers.`);
      return issues;
    }
    if (chain.ambiguous) {
      issues.push(`${label} chain "${chainId}" is assigned to more than one polymer.`);
      return issues;
    }
    if (chain.type !== "protein") {
      issues.push(`${label} chain "${chainId}" must be a protein chain.`);
      return issues;
    }
    for (const residue of residues) {
      if (residue > chain.length) {
        issues.push(
          `${label} residue ${chainId}:${residue} exceeds chain length ${chain.length}.`
        );
      }
    }
    return issues;
  }

  function canEmitInterfaceContactDraft(patch1, patch2) {
    return [patch1, patch2].every((patch) => (
      Boolean(String(patch?.chain || "").trim())
      && patch?.syntaxValid !== false
      && Array.isArray(patch?.residues)
      && patch.residues.length > 0
    ));
  }

  return {
    buildPolymerChainIndex,
    validateInterfacePatch,
    canEmitInterfaceContactDraft
  };
}));
