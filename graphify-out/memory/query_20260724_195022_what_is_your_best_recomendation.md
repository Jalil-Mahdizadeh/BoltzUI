---
type: "query"
date: "2026-07-24T19:50:22.380774+00:00"
question: "what is your best recomendation?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["apply_interface_contact_potentials", "InterfaceContactPotentital", "measureInterfaceContact()", "validateInterfaceContacts()"]
---

# Q: what is your best recomendation?

## Answer

Expanded query terms: constraint, interface, force, guidance, contact, distance, residue, restraint, potentials, samples, measureinterfacecontact, validateinterfacecontacts. Best recommendation: do not ship current force=true interface guidance as a normal default. Keep it opt-in and experimental, with force=false/report-only as the safe default, until the potential is revised. The current featurizer creates reciprocal hard-OR groups for every source residue against every atom in the opposite patch, while the potential sums group minima. Consequently patch size increases total guidance and all CSP-active residues are treated as direct contacts, causing the NusA global refolding and clashes. Replace it with an interface-specific, size-normalized, bounded and clash-aware objective: use one residue representative (C-beta; C-alpha for glycine), reciprocal nearest-opposite distances, average rather than sum over residues, robust/capped penalties, a lower interface-specific guidance weight, and a short-range nonbonded repulsion excluding covalent same-chain neighbors. Keep max_distance but reinterpret/default it around 8 A for representative-atom guidance; retain heavy-atom distance only for posthoc reporting. Do not use raw patch-wide D^-6 alone because one accidental close pair can satisfy it and patch size changes the effective distance. Validate with matched positive/control datasets, contact coverage, confidence, global fold preservation, and clash metrics before enabling force by default.

## Outcome

- Signal: useful

## Source Nodes

- apply_interface_contact_potentials
- InterfaceContactPotentital
- measureInterfaceContact()
- validateInterfaceContacts()