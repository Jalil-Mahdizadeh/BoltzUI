---
type: "query"
date: "2026-07-24T19:43:39.313930+00:00"
question: "find the unconstraint run in boltz_results_NusA_no-constraint"
contributor: "graphify"
outcome: "useful"
source_nodes: ["measureInterfaceContact()", "restraint-report.js", "Evaluation"]
---

# Q: find the unconstraint run in boltz_results_NusA_no-constraint

## Answer

Expanded query terms: control, comparison, confidence, distance, evaluation, interface, models, report, restraint, result, structure, compare. Found workspace/results/boltz_results_NusA_no-constraint as a clean matched 10-model control: same 495-aa sequence, MSA, seed, model, 400 sampling steps, 3 recycling steps, 10 diffusion samples, max parallel samples 1, step scale 1, and potentials enabled; only the interface restraint differs. Evaluating the guided patches with measureInterfaceContact gives control mean 0/28 satisfied versus guided 15.2/28; mean worst nearest-patch distance 33.285 A versus 13.124 A; mean confidence 0.802 versus 0.757. Guided improves both metrics in all 10 paired models but introduces cross-patch atom pairs below 2 A in 8/10 models (below 1 A in 3/10), versus none in control. Paired all-residue CA RMSD averages 37.286 A (range 11.243-56.320 A). Conclusion: interface guidance is active and strongly changes the ensemble, but is over-aggressive and causes global rearrangement/steric overlaps; this is a restraint-design/balancing problem rather than a missing integration.

## Outcome

- Signal: useful

## Source Nodes

- measureInterfaceContact()
- restraint-report.js
- Evaluation