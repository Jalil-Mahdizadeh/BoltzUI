"use strict";

const fsp = require("node:fs/promises");

// Cache parsed JSON by file identity, never just the directory's timestamp:
// rewriting a model or report does not necessarily touch its parent directory.
function createJsonCache({ maxBytes = 64 * 1024 * 1024, maxEntries = 1024 } = {}) {
  const entries = new Map();
  let bytes = 0;
  return async function readJson(file) {
    try {
      const stat = await fsp.stat(file);
      const signature = `${stat.ino}:${stat.size}:${stat.mtimeMs}:${stat.ctimeMs}`;
      const existing = entries.get(file);
      if (existing?.signature === signature) {
        entries.delete(file);
        entries.set(file, existing);
        return existing.value;
      }
      if (existing) { bytes -= existing.size; entries.delete(file); }
      const value = JSON.parse(await fsp.readFile(file, "utf8"));
      if (stat.size <= maxBytes) {
        while (entries.size && (bytes + stat.size > maxBytes || entries.size >= maxEntries)) {
          const oldest = entries.keys().next().value;
          bytes -= entries.get(oldest).size;
          entries.delete(oldest);
        }
        entries.set(file, { signature, size: stat.size, value });
        bytes += stat.size;
      }
      return value;
    } catch {
      const existing = entries.get(file);
      if (existing) { bytes -= existing.size; entries.delete(file); }
      return null;
    }
  };
}

function selectAuditModel(report, model) {
  if (!report || !model) return report;
  const select = (values) => (values || []).filter((entry) => entry.model === model);
  const measure = (entry) => ({ ...entry, models: select(entry.models) });
  return {
    ...report,
    structures_examined: select(report.structures_examined),
    model_summaries: select(report.model_summaries),
    restraints: (report.restraints || []).map(measure),
    token_contacts: (report.token_contacts || []).map(measure),
    interface_contacts: (report.interface_contacts || []).map(measure),
    union_groups: (report.union_groups || []).map((group) => ({
      ...measure(group),
      alternatives: (group.alternatives || []).map(({ models, ...alternative }) => alternative)
    }))
  };
}

module.exports = { createJsonCache, selectAuditModel };
