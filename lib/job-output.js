"use strict";

const fsp = require("node:fs/promises");
const path = require("node:path");

// A run starts with an empty result directory. Keep previous and failed output
// together so neither a failed prediction nor a smaller rerun mixes generations.
async function prepareJobOutput(directory, id, override) {
  const history = path.join(path.dirname(directory), ".boltzui-history", path.basename(directory), id);
  const previous = path.join(history, "previous");
  let exists = false;
  try {
    await fsp.stat(directory);
    exists = true;
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  if (exists && !override) {
    throw new Error("This result directory already exists. Enable Override existing or choose another output directory to start a new run.");
  }
  if (exists) {
    await fsp.mkdir(history, { recursive: true });
    await fsp.rename(directory, previous);
  }
  return { directory, history, previous: exists ? previous : null };
}

async function finishJobOutput(output, succeeded) {
  if (succeeded) return output.directory;
  const failed = path.join(output.history, "failed");
  await fsp.mkdir(output.history, { recursive: true });
  try {
    await fsp.rename(output.directory, failed);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
    await fsp.mkdir(failed, { recursive: true });
  }
  if (output.previous) await fsp.rename(output.previous, output.directory);
  return failed;
}

module.exports = { prepareJobOutput, finishJobOutput };
