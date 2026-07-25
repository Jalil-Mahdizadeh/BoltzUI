(function initializeInterfaceAuditSemantics(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.InterfaceAuditSemantics = api;
  }
}(typeof globalThis !== "undefined" ? globalThis : this, () => {
  "use strict";

  function fractionForPatch(model, patchName) {
    const total = model?.[`${patchName}_residue_total`];
    const satisfied = model?.[`${patchName}_residue_satisfied`];
    if (Number.isInteger(total) && total > 0 && Number.isInteger(satisfied)) {
      return { total, satisfied, fraction: satisfied / total };
    }
    const measurements = Array.isArray(model?.residue_restraints)
      ? model.residue_restraints.filter((item) => item.patch === patchName)
      : [];
    if (!measurements.length) return { total: null, satisfied: null, fraction: null };
    const resolved = measurements.filter((item) => typeof item.satisfied === "boolean");
    if (resolved.length !== measurements.length) {
      return { total: measurements.length, satisfied: null, fraction: null };
    }
    const resolvedSatisfied = resolved.filter((item) => item.satisfied).length;
    return {
      total: measurements.length,
      satisfied: resolvedSatisfied,
      fraction: resolvedSatisfied / measurements.length
    };
  }

  function normalize(model, schemaVersion) {
    const schema = Number(schemaVersion) || 0;
    const residueMeasurements = Array.isArray(model?.residue_restraints)
      ? model.residue_restraints.filter((item) => typeof item.satisfied === "boolean")
      : [];
    let patchContact;
    if (typeof model?.patch_contact_satisfied === "boolean") {
      patchContact = model.patch_contact_satisfied;
    } else if (schema >= 7 && typeof model?.satisfied === "boolean") {
      patchContact = model.satisfied;
    } else if (residueMeasurements.length) {
      patchContact = residueMeasurements.some((item) => item.satisfied);
    } else {
      patchContact = model?.satisfied === true ? true : null;
    }

    let allActiveResidues;
    if (typeof model?.all_active_residues_satisfied === "boolean") {
      allActiveResidues = model.all_active_residues_satisfied;
    } else if (schema > 0 && schema < 7 && typeof model?.satisfied === "boolean") {
      allActiveResidues = model.satisfied;
    } else if (residueMeasurements.length) {
      allActiveResidues = residueMeasurements.every((item) => item.satisfied);
    } else {
      allActiveResidues = null;
    }

    const patch1 = fractionForPatch(model, "patch1");
    const patch2 = fractionForPatch(model, "patch2");
    const balancedCoverage = Number.isFinite(model?.balanced_residue_satisfaction_fraction)
      ? model.balanced_residue_satisfaction_fraction
      : Number.isFinite(patch1.fraction) && Number.isFinite(patch2.fraction)
        ? (patch1.fraction + patch2.fraction) / 2
        : null;
    const status = allActiveResidues === true
      ? "satisfied"
      : patchContact === true
        ? "partial"
        : patchContact === false
          ? "violated"
          : "unresolved";
    return { patchContact, allActiveResidues, patch1, patch2, balancedCoverage, status };
  }

  return { normalize };
}));
