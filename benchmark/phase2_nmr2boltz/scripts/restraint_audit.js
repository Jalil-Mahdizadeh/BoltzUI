"use strict";

const path = require("node:path");
const {
  parseInputFile,
  validateAtomContacts
} = require("/workspace/BoltzUI/lib/atom-contact");
const {
  writeRestraintReport
} = require("/workspace/BoltzUI/lib/restraint-report");

async function main() {
  if (process.argv.length !== 4) {
    throw new Error("Usage: node restraint_audit.js INPUT_YAML RESULT_DIRECTORY");
  }
  const input = path.resolve(process.argv[2]);
  const resultDirectory = path.resolve(process.argv[3]);
  const document = parseInputFile(input);
  const { restraints, unionGroups } = validateAtomContacts(document);
  const { reportPath } = await writeRestraintReport(
    resultDirectory,
    restraints,
    unionGroups
  );
  process.stdout.write(`${reportPath}\n`);
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
