# Graph Report - BoltzUI  (2026-07-19)

## Corpus Check
- 99 files · ~2,253,448 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 521 nodes · 967 edges · 33 communities (14 shown, 19 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c3e5c7f6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]

## God Nodes (most connected - your core abstractions)
1. `$()` - 98 edges
2. `$()` - 66 edges
3. `handleApi()` - 20 edges
4. `buildYamlFromBuilder()` - 17 edges
5. `applyParsedYamlToBuilder()` - 15 edges
6. `BoltzPatchTests` - 15 edges
7. `applyYamlPreset()` - 13 edges
8. `preparePrediction()` - 13 edges
9. `refreshAll()` - 11 edges
10. `parseYamlConstraints()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `handleApi()` --calls--> `parseInputText()`  [EXTRACTED]
  server.js → lib/atom-contact.js
- `documentFromFixture()` --calls--> `parseInputText()`  [EXTRACTED]
  tests/atom-contact.test.js → lib/atom-contact.js
- `preparePrediction()` --calls--> `parseInputFile()`  [EXTRACTED]
  server.js → lib/atom-contact.js
- `handleApi()` --calls--> `validateAtomContacts()`  [EXTRACTED]
  server.js → lib/atom-contact.js
- `preparePrediction()` --calls--> `validateAtomContacts()`  [EXTRACTED]
  server.js → lib/atom-contact.js

## Import Cycles
- None detected.

## Communities (33 total, 19 thin omitted)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (62): addLog(), appendPredictOptions(), buildBoltzCommand(), { completeRunManifest, createRunManifest, writeJson }, contentType(), {
  DEFAULT_PRESET,
  optionSchema,
  publicPresets,
  resolvePredictionOptions
}, displayPath(), {
  documentHasAtomContacts,
  inputMsaSummary,
  parseInputFile,
  parseInputText,
  validateAtomContacts
} (+54 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (59): $(), api(), applyPreset(), applySelectedInputDefaults(), applyViewerStyle(), basename(), clamp(), clearViewer() (+51 more)

### Community 3 - "Community 3"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Deeply explore he current version of the BoltzUI and fully understand it. Particularly, the 'token contact constraints' and 'atom contact constraints' workflow. Then I will ask some questions., Source Nodes

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (14): dependencies, yaml, description, engines, node, name, private, scripts (+6 more)

### Community 5 - "Community 5"
Cohesion: 0.13
Nodes (14): BoltzUI, Build The Image, Constraint Types, Diffusion Chunking Benchmark, GPU Guidance, Laptop GPU Length Boundary, Laptop Smoke Benchmark, Prediction Options (+6 more)

### Community 7 - "Community 7"
Cohesion: 0.22
Nodes (8): Build From Source, Docker Hub Description, Highlights, Overview, Prediction Presets, Quick Start, Short Description, VRAM Note

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (93): $(), api(), appendPolymerYaml(), applyParsedYamlToBuilder(), applyYamlPreset(), atomContactCard(), atomContactUnionAlternativeCard(), bindBuilderPage() (+85 more)

### Community 13 - "Community 13"
Cohesion: 0.33
Nodes (5): Build input, GPU memory, Host system, Prediction presets, Requirements

### Community 19 - "Community 19"
Cohesion: 0.54
Nodes (12): check_compatibility(), main(), patch_diffusionv2(), patch_featurizerv2(), patch_inferencev2(), patch_schema(), patch_types(), replace_once() (+4 more)

### Community 22 - "Community 22"
Cohesion: 0.07
Nodes (41): defaultOptions(), METHOD_CHOICES, normalizeOptions(), normalizeScalar(), optionSchema, presetById(), presets, publicPresets() (+33 more)

### Community 23 - "Community 23"
Cohesion: 0.11
Nodes (34): addMmcifAtom(), atomKey(), createMmcifNamespace(), createRestraintReport(), endpoint(), endpointText(), findStructureFiles(), fsp (+26 more)

### Community 24 - "Community 24"
Cohesion: 0.12
Nodes (28): AtomContactValidationError, buildChainIndex(), canonicalPair(), documentHasAtomContacts(), endpointLabel(), entityIds(), fs, inputMsaSummary() (+20 more)

### Community 26 - "Community 26"
Cohesion: 0.24
Nodes (19): arguments(), atom_priority(), compare(), contact_metrics(), coordinates(), describe(), fit(), load_predictions() (+11 more)

### Community 27 - "Community 27"
Cohesion: 0.20
Nodes (9): 9SGX exact + union atom-contact benchmark, Benchmark target, Code improvement learned from the test, Files, Limitations, Matched prediction settings, Outcome, Restraint satisfaction (+1 more)

## Knowledge Gaps
- **139 isolated node(s):** `fs`, `path`, `YAML`, `fsp`, `path` (+134 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `path` connect `Community 19` to `Community 1`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **What connects `fs`, `path`, `YAML` to the rest of the system?**
  _139 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05714285714285714 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.05687645687645688 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.0764423076923077 - nodes in this community are weakly interconnected._
- **Should `Community 4` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Should `Community 5` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._