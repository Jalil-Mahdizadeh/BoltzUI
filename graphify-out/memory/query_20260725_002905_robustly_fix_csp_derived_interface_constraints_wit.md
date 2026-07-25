---
type: "query"
date: "2026-07-25T00:29:05.690432+00:00"
question: "Robustly fix CSP-derived interface constraints without changing the native token-constraint pipeline"
contributor: "graphify"
outcome: "useful"
source_nodes: ["apply_interface_contact_potentials", "PredictionDataset.__getitem__", "validateInterfaceContacts()", "measureInterfaceContact()"]
---

# Q: Robustly fix CSP-derived interface constraints without changing the native token-constraint pipeline

## Answer

Implemented reciprocal literal-heavy-atom per-active-residue guidance with normalized Huber loss and local clash protection; aligned builder, server, Boltz schema, cyclic topology, crop fail-fast behavior, reporting, partial/strict UI semantics, and PredictionDataset error propagation; preserved native token fingerprints; validated on NusA and in the final Docker test suites.

## Outcome

- Signal: useful

## Source Nodes

- apply_interface_contact_potentials
- PredictionDataset.__getitem__
- validateInterfaceContacts()
- measureInterfaceContact()