"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { createJsonCache, selectAuditModel } = require("../lib/result-cache");

test("JSON cache reuses unchanged files, invalidates edits and bounds retained entries", async (t) => {
  const directory = await fsp.mkdtemp(path.join(os.tmpdir(), "boltz-cache-"));
  t.after(() => fsp.rm(directory, { recursive: true, force: true }));
  const file = path.join(directory, "report.json");
  const other = path.join(directory, "other.json");
  const read = createJsonCache({ maxEntries: 1 });
  await fsp.writeFile(file, '{"value":1}');
  const first = await read(file);
  assert.equal(await read(file), first);
  await fsp.writeFile(file, '{"value":22}');
  const edited = await read(file);
  assert.deepEqual(edited, { value: 22 });
  assert.notEqual(edited, first);
  await fsp.writeFile(other, "{}");
  await read(other);
  assert.notEqual(await read(file), edited);
  await fsp.unlink(file);
  assert.equal(await read(file), null);
});

test("model audit payload omits other model measurements without mutating full report", () => {
  const models = [{ model: "model_0", satisfied: true }, { model: "model_1", satisfied: false }];
  const report = { restraints: [{ models }], union_groups: [{ models, alternatives: [{ atom1: "CA", models }] }], model_summaries: models };
  const selected = selectAuditModel(report, "model_1");
  assert.deepEqual(selected.restraints[0].models, [models[1]]);
  assert.deepEqual(selected.model_summaries, [models[1]]);
  assert.equal(selected.union_groups[0].alternatives[0].models, undefined);
  assert.equal(report.union_groups[0].alternatives[0].models.length, 2);
});
