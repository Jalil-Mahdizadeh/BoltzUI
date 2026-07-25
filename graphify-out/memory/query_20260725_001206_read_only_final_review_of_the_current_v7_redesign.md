---
type: "query"
date: "2026-07-25T00:12:06.767178+00:00"
question: "Read-only final review of the current v7 redesign for tests, documentation, report schema, UI consistency, stale D^-6 or minimax claims, regression coverage, and validation metrics"
contributor: "graphify"
outcome: "useful"
source_nodes: ["measureInterfaceContact()", "restraint-report.js", "restraint-report.test.js", "Validation", "Documentation"]
---

# Q: Read-only final review of the current v7 redesign for tests, documentation, report schema, UI consistency, stale D^-6 or minimax claims, regression coverage, and validation metrics

## Answer

Expanded via graph vocabulary: [interface, constraint, validation, test, yaml, schema, restraint, report, documentation, confidence, distance, atom]. BFS led to measureInterfaceContact(), restraint-report.js, and restraint-report.test.js. Findings: validation only requires one non-neighbor same-chain pair, runtime silently drops any source residue without an eligible target, while the report marks the whole interface unresolved; cyclic neighbor and explicit-bond eligibility also diverge between runtime and report. Schema 7 intentionally redefines satisfied as any patch contact, but the UI colors and sorts partial low-coverage interfaces as satisfied; existing schema 5/6 reports use satisfied for strict coverage and are mislabelled because there is no version normalization. Add per-patch/balanced coverage, legacy-schema UI tests, mixed-neighbor and cyclic/report regressions. D^-6 user-facing text is an accurate contrast to the implemented hard-min Huber loss; minimax appears only in a migration anchor. Whole-structure clash, ensemble confidence delta, and CA/local geometry are appropriate complementary metrics with bond-aware exclusions, normalized clashscore, unpaired ensemble comparisons, and domain-aware alignment.

## Outcome

- Signal: useful

## Source Nodes

- measureInterfaceContact()
- restraint-report.js
- restraint-report.test.js
- Validation
- Documentation