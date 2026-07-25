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
          cyclic: polymer?.cyclic === true,
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

  function sameChainSequenceNeighbors(residue1, residue2, chain) {
    const delta = Math.abs(residue1 - residue2);
    return delta <= 1 || (
      chain?.cyclic === true
      && Number.isInteger(chain.length)
      && chain.length - delta <= 1
    );
  }

  function validateInterfacePatchPair(chainId, patch1Residues, patch2Residues, label, chainIndex) {
    const issues = [];
    const overlap = patch1Residues.filter((residue) => patch2Residues.includes(residue));
    if (overlap.length) {
      issues.push(`${label} same-chain patches overlap at residue(s) ${overlap.join(", ")}.`);
    }
    const chain = chainIndex.get(chainId);
    const missing1 = patch1Residues.filter((source) => (
      !patch2Residues.some((target) => !sameChainSequenceNeighbors(source, target, chain))
    ));
    const missing2 = patch2Residues.filter((source) => (
      !patch1Residues.some((target) => !sameChainSequenceNeighbors(source, target, chain))
    ));
    if (missing1.length || missing2.length) {
      const details = [
        missing1.length ? `patch 1: ${missing1.join(", ")}` : "",
        missing2.length ? `patch 2: ${missing2.join(", ")}` : ""
      ].filter(Boolean).join("; ");
      issues.push(
        `${label} every active residue needs a non-neighbor residue in the opposite `
        + `patch; residues without an eligible target: ${details}.`
      );
    }
    return issues;
  }

  return {
    buildPolymerChainIndex,
    validateInterfacePatch,
    validateInterfacePatchPair,
    canEmitInterfaceContactDraft
  };
}));
