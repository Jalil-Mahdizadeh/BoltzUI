"use strict";

const YAML = require("yaml");
const { validateAtomContacts } = require("./atom-contact");

function mapping(value, allowed, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} must be a mapping.`);
  const unsupported = Object.keys(value).filter((key) => !allowed.includes(key));
  if (unsupported.length) throw new Error(`${label} contains fields the builder cannot preserve: ${unsupported.join(", ")}. Edit this input in the YAML editor.`);
  return value;
}

function list(value, label) {
  if (!Array.isArray(value)) throw new Error(`${label} must be a list.`);
  return value;
}

function text(value, fallback = "") {
  if (value === undefined || value === null) return fallback;
  if (typeof value === "object") throw new Error("Expected a scalar field in the builder input.");
  return String(value);
}

function ids(value) { return (Array.isArray(value) ? value : [value]).map((item) => text(item)).join(", "); }
function endpoint(value, count) {
  if (list(value, "Constraint endpoint").length !== count) throw new Error(`Constraint endpoint must have ${count} entries.`);
  return value.map((item) => text(item)).join(":");
}
function forced(value) {
  if (value !== undefined && typeof value !== "boolean") throw new Error("force and cyclic must be booleans.");
  return value === true;
}

function parseBuilderYaml(content) {
  const document = mapping(YAML.parse(content), ["version", "sequences", "constraints", "templates", "properties"], "Input");
  if (document.version !== 1) throw new Error("The builder supports version: 1 inputs.");
  const parsed = { polymers: [], ligands: [], pockets: [], interfaceContacts: [], contacts: [], atomContacts: [], atomContactUnions: [], bonds: [], templates: [], affinity: null, warnings: [] };
  for (const wrapper of list(document.sequences, "sequences")) {
    mapping(wrapper, ["protein", "rna", "dna", "ligand"], "Sequence");
    if (Object.keys(wrapper).length !== 1) throw new Error("Each sequence must contain one entity.");
    const [type, value] = Object.entries(wrapper)[0];
    if (type === "ligand") {
      mapping(value, ["id", "ccd", "smiles"], "Ligand");
      if ((value.ccd !== undefined) === (value.smiles !== undefined)) throw new Error("Ligand needs either ccd or smiles.");
      const source = value.ccd === undefined ? "smiles" : "ccd";
      parsed.ligands.push({ ids: ids(value.id), source, value: source === "ccd" ? ids(value.ccd) : text(value.smiles) });
    } else {
      mapping(value, ["id", "sequence", "msa", "cyclic", "modifications"], "Polymer");
      const msa = text(value.msa);
      parsed.polymers.push({ type, ids: ids(value.id), sequence: text(value.sequence), msaMode: msa ? (msa === "empty" ? "empty" : "custom") : "auto", msaPath: msa === "empty" ? "" : msa, cyclic: forced(value.cyclic), modifications: list(value.modifications || [], "modifications").map((mod) => {
        mapping(mod, ["position", "ccd"], "Modification");
        return `${text(mod.position)}:${text(mod.ccd)}`;
      }).join("\n") });
    }
  }
  // The current builder always emits at least one polymer; protect ligand-only
  // documents instead of silently adding a new entity on the first edit.
  if (!parsed.polymers.length) throw new Error("This input has no polymers and must be edited in the YAML editor.");
  for (const wrapper of list(document.constraints || [], "constraints")) {
    mapping(wrapper, ["contact", "pocket", "interface_contact", "atom_contact", "atom_contact_union", "bond"], "Constraint");
    if (Object.keys(wrapper).length !== 1) throw new Error("Each constraint must contain one constraint type.");
    const [type, item] = Object.entries(wrapper)[0];
    const fields = {
      contact: ["token1", "token2", "max_distance", "force"],
      pocket: ["binder", "contacts", "max_distance", "force"],
      interface_contact: ["patch1", "patch2", "max_distance", "force"],
      atom_contact: ["atom1", "atom2", "max_distance", "force"],
      atom_contact_union: ["alternatives", "force"],
      bond: ["atom1", "atom2"]
    };
    mapping(item, fields[type], type);
    const common = { distance: text(item.max_distance, "6"), force: forced(item.force) };
    if (type === "contact") parsed.contacts.push({ ...common, token1: endpoint(item.token1, 2), token2: endpoint(item.token2, 2) });
    if (type === "bond") parsed.bonds.push({ atom1: endpoint(item.atom1, 3), atom2: endpoint(item.atom2, 3) });
    if (type === "pocket") parsed.pockets.push({ ...common, binder: text(item.binder), contacts: list(item.contacts, "pocket contacts").map((entry) => endpoint(entry, 2)).join("\n") });
    if (type === "interface_contact") {
      for (const patch of [item.patch1, item.patch2]) mapping(patch, ["chain", "residues"], "Interface patch");
      parsed.interfaceContacts.push({ ...common, patch1Chain: text(item.patch1.chain), patch2Chain: text(item.patch2.chain), patch1Residues: list(item.patch1.residues, "patch1 residues").join("\n"), patch2Residues: list(item.patch2.residues, "patch2 residues").join("\n") });
    }
    if (type === "atom_contact_union") for (const alternative of list(item.alternatives, "alternatives")) mapping(alternative, ["atom1", "atom2", "max_distance"], "Union alternative");
  }
  const { restraints, unionGroups } = validateAtomContacts(document, { validateChains: false });
  const atomFields = (item) => ({ atom1: `${item.chain1}:${item.residue1}:${item.atom1}`, atom2: `${item.chain2}:${item.residue2}:${item.atom2}`, distance: String(item.max_distance) });
  parsed.atomContacts = restraints.map((item) => ({ ...atomFields(item), force: item.force }));
  parsed.atomContactUnions = unionGroups.map((group) => ({ force: group.force, alternatives: group.alternatives.map(atomFields) }));
  for (const item of list(document.templates || [], "templates")) {
    mapping(item, ["cif", "pdb", "chain_id", "template_id", "force", "threshold"], "Template");
    if ((item.cif !== undefined) === (item.pdb !== undefined)) throw new Error("Template needs either cif or pdb.");
    const format = item.cif === undefined ? "pdb" : "cif";
    parsed.templates.push({ format, path: text(item[format]), chainIds: ids(item.chain_id), templateIds: item.template_id === undefined ? "" : ids(item.template_id), force: forced(item.force), threshold: text(item.threshold, "2") });
  }
  for (const item of list(document.properties || [], "properties")) {
    mapping(item, ["affinity"], "Property");
    mapping(item.affinity, ["binder"], "Affinity");
    if (parsed.affinity) throw new Error("Multiple affinity properties must be edited in the YAML editor.");
    parsed.affinity = { enabled: true, binder: text(item.affinity.binder) };
  }
  return parsed;
}

module.exports = { parseBuilderYaml };
