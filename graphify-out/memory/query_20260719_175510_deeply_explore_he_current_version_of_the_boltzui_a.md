---
type: "query"
date: "2026-07-19T17:55:10.380082+00:00"
question: "Deeply explore he current version of the BoltzUI and fully understand it. Particularly, the 'token contact constraints' and 'atom contact constraints' workflow. Then I will ask some questions."
contributor: "graphify"
outcome: "useful"
source_nodes: ["state", "server.js", "restraint-report.js", "parseMmcif"]
---

# Q: Deeply explore he current version of the BoltzUI and fully understand it. Particularly, the 'token contact constraints' and 'atom contact constraints' workflow. Then I will ask some questions.

## Answer

Expanded from original query via graph vocab: [token, atom, contact, constraints, validation, payload, yaml, state, server, endpoint, parse, tests]. Verified against the checked-out source and the built Boltz 2.2.1 image. The browser builder keeps separate repeatable contacts and atomContacts state, emits contact token1/token2 cards and patched atom_contact atom1/atom2 cards, and saves editable YAML through POST /api/inputs. The dashboard sends data, preset, and options to /api/command or /api/jobs. The server preflights atom_contact only, resolves presets, builds boltz predict arguments, writes provenance, runs jobs over SSE, and post-audits atom contacts. Runtime contact gives token-pair neural conditioning; force true additionally expands both tokens to Cartesian atom pairs in a soft union upper-bound potential. Patched atom_contact resolves exact atoms, adds containing-token conditioning with the minimum threshold per token pair, and adds one exact atom pair per restraint to the same potential. Contact guidance is active independently of optional FK/physical potentials. Token contacts have no BoltzUI server preflight or post-run audit; atom contacts require force true and 2-20 Angstrom, receive server and runtime validation, auto-override behavior, optional experimental preset settings, manifests, and per-model restraint reports. JS tests 22/22 and in-image Python tests 9/9 passed; patch compatibility passed.

## Outcome

- Signal: useful

## Source Nodes

- state
- server.js
- restraint-report.js
- parseMmcif