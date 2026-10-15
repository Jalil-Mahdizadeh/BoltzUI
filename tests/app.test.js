"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function appHarness() {
  const elements = new Map();
  let createdRows = 0;
  const element = () => ({ value: "", open: false, children: [], classList: { add() {}, remove() {} }, removeAttribute() {}, appendChild(row) { this.children.push(row); } });
  const document = {
    querySelector(selector) {
      if (!elements.has(selector)) elements.set(selector, element());
      return elements.get(selector);
    },
    createElement(tag) { if (tag === "tr") createdRows++; return element(); }
  };
  const context = vm.createContext({ document, AbortController, setTimeout, clearTimeout, URLSearchParams,
    InterfaceAuditSemantics: require("../public/interface-audit-semantics") });
  const source = fs.readFileSync(path.join(__dirname, "../public/app.js"), "utf8");
  vm.runInContext(source.slice(0, source.lastIndexOf("\nbindEvents();")), context);
  context.result = { path: "results/test", modifiedAt: "1", models: [] };
  context.selected = { index: 0, auditModel: "model_0", structurePath: "model_0.pdb" };
  vm.runInContext("currentResult = () => result; currentModel = () => selected;", context);
  return { context, elements, document, rows: () => createdRows, run: (source) => vm.runInContext(source, context) };
}

test("late structure responses and errors cannot overwrite the selected model", async () => {
  for (const failOld of [false, true]) {
    const harness = appHarness();
    const pending = [];
    harness.context.fetch = () => new Promise((resolve, reject) => pending.push({ resolve, reject }));
    harness.run("draw3DStructure = (text, path) => { state.currentStructurePath = path; }; clearViewer = () => { state.currentStructurePath = null; };");
    const old = harness.run("renderSelectedStructure()");
    harness.context.selected = { index: 1, structurePath: "model_1.pdb" };
    const current = harness.run("renderSelectedStructure()");
    pending[1].resolve({ ok: true, text: async () => "new" });
    await current;
    if (failOld) pending[0].reject(new Error("old request failed"));
    else pending[0].resolve({ ok: true, text: async () => "old" });
    await old;
    assert.equal(harness.run("state.currentStructurePath"), "model_1.pdb");
  }
});

test("collapsed audits perform no fetch or row creation; expanded audits create only 500 rows", async () => {
  const harness = appHarness();
  harness.context.result.restraintReportPath = "results/test/contact_restraints.json";
  let requests = 0;
  harness.context.fetch = async () => { requests++; throw new Error("Unexpected fetch"); };
  await harness.run("loadSelectedAudit()");
  assert.equal(requests, 0);
  assert.equal(harness.rows(), 0);
  harness.context.result.restraintReport = { schema_version: 9, restraints: Array.from({ length: 3606 }, (_, index) => ({
    chain1: "A", residue1: index + 1, atom1: "CA", chain2: "B", residue2: 1, atom2: "CA", max_distance: 4,
    models: [{ model: "model_0", status: index === 3605 ? "violated" : "satisfied", satisfied: index !== 3605, observed_distance: index === 3605 ? 5 : 3, excess_distance: index === 3605 ? 1 : 0 }]
  })) };
  harness.run("renderRestraintAudit()");
  assert.equal(harness.rows(), 500);
  const rows = harness.document.querySelector("#restraint-table-body").children;
  assert.equal(rows.length, 500);
  assert.match(rows[0].innerHTML, /A:3606:CA/);
  assert.match(harness.document.querySelector("#restraint-audit-summary").textContent, /3605\/3606/);
});
