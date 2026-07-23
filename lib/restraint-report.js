"use strict";

const fsp = require("node:fs/promises");
const path = require("node:path");
const { writeJson } = require("./run-manifest");

const STRUCTURE_EXTENSIONS = new Set([".pdb", ".cif", ".mmcif"]);

function atomKey(chain, residue, atom, insertionCode = "") {
  return `${chain}\u0000${residue}\u0000${atom}\u0000${insertionCode}`;
}

function residueKey(chain, residue) {
  return `${chain}\u0000${residue}`;
}

function chainAtomKey(chain, atom) {
  return `${chain}\u0000${atom}`;
}

function createTokenIndex(records) {
  const index = { residues: new Map(), atoms: new Map() };
  for (const record of records) {
    const residue = residueKey(record.chain, record.residue);
    const atom = chainAtomKey(record.chain, record.atom);
    if (!index.residues.has(residue)) index.residues.set(residue, []);
    if (!index.atoms.has(atom)) index.atoms.set(atom, []);
    index.residues.get(residue).push(record);
    index.atoms.get(atom).push(record);
  }
  return index;
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
    const element = line.slice(76, 78).trim().toUpperCase()
      || atom.replace(/^\d+/, "").slice(0, 1).toUpperCase();
    if (!chain || !atom || !Number.isInteger(residue) || ![x, y, z].every(Number.isFinite)) continue;
    const key = atomKey(chain, residue, atom);
    if (!atoms.has(key) || preferAltLocation(alt)) {
      atoms.set(key, { x, y, z, chain, residue, atom, element, insertionCode: "" });
    }
  }
  atoms.format = "pdb";
  atoms.tokenIndex = createTokenIndex(atoms.values());
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

function addMmcifAtom(namespace, chain, residue, atom, insertionCode, coordinates, alt, element) {
  if (!chain || !Number.isInteger(residue) || !atom) return;
  const insertion = normalizeCifValue(insertionCode);
  const exactKey = atomKey(chain, residue, atom, insertion);
  if (namespace.exact.has(exactKey) && !preferAltLocation(alt)) return;
  const record = {
    ...coordinates,
    chain,
    residue,
    atom,
    element: normalizeCifValue(element).toUpperCase(),
    insertionCode: insertion
  };
  namespace.exact.set(exactKey, record);
  const baseKey = atomKey(chain, residue, atom);
  if (!namespace.byBase.has(baseKey)) namespace.byBase.set(baseKey, new Map());
  namespace.byBase.get(baseKey).set(insertion, record);
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
    const elementIndex = field("_atom_site.type_symbol");

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
        alt,
        elementIndex >= 0 ? row[elementIndex] : ""
      );
      addMmcifAtom(
        atoms.label,
        normalizeCifValue(row[labelChainIndex]),
        Number(row[labelResidueIndex]),
        normalizeCifValue(row[labelAtomIndex]),
        "",
        coordinates,
        alt,
        elementIndex >= 0 ? row[elementIndex] : ""
      );
    }
  }
  atoms.author.tokenIndex = createTokenIndex(atoms.author.exact.values());
  atoms.label.tokenIndex = createTokenIndex(atoms.label.exact.values());
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

function tokenEndpoint(contact, side) {
  return {
    chain: contact[`chain${side}`],
    token: contact[`token${side}`]
  };
}

function tokenEndpointText(value) {
  return `${value.chain}:${value.token}`;
}

function resolveTokenEndpoint(tokenIndex, value) {
  const matches = Number.isInteger(value.token)
    ? tokenIndex?.residues.get(residueKey(value.chain, value.token))
    : tokenIndex?.atoms.get(chainAtomKey(value.chain, value.token));
  return Array.isArray(matches) && matches.length
    ? { atoms: matches }
    : { error: `missing ${tokenEndpointText(value)}` };
}

function resolveMmcifTokenPair(atoms, first, second) {
  const attempts = [];
  for (const [label, namespace] of [["author", atoms.author], ["label", atoms.label]]) {
    const resolved1 = resolveTokenEndpoint(namespace.tokenIndex, first);
    const resolved2 = resolveTokenEndpoint(namespace.tokenIndex, second);
    if (resolved1.atoms && resolved2.atoms) {
      return { atoms1: resolved1.atoms, atoms2: resolved2.atoms, namespace: label };
    }
    attempts.push(`${label} namespace: ${[resolved1.error, resolved2.error].filter(Boolean).join(", ")}`);
  }
  return {
    error: `Unable to resolve token-contact pair ${tokenEndpointText(first)} <-> ${tokenEndpointText(second)} entirely in the author or label namespace. ${attempts.join("; ")}`
  };
}

function closestAtomPair(atoms1, atoms2) {
  let closest = null;
  for (const atom1 of atoms1) {
    for (const atom2 of atoms2) {
      const distance = Math.hypot(atom1.x - atom2.x, atom1.y - atom2.y, atom1.z - atom2.z);
      if (!closest || distance < closest.distance) closest = { atom1, atom2, distance };
    }
  }
  return closest;
}

function measuredAtomLabel(atom) {
  return `${atom.chain}:${atom.residue}${atom.insertionCode || ""}:${atom.atom}`;
}

function isHeavyAtom(atom) {
  const element = String(atom?.element || "").toUpperCase();
  if (element) return element !== "H" && element !== "D";
  return !/^[0-9]*[HD]/i.test(String(atom?.atom || ""));
}

function resolvePatch(tokenIndex, patch) {
  const resolved = [];
  const errors = [];
  for (const residue of patch.residues) {
    const endpointValue = { chain: patch.chain, token: residue };
    const match = resolveTokenEndpoint(tokenIndex, endpointValue);
    const heavyAtoms = match.atoms?.filter(isHeavyAtom) || [];
    if (!match.atoms) {
      errors.push(match.error);
    } else if (!heavyAtoms.length) {
      errors.push(`no heavy atoms for ${patch.chain}:${residue}`);
    } else {
      resolved.push({ chain: patch.chain, residue, atoms: heavyAtoms });
    }
  }
  return { resolved, errors };
}

function resolveInterfacePatches(interfaceContact, atoms) {
  if (atoms?.format !== "mmcif") {
    const patch1 = resolvePatch(atoms?.tokenIndex, interfaceContact.patch1);
    const patch2 = resolvePatch(atoms?.tokenIndex, interfaceContact.patch2);
    return patch1.errors.length || patch2.errors.length
      ? { error: [...patch1.errors, ...patch2.errors].join(", ") }
      : { patch1: patch1.resolved, patch2: patch2.resolved, namespace: "pdb" };
  }

  const attempts = [];
  for (const [label, namespace] of [["author", atoms.author], ["label", atoms.label]]) {
    const patch1 = resolvePatch(namespace.tokenIndex, interfaceContact.patch1);
    const patch2 = resolvePatch(namespace.tokenIndex, interfaceContact.patch2);
    if (!patch1.errors.length && !patch2.errors.length) {
      return { patch1: patch1.resolved, patch2: patch2.resolved, namespace: label };
    }
    attempts.push(`${label} namespace: ${[...patch1.errors, ...patch2.errors].join(", ")}`);
  }
  return {
    error: `Unable to resolve interface patches entirely in the author or label namespace. ${attempts.join("; ")}`
  };
}

function measureInterfaceContact(interfaceContact, atoms, model) {
  const resolved = resolveInterfacePatches(interfaceContact, atoms);
  if (resolved.error) {
    return {
      model,
      status: "unresolved",
      satisfied: null,
      maximum_observed_distance: null,
      maximum_excess_distance: null,
      violated_residues: [],
      residue_restraints: [],
      unresolved_reason: resolved.error
    };
  }

  const residueRestraints = [];
  for (const [patchName, oppositeName] of [["patch1", "patch2"], ["patch2", "patch1"]]) {
    const targetAtoms = resolved[oppositeName].flatMap((entry) => entry.atoms);
    for (const source of resolved[patchName]) {
      const closest = closestAtomPair(source.atoms, targetAtoms);
      const observed = roundDistance(closest.distance);
      const excess = roundDistance(Math.max(0, closest.distance - interfaceContact.max_distance));
      const satisfied = closest.distance <= interfaceContact.max_distance;
      residueRestraints.push({
        patch: patchName,
        chain: source.chain,
        residue: source.residue,
        opposite_patch: oppositeName,
        status: satisfied ? "satisfied" : "violated",
        observed_distance: observed,
        excess_distance: excess,
        satisfied,
        closest_source_atom: measuredAtomLabel(closest.atom1),
        closest_opposite_atom: measuredAtomLabel(closest.atom2)
      });
    }
  }
  const violated = residueRestraints.filter((measurement) => !measurement.satisfied);
  return {
    model,
    status: violated.length ? "violated" : "satisfied",
    satisfied: violated.length === 0,
    maximum_observed_distance: roundDistance(
      Math.max(...residueRestraints.map((measurement) => measurement.observed_distance))
    ),
    maximum_excess_distance: roundDistance(
      Math.max(...residueRestraints.map((measurement) => measurement.excess_distance))
    ),
    violated_residues: violated.map((measurement) => (
      `${measurement.chain}:${measurement.residue}`
    )),
    residue_restraints: residueRestraints,
    unresolved_reason: null
  };
}

function measureTokenContact(contact, atoms, model) {
  const first = tokenEndpoint(contact, 1);
  const second = tokenEndpoint(contact, 2);
  let resolved;
  if (atoms?.format === "mmcif") {
    resolved = resolveMmcifTokenPair(atoms, first, second);
  } else {
    const resolved1 = resolveTokenEndpoint(atoms?.tokenIndex, first);
    const resolved2 = resolveTokenEndpoint(atoms?.tokenIndex, second);
    resolved = resolved1.atoms && resolved2.atoms
      ? { atoms1: resolved1.atoms, atoms2: resolved2.atoms, namespace: "pdb" }
      : {
        error: `Unable to resolve token-contact pair ${tokenEndpointText(first)} <-> ${tokenEndpointText(second)}. ${
          [resolved1.error, resolved2.error].filter(Boolean).join(", ")
        }`
      };
  }
  if (resolved.error) {
    return {
      model,
      status: "unresolved",
      observed_distance: null,
      excess_distance: null,
      satisfied: null,
      closest_atom1: null,
      closest_atom2: null,
      unresolved_reason: resolved.error
    };
  }

  const closest = closestAtomPair(resolved.atoms1, resolved.atoms2);
  if (!closest) {
    return {
      model,
      status: "unresolved",
      observed_distance: null,
      excess_distance: null,
      satisfied: null,
      closest_atom1: null,
      closest_atom2: null,
      unresolved_reason: "No atom pairs were available for the resolved token-contact endpoints."
    };
  }
  const observed = roundDistance(closest.distance);
  const excess = roundDistance(Math.max(0, closest.distance - contact.max_distance));
  const satisfied = closest.distance <= contact.max_distance;
  return {
    model,
    status: satisfied ? "satisfied" : "violated",
    observed_distance: observed,
    excess_distance: excess,
    satisfied,
    closest_atom1: measuredAtomLabel(closest.atom1),
    closest_atom2: measuredAtomLabel(closest.atom2),
    unresolved_reason: null
  };
}

function summarizeUnionMeasurements(measurements, model) {
  const satisfiedAlternatives = measurements
    .filter((measurement) => measurement.satisfied === true)
    .map((measurement) => measurement.alternative_index);
  const resolved = measurements.filter((measurement) => measurement.satisfied !== null);
  const unresolved = measurements.filter((measurement) => measurement.satisfied === null);
  const best = resolved.reduce((current, measurement) => {
    if (!current || measurement.excess_distance < current.excess_distance) return measurement;
    if (
      measurement.excess_distance === current.excess_distance
      && measurement.observed_distance < current.observed_distance
    ) return measurement;
    return current;
  }, null);
  const satisfied = satisfiedAlternatives.length
    ? true
    : unresolved.length === 0
      ? false
      : null;
  const status = satisfied === true
    ? "satisfied"
    : satisfied === false
      ? "violated"
      : resolved.length
        ? "indeterminate"
        : "unresolved";
  return {
    model,
    status,
    satisfied,
    satisfying_alternatives: satisfiedAlternatives,
    best_alternative_index: best?.alternative_index ?? null,
    best_observed_distance: best?.observed_distance ?? null,
    minimum_excess_distance: best?.excess_distance ?? null,
    unresolved_alternatives: unresolved.map((measurement) => measurement.alternative_index),
    unresolved_reason: unresolved.length
      ? unresolved.map((measurement) => (
        `Alternative ${measurement.alternative_index}: ${measurement.unresolved_reason}`
      )).join("; ")
      : null
  };
}

function measureUnionGroup(group, atoms, model) {
  const measurements = group.alternatives.map((alternative, index) => ({
    alternative_index: alternative.alternative_index || index + 1,
    ...measureStructure(alternative, atoms, model)
  }));
  return {
    measurements,
    summary: summarizeUnionMeasurements(measurements, model)
  };
}

function summarizeValues(values) {
  if (!values.length) return { mean: null, maximum: null };
  return {
    mean: roundDistance(values.reduce((sum, value) => sum + value, 0) / values.length),
    maximum: roundDistance(Math.max(...values))
  };
}

function summarizeModelAudit(
  model,
  measuredRestraints,
  measuredUnionGroups,
  measuredTokenContacts = [],
  measuredInterfaceContacts = []
) {
  const exact = measuredRestraints
    .map((restraint) => restraint.models.find((measurement) => measurement.model === model))
    .filter(Boolean);
  const unions = measuredUnionGroups
    .map((group) => group.models.find((measurement) => measurement.model === model))
    .filter(Boolean);
  const tokens = measuredTokenContacts
    .map((contact) => contact.models.find((measurement) => measurement.model === model))
    .filter(Boolean);
  const interfaces = measuredInterfaceContacts
    .map((item) => item.models.find((measurement) => measurement.model === model))
    .filter(Boolean);
  const exactResolved = exact.filter((measurement) => measurement.satisfied !== null);
  const exactViolated = exactResolved.filter((measurement) => measurement.satisfied === false);
  const unionConclusive = unions.filter((measurement) => measurement.satisfied !== null);
  const unionViolated = unionConclusive.filter((measurement) => measurement.satisfied === false);
  const tokenResolved = tokens.filter((measurement) => measurement.satisfied !== null);
  const tokenViolated = tokenResolved.filter((measurement) => measurement.satisfied === false);
  const exactExcess = summarizeValues(exactResolved.map((measurement) => measurement.excess_distance));
  const exactViolationExcess = summarizeValues(
    exactViolated.map((measurement) => measurement.excess_distance)
  );
  const unionExcess = summarizeValues(
    unionConclusive.map((measurement) => measurement.minimum_excess_distance)
  );
  const unionViolationExcess = summarizeValues(
    unionViolated.map((measurement) => measurement.minimum_excess_distance)
  );
  const tokenExcess = summarizeValues(tokenResolved.map((measurement) => measurement.excess_distance));
  const tokenViolationExcess = summarizeValues(
    tokenViolated.map((measurement) => measurement.excess_distance)
  );
  const interfaceResolved = interfaces.filter((measurement) => measurement.satisfied !== null);
  const interfaceViolated = interfaceResolved.filter((measurement) => measurement.satisfied === false);
  const interfaceExcess = summarizeValues(
    interfaceResolved.map((measurement) => measurement.maximum_excess_distance)
  );
  return {
    model,
    token: {
      total: tokens.length,
      resolved: tokenResolved.length,
      satisfied: tokenResolved.filter((measurement) => measurement.satisfied === true).length,
      violated: tokenViolated.length,
      unresolved: tokens.filter((measurement) => measurement.satisfied === null).length,
      satisfaction_fraction_of_resolved: tokenResolved.length
        ? tokenResolved.filter((measurement) => measurement.satisfied === true).length / tokenResolved.length
        : null,
      mean_excess_distance: tokenExcess.mean,
      mean_violation_excess_distance: tokenViolationExcess.mean,
      maximum_excess_distance: tokenExcess.maximum
    },
    interface: {
      total: interfaces.length,
      resolved: interfaceResolved.length,
      satisfied: interfaceResolved.filter((measurement) => measurement.satisfied === true).length,
      violated: interfaceViolated.length,
      unresolved: interfaces.filter((measurement) => measurement.satisfied === null).length,
      satisfaction_fraction_of_resolved: interfaceResolved.length
        ? interfaceResolved.filter((measurement) => measurement.satisfied === true).length
          / interfaceResolved.length
        : null,
      mean_maximum_excess_distance: interfaceExcess.mean,
      maximum_excess_distance: interfaceExcess.maximum
    },
    exact: {
      total: exact.length,
      resolved: exactResolved.length,
      satisfied: exactResolved.filter((measurement) => measurement.satisfied === true).length,
      violated: exactViolated.length,
      unresolved: exact.filter((measurement) => measurement.satisfied === null).length,
      satisfaction_fraction_of_resolved: exactResolved.length
        ? exactResolved.filter((measurement) => measurement.satisfied === true).length / exactResolved.length
        : null,
      mean_excess_distance: exactExcess.mean,
      mean_violation_excess_distance: exactViolationExcess.mean,
      maximum_excess_distance: exactExcess.maximum
    },
    union: {
      total: unions.length,
      conclusive: unionConclusive.length,
      satisfied: unionConclusive.filter((measurement) => measurement.satisfied === true).length,
      violated: unionViolated.length,
      indeterminate: unions.filter((measurement) => measurement.status === "indeterminate").length,
      unresolved: unions.filter((measurement) => measurement.status === "unresolved").length,
      satisfaction_fraction_of_conclusive: unionConclusive.length
        ? unionConclusive.filter((measurement) => measurement.satisfied === true).length / unionConclusive.length
        : null,
      mean_minimum_excess_distance: unionExcess.mean,
      mean_violation_excess_distance: unionViolationExcess.mean,
      maximum_minimum_excess_distance: unionExcess.maximum
    }
  };
}

function modelName(filePath) {
  const stem = path.basename(filePath, path.extname(filePath));
  const match = stem.match(/model_(\d+)(?:_(addh_energy_min|addh))?/);
  return match ? `model_${match[1]}${match[2] ? `_${match[2]}` : ""}` : stem;
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

async function createRestraintReport(
  resultDirectory,
  restraints,
  unionGroups = [],
  tokenContacts = [],
  interfaceContacts = []
) {
  const structures = [
    ...await findStructureFiles(path.join(resultDirectory, "predictions")),
    ...await findStructureFiles(path.join(resultDirectory, "postprocessed"))
  ].sort();
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
  const measuredRestraints = restraints.map((restraint) => ({
    ...restraint,
    models: parsedStructures.map((structure) => measureStructure(restraint, structure.atoms, structure.model))
  }));
  const measuredTokenContacts = tokenContacts.map((contact) => ({
    ...contact,
    models: parsedStructures.map((structure) => (
      measureTokenContact(contact, structure.atoms, structure.model)
    ))
  }));
  const measuredUnionGroups = unionGroups.map((group, index) => {
    const measurementsByStructure = parsedStructures.map((structure) => (
      measureUnionGroup(group, structure.atoms, structure.model)
    ));
    return {
      group_index: group.group_index || index + 1,
      force: group.force === true,
      alternatives: group.alternatives.map((alternative, alternativeIndex) => ({
        ...alternative,
        alternative_index: alternative.alternative_index || alternativeIndex + 1,
        models: measurementsByStructure.map((measurement) => (
          measurement.measurements[alternativeIndex]
        ))
      })),
      models: measurementsByStructure.map((measurement) => measurement.summary)
    };
  });
  const measuredInterfaceContacts = interfaceContacts.map((interfaceContact, index) => ({
    ...interfaceContact,
    interface_index: interfaceContact.interface_index || index + 1,
    models: parsedStructures.map((structure) => (
      measureInterfaceContact(interfaceContact, structure.atoms, structure.model)
    ))
  }));
  return {
    schema_version: 5,
    generated_at: new Date().toISOString(),
    result_directory: resultDirectory,
    structures_examined: parsedStructures.map((structure) => ({
      model: structure.model,
      format: structure.format,
      file: path.basename(structure.path)
    })),
    model_summaries: parsedStructures.map((structure) => (
      summarizeModelAudit(
        structure.model,
        measuredRestraints,
        measuredUnionGroups,
        measuredTokenContacts,
        measuredInterfaceContacts
      )
    )),
    token_contacts: measuredTokenContacts,
    interface_contacts: measuredInterfaceContacts,
    restraints: measuredRestraints,
    union_groups: measuredUnionGroups
  };
}

async function writeRestraintReport(
  resultDirectory,
  restraints,
  unionGroups = [],
  tokenContacts = [],
  interfaceContacts = []
) {
  const report = await createRestraintReport(
    resultDirectory,
    restraints,
    unionGroups,
    tokenContacts,
    interfaceContacts
  );
  const reportPath = path.join(resultDirectory, "contact_restraints.json");
  await writeJson(reportPath, report);
  return { report, reportPath };
}

module.exports = {
  createRestraintReport,
  findStructureFiles,
  measureStructure,
  measureInterfaceContact,
  measureTokenContact,
  measureUnionGroup,
  parseMmcif,
  parsePdb,
  summarizeModelAudit,
  writeRestraintReport
};
