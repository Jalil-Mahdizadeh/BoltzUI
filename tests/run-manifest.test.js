"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { completeRunManifest, createRunManifest } = require("../lib/run-manifest");
const { resolvePredictionOptions } = require("../lib/prediction-config");

test("run manifest records resolved provenance and excludes credentials", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "boltzui-manifest-"));
  const inputPath = path.join(root, "input.yaml");
  fs.writeFileSync(inputPath, "version: 1\n", "utf8");
  const options = resolvePredictionOptions({
    sampling_steps: "275",
    step_scale: "1.2",
    msa_server_password: "secret"
  }, "custom").options;
  const manifest = createRunManifest({
    root,
    jobId: "test-job",
    preset: "custom",
    options,
    args: ["predict", inputPath, "--sampling_steps", "275"],
    inputPath,
    outputDirectory: "workspace/results/boltz_results_input",
    atomContacts: [],
    msa: { mode: "server", input_modes: ["auto"], server_url: "https://example.test" },
    startedAt: "2026-01-01T00:00:00.000Z",
    metadata: { boltzui_git_commit: "abc123", boltzui_git_dirty: true, boltz_version: "2.2.1" }
  });
  assert.equal(manifest.selected_preset, "custom");
  assert.equal(manifest.sampling_steps, 275);
  assert.equal(manifest.step_scale, 1.2);
  assert.equal(manifest.boltz_version, "2.2.1");
  assert.equal(manifest.boltzui_git_dirty, true);
  assert.equal(manifest.resolved_prediction_parameters.msa_server_password, undefined);
  assert.doesNotMatch(JSON.stringify(manifest), /secret/);
  assert.match(manifest.input_sha256, /^[a-f0-9]{64}$/);
  const complete = completeRunManifest(manifest, {
    endedAt: "2026-01-01T00:01:00.000Z",
    status: "failed",
    exitCode: 1,
    signal: null,
    failureReason: "fixture failure"
  });
  assert.equal(complete.exit_status, "failed");
  assert.equal(complete.completion_time, "2026-01-01T00:01:00.000Z");
  assert.equal(complete.failure_reason, "fixture failure");
});
