"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { analyzePostprocessEligibility } = require("../lib/postprocess-eligibility");

test("standard protein, RNA, and DNA polymers are eligible", () => {
  const result = analyzePostprocessEligibility({
    sequences: [
      { protein: { id: "A", sequence: "ACDEFGHIKLMNPQRSTVWY" } },
      { rna: { id: "B", sequence: "ACGU" } },
      { dna: { id: "C", sequence: "ACGT" } }
    ]
  });
  assert.deepEqual(result, { eligible: true, reason: null });
});

test("ligands disable hydrogen postprocessing with a useful reason", () => {
  const result = analyzePostprocessEligibility({
    sequences: [
      { protein: { id: "A", sequence: "M" } },
      { ligand: { id: "L", ccd: "ZN" } }
    ]
  });
  assert.equal(result.eligible, false);
  assert.match(result.reason, /ligand chain L/);
  assert.match(result.reason, /Only unmodified, non-cyclic standard protein, RNA, and DNA/);
});

test("modified, cyclic, and non-standard polymers report every incompatibility", () => {
  const result = analyzePostprocessEligibility({
    sequences: [
      { protein: { id: "A", sequence: "MU", modifications: [{ position: 2, ccd: "SEC" }] } },
      { rna: { id: "B", sequence: "ACGN", cyclic: true } }
    ]
  });
  assert.equal(result.eligible, false);
  assert.match(result.reason, /modified residue \(SEC\)/);
  assert.match(result.reason, /non-standard sequence symbol U/);
  assert.match(result.reason, /rna chain B is cyclic/);
  assert.match(result.reason, /non-standard sequence symbol N/);
});

test("unknown sequence entity types cannot silently pass eligibility", () => {
  const result = analyzePostprocessEligibility({ sequences: [{ carbohydrate: { id: "G" } }] });
  assert.equal(result.eligible, false);
  assert.match(result.reason, /carbohydrate chain G/);
});
