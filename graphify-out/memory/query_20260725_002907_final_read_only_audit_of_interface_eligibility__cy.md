---
type: "query"
date: "2026-07-25T00:29:07.685042+00:00"
question: "Final read-only audit of interface eligibility, cyclic closure, crop fail-fast, schema 8 report semantics, mathematical potential, and native token isolation"
contributor: "graphify"
outcome: "useful"
source_nodes: ["measureInterfaceContact()", "restraint-report.js"]
---

# Q: Final read-only audit of interface eligibility, cyclic closure, crop fail-fast, schema 8 report semantics, mathematical potential, and native token isolation

## Answer

Expanded from original query via graph vocab: [interface, contact, validate, validation, report, token, gradient, potentials, force, restraint, atom, residue]. Traversal anchored at measureInterfaceContact() and restraint-report.js; live-source verification was required because the graph predates final edits. One blocker was found and fixed during audit: PredictionDataset swallowed interface featurizer ValueErrors and recursively substituted record 0. The final patch now re-raises when interface_contact_constraints is nonempty, preserves native-only fallback behavior, verifies an applied-state marker, and has a dataset __getitem__ regression. After that fix, no remaining release-blocking code issue was found: reciprocal literal hard-min Huber math is unchanged, native contact tensors/source remain isolated, per-residue/cyclic/crop validation is coherent, and schema-8 report/UI semantics distinguish existential patch contact from strict active-residue coverage.

## Outcome

- Signal: useful

## Source Nodes

- measureInterfaceContact()
- restraint-report.js