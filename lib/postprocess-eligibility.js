"use strict";

const SUPPORTED_POLYMERS = new Set(["protein", "rna", "dna"]);
const STANDARD_ALPHABETS = {
  protein: new Set("ACDEFGHIKLMNPQRSTVWY"),
  rna: new Set("ACGU"),
  dna: new Set("ACGT")
};

function entityIds(value) {
  const values = Array.isArray(value) ? value : [value];
  return values.map((item) => String(item ?? "").trim()).filter(Boolean);
}

function entityLabel(type, entity, index) {
  const ids = entityIds(entity?.id);
  return ids.length ? `${type} chain ${ids.join(", ")}` : `${type} entry ${index + 1}`;
}

function summarizeIssues(issues) {
  const visible = issues.slice(0, 4);
  const remainder = issues.length - visible.length;
  const details = remainder > 0 ? `${visible.join("; ")}; and ${remainder} more` : visible.join("; ");
  return (
    `Hydrogen addition and energy minimization are unavailable because this input contains ${details}. ` +
    "Only unmodified, non-cyclic standard protein, RNA, and DNA polymers are currently supported."
  );
}

function analyzePostprocessEligibility(document) {
  if (!document || typeof document !== "object" || Array.isArray(document)) {
    return {
      eligible: false,
      reason: "Hydrogen addition and energy minimization are unavailable because the input document is not a valid object."
    };
  }

  const sequences = Array.isArray(document.sequences) ? document.sequences : [];
  const issues = [];
  sequences.forEach((entry, index) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
      issues.push(`an invalid sequence entry at position ${index + 1}`);
      return;
    }

    const entityTypes = Object.keys(entry);
    for (const type of entityTypes) {
      const entity = entry[type];
      if (!SUPPORTED_POLYMERS.has(type)) {
        issues.push(`${entityLabel(type, entity, index)}, which requires separate parameters`);
        continue;
      }

      if (!entity || typeof entity !== "object" || Array.isArray(entity)) {
        issues.push(`an invalid ${type} entry at position ${index + 1}`);
        continue;
      }

      const label = entityLabel(type, entity, index);
      if (entity.cyclic === true) {
        issues.push(`${label} is cyclic`);
      }
      const modifications = Array.isArray(entity.modifications)
        ? entity.modifications
        : entity.modifications ? [entity.modifications] : [];
      if (modifications.length > 0) {
        const codes = modifications
          .map((modification) => String(modification?.ccd ?? modification?.name ?? "").trim())
          .filter(Boolean);
        issues.push(`${label} declares modified residue${codes.length === 1 ? "" : "s"}${codes.length ? ` (${codes.join(", ")})` : ""}`);
      }

      const sequence = typeof entity.sequence === "string"
        ? entity.sequence.replace(/\s+/g, "").toUpperCase()
        : "";
      const invalidSymbols = [...new Set([...sequence].filter((symbol) => !STANDARD_ALPHABETS[type].has(symbol)))];
      if (invalidSymbols.length) {
        issues.push(`${label} uses non-standard sequence symbol${invalidSymbols.length === 1 ? "" : "s"} ${invalidSymbols.join(", ")}`);
      }
    }
  });

  return issues.length
    ? { eligible: false, reason: summarizeIssues(issues) }
    : { eligible: true, reason: null };
}

module.exports = { analyzePostprocessEligibility };
