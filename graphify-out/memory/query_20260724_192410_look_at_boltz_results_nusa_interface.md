---
type: "query"
date: "2026-07-24T19:24:10.953992+00:00"
question: "look at boltz_results_NusA_interface"
contributor: "graphify"
outcome: "useful"
source_nodes: ["measureInterfaceContact()", "writeRestraintReport()", "restraint-report.js"]
---

# Q: look at boltz_results_NusA_interface

## Answer

Expanded from original query via graph vocab: [interface, restraint, report, result, models, prediction, distance, satisfied, contact, structure, manifest, pdb]. The run succeeded technically and all 10 models contain at least one patch-to-patch contact within 6 A, but zero models satisfy the implemented reciprocal per-active-residue criterion. Mean coverage is 152/280 residue restraints (54.3%); model_6 is best at 20/28, while model_8 has the best worst-case distance at 10.196 A. Seven models contain a cross-patch heavy-atom distance below 2 A and three below 1 A, so the result is not yet scientifically clean.

## Outcome

- Signal: useful

## Source Nodes

- measureInterfaceContact()
- writeRestraintReport()
- restraint-report.js