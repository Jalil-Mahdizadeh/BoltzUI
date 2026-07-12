"use strict";

const fsp = require("node:fs/promises");
const path = require("node:path");
const { writeJson } = require("./run-manifest");

const STRUCTURE_EXTENSIONS = new Set([".pdb", ".cif", ".mmcif"]);

function atomKey(chain, residue, atom, insertionCode = "") {
  return `${chain}\u0000${residue}\u0000${atom}\u0000${insertionCode}`;
}

function preferAltLocation(alt) {
  return !alt || alt === "." || alt === "?" || alt === "A" || alt === "1";
}

function parsePdb(text) {
  const atoms = new Map();
  for (const line of text.split(/\r?\n/)) {
    const record = line.slice(0, 6).trim();
    if (record !== "ATOM" && record !== "HETATM") continue;
    const atom = line.slice(12, 16).trim();
    const alt = line.slice(16, 17).trim();
    const chain = line.slice(21, 22).trim();
    const residue = Number.parseInt(line.slice(22, 26).trim(), 10);
    const x = Number(line.slice(30, 38));
    const y = Number(line.slice(38, 46));
    const z = Number(line.slice(46, 54));
    if (!chain || !atom || !Number.isInteger(residue) || ![x, y, z].every(Number.isFinite)) continue;
    const key = atomKey(chain, residue, atom);
    if (!atoms.has(key) || preferAltLocation(alt)) atoms.set(key, { x, y, z });
  }
  return atoms;
}

function tokenizeCif(text) {
  const tokens = [];
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const line = lines[lineIndex];
    if (line.startsWith(";")) {
      const value = [];
      lineIndex += 1;
      while (lineIndex < lines.length && !lines[lineIndex].startsWith(";")) {
        value.push(lines[lineIndex]);
        lineIndex += 1;
      }
      tokens.push(value.join("\n"));
      continue;
    }

    let index = 0;
    while (index < line.length) {
      while (index < line.length && /\s/.test(line[index])) index += 1;
      if (index >= line.length || line[index] === "#") break;
      if (line[index] === "'" || line[index] === '"') {
        const quote = line[index];
        index += 1;
        let value = "";
        while (index < line.length && line[index] !== quote) value += line[index++];
        index += 1;
        tokens.push(value);
      } else {
        let value = "";
        while (index < line.length && !/\s/.test(line[index])) value += line[index++];
        tokens.push(value);
      }
    }
  }
  return tokens;
}

function normalizeCifValue(value) {
  return !value || value === "." || value === "?" ? "" : String(value);
}

function createMmcifNamespace() {
  return { exact: new Map(), byBase: new Map() };
}

function addMmcifAtom(namespace, chain, residue, atom, insertionCode, coordinates, alt) {
  if (!chain || !Number.isInteger(residue) || !atom) return;
  const insertion = normalizeCifValue(insertionCode);
  const exactKey = atomKey(chain, residue, atom, insertion);
  if (namespace.exact.has(exactKey) && !preferAltLocation(alt)) return;
  namespace.exact.set(exactKey, coordinates);
  const baseKey = atomKey(chain, residue, atom);
  if (!namespace.byBase.has(baseKey)) namespace.byBase.set(baseKey, new Map());
  namespace.byBase.get(baseKey).set(insertion, coordinates);
}

function parseMmcif(text) {
  const tokens = tokenizeCif(text);
  const atoms = {
    format: "mmcif",
    author: createMmcifNamespace(),
    label: createMmcifNamespace()
  };
  for (let index = 0; index < tokens.length; index += 1) {
    if (tokens[index].toLowerCase() !== "loop_") continue;
    const tags = [];
    index += 1;
    while (index < tokens.length && tokens[index].startsWith("_")) tags.push(tokens[index++]);
    if (!tags.some((tag) => tag.startsWith("_atom_site."))) {
      index -= 1;
      continue;
    }

    const lowerTags = tags.map((tag) => tag.toLowerCase());
    const field = (...names) => {
      for (const name of names) {
        const found = lowerTags.indexOf(name.toLowerCase());
        if (found >= 0) return found;
      }
      return -1;
    };
    const groupIndex = field("_atom_site.group_PDB");
    const authChainIndex = field("_atom_site.auth_asym_id");
    const labelChainIndex = field("_atom_site.label_asym_id");
    const authResidueIndex = field("_atom_site.auth_seq_id");
    const labelResidueIndex = field("_atom_site.label_seq_id");
    const authAtomIndex = field("_atom_site.auth_atom_id");
    const labelAtomIndex = field("_atom_site.label_atom_id");
    const insertionIndex = field("_atom_site.pdbx_PDB_ins_code");
    const altIndex = field("_atom_site.label_alt_id", "_atom_site.auth_alt_id");
    const xIndex = field("_atom_site.Cartn_x");
    const yIndex = field("_atom_site.Cartn_y");
    const zIndex = field("_atom_site.Cartn_z");

    while (index + tags.length <= tokens.length) {
      const next = tokens[index];
      if (next === "loop_" || next.startsWith("_") || /^(data_|save_|stop_)/i.test(next)) {
        index -= 1;
        break;
      }
      const row = tokens.slice(index, index + tags.length);
      if (row.length < tags.length) break;
      index += tags.length;
      const group = groupIndex >= 0 ? row[groupIndex].toUpperCase() : "ATOM";
      if (group !== "ATOM" && group !== "HETATM") continue;
      const x = Number(row[xIndex]);
      const y = Number(row[yIndex]);
      const z = Number(row[zIndex]);
      if (![x, y, z].every(Number.isFinite)) continue;
      const alt = altIndex >= 0 ? row[altIndex] : ".";
      const coordinates = { x, y, z };
      addMmcifAtom(
        atoms.author,
        normalizeCifValue(row[authChainIndex]),
        Number(row[authResidueIndex]),
        normalizeCifValue(row[authAtomIndex]),
        insertionIndex >= 0 ? row[insertionIndex] : "",
        coordinates,
        alt
      );
      addMmcifAtom(
        atoms.label,
        normalizeCifValue(row[labelChainIndex]),
        Number(row[labelResidueIndex]),
        normalizeCifValue(row[labelAtomIndex]),
        "",
        coordinates,
        alt
      );
    }
  }
  return atoms;
}

function endpoint(restraint, side) {
  const insertionKey = `insertion${side}`;
  const insertionCodeKey = `insertion_code${side}`;
  const insertionSpecified = Object.prototype.hasOwnProperty.call(restraint, insertionKey)
    || Object.prototype.hasOwnProperty.call(restraint, insertionCodeKey);
  return {
    chain: restraint[`chain${side}`],
    residue: restraint[`residue${side}`],
    atom: restraint[`atom${side}`],
    insertionCode: normalizeCifValue(restraint[insertionKey] ?? restraint[insertionCodeKey]),
    insertionSpecified
  };
}

function endpointText(value) {
  return `${value.chain}:${value.residue}${value.insertionCode || ""}:${value.atom}`;
}

function resolveMmcifEndpoint(namespace, value) {
  if (value.insertionSpecified) {
    const coordinate = namespace.exact.get(atomKey(
      value.chain, value.residue, value.atom, value.insertionCode
    ));
    return coordinate
      ? { coordinate }
      : { error: `missing ${endpointText(value)}` };
  }

  const blank = namespace.exact.get(atomKey(value.chain, value.residue, value.atom));
  if (blank) return { coordinate: blank };
  const variants = namespace.byBase.get(atomKey(value.chain, value.residue, value.atom));
  if (!variants || variants.size === 0) return { error: `missing ${endpointText(value)}` };
  if (variants.size === 1) return { coordinate: variants.values().next().value };
  const codes = [...variants.keys()].map((code) => code || "<blank>").sort().join(", ");
  return { error: `ambiguous insertion codes for ${endpointText(value)} (${codes})` };
}

function resolveMmcifPair(atoms, first, second) {
  const attempts = [];
  for (const [label, namespace] of [["author", atoms.author], ["label", atoms.label]]) {
    const resolved1 = resolveMmcifEndpoint(namespace, first);
    const resolved2 = resolveMmcifEndpoint(namespace, second);
    if (resolved1.coordinate && resolved2.coordinate) {
      return { coordinate1: resolved1.coordinate, coordinate2: resolved2.coordinate };
    }
    attempts.push(`${label} namespace: ${[resolved1.error, resolved2.error].filter(Boolean).join(", ")}`);
  }
  return {
    error: `Unable to resolve atom-contact pair ${endpointText(first)} <-> ${endpointText(second)} entirely in the author or label namespace. ${attempts.join("; ")}`
  };
}

function roundDistance(value) {
  return Math.round(value * 1000) / 1000;
}

function measureStructure(restraint, atoms, model) {
  const first = endpoint(restraint, 1);
  const second = endpoint(restraint, 2);
  let coordinate1;
  let coordinate2;
  const missing = [];
  if (atoms?.format === "mmcif") {
    const resolved = resolveMmcifPair(atoms, first, second);
    coordinate1 = resolved.coordinate1;
    coordinate2 = resolved.coordinate2;
    if (resolved.error) missing.push(resolved.error);
  } else {
    coordinate1 = atoms.get(atomKey(first.chain, first.residue, first.atom));
    coordinate2 = atoms.get(atomKey(second.chain, second.residue, second.atom));
    if (!coordinate1) missing.push(`Unable to resolve atom-contact endpoint ${endpointText(first)}`);
    if (!coordinate2) missing.push(`Unable to resolve atom-contact endpoint ${endpointText(second)}`);
  }
  if (missing.length) {
    return {
      model,
      status: "unresolved",
      observed_distance: null,
      excess_distance: null,
      satisfied: null,
      unresolved_reason: missing.join("; ")
    };
  }
  const distance = Math.hypot(
    coordinate1.x - coordinate2.x,
    coordinate1.y - coordinate2.y,
    coordinate1.z - coordinate2.z
  );
  const observed = roundDistance(distance);
  const excess = roundDistance(Math.max(0, distance - restraint.max_distance));
  const satisfied = distance <= restraint.max_distance;
  return {
    model,
    status: satisfied ? "satisfied" : "violated",
    observed_distance: observed,
    excess_distance: excess,
    satisfied,
    unresolved_reason: null
  };
}

function modelName(filePath) {
  const stem = path.basename(filePath, path.extname(filePath));
  const match = stem.match(/model_(\d+)/);
  return match ? `model_${match[1]}` : stem;
}

async function findStructureFiles(directory, output = []) {
  let entries = [];
  try {
    entries = await fsp.readdir(directory, { withFileTypes: true });
  } catch {
    return output;
  }
  for (const entry of entries) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) await findStructureFiles(fullPath, output);
    else if (entry.isFile() && STRUCTURE_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) output.push(fullPath);
  }
  return output.sort();
}

async function createRestraintReport(resultDirectory, restraints) {
  const structures = await findStructureFiles(path.join(resultDirectory, "predictions"));
  const parsedStructures = [];
  for (const structurePath of structures) {
    const text = await fsp.readFile(structurePath, "utf8");
    const extension = path.extname(structurePath).toLowerCase();
    parsedStructures.push({
      model: modelName(structurePath),
      format: extension === ".pdb" ? "pdb" : "mmcif",
      path: structurePath,
      atoms: extension === ".pdb" ? parsePdb(text) : parseMmcif(text)
    });
  }
  return {
    schema_version: 1,
    generated_at: new Date().toISOString(),
    result_directory: resultDirectory,
    structures_examined: parsedStructures.map((structure) => ({
      model: structure.model,
      format: structure.format,
      file: path.basename(structure.path)
    })),
    restraints: restraints.map((restraint) => ({
      ...restraint,
      models: parsedStructures.map((structure) => measureStructure(restraint, structure.atoms, structure.model))
    }))
  };
}

async function writeRestraintReport(resultDirectory, restraints) {
  const report = await createRestraintReport(resultDirectory, restraints);
  const reportPath = path.join(resultDirectory, "atom_contact_restraints.json");
  await writeJson(reportPath, report);
  return { report, reportPath };
}

module.exports = {
  createRestraintReport,
  findStructureFiles,
  measureStructure,
  parseMmcif,
  parsePdb,
  writeRestraintReport
};
