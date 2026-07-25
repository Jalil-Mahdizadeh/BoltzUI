---
type: "query"
date: "2026-07-24T23:23:18.354896+00:00"
question: "Recommend a mathematically coherent, patch-size-robust interface objective that can yield literal heavy-atom max_distance satisfaction without touching native token constraints."
contributor: "graphify"
outcome: "useful"
source_nodes: ["measureInterfaceContact()", "restraint-report.js"]
---

# Q: Recommend a mathematically coherent, patch-size-robust interface objective that can yield literal heavy-atom max_distance satisfaction without touching native token constraints.

## Answer

Expanded from original query via vocab: interface contact potential constraint restraint distance energy gradient group residue atom threshold. The graph led to measureInterfaceContact() in lib/restraint-report.js:L408, whose reciprocal per-residue heavy-atom minima define literal coverage. Raw D^-6 and representative atoms cannot share that zero-set. Use exact per-active-residue heavy-atom minima, a reciprocal direction-normalized Huber hinge at the literal YAML cutoff, and non-starving gradients; report existential patch contact separately from active-residue coverage and strict full coverage.

## Outcome

- Signal: useful

## Source Nodes

- measureInterfaceContact()
- restraint-report.js