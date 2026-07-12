# Graph Report - BoltzUI  (2026-07-12)

## Corpus Check
- 63 files · ~86,592 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 448 nodes · 835 edges · 26 communities (12 shown, 14 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b5e35560`
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

## God Nodes (most connected - your core abstractions)
1. `$()` - 88 edges
2. `$()` - 66 edges
3. `handleApi()` - 18 edges
4. `buildYamlFromBuilder()` - 17 edges
5. `applyParsedYamlToBuilder()` - 14 edges
6. `preparePrediction()` - 13 edges
7. `applyYamlPreset()` - 12 edges
8. `refreshAll()` - 11 edges
9. `parseYamlConstraints()` - 11 edges
10. `stripYamlQuotes()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `preparePrediction()` --calls--> `validateAtomContacts()`  [EXTRACTED]
  server.js → lib/atom-contact.js
- `preparePrediction()` --calls--> `inputMsaSummary()`  [EXTRACTED]
  server.js → lib/atom-contact.js
- `preparePrediction()` --calls--> `resolvePredictionOptions()`  [EXTRACTED]
  server.js → lib/prediction-config.js
- `handleApi()` --calls--> `publicPresets()`  [EXTRACTED]
  server.js → lib/prediction-config.js
- `startJob()` --calls--> `createRunManifest()`  [EXTRACTED]
  server.js → lib/run-manifest.js

## Import Cycles
- None detected.

## Communities (26 total, 14 thin omitted)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (64): documentHasAtomContacts(), parseInputFile(), addLog(), appendPredictOptions(), buildBoltzCommand(), { completeRunManifest, createRunManifest, writeJson }, contentType(), {
  DEFAULT_PRESET,
  optionSchema,
  publicPresets,
  resolvePredictionOptions
} (+56 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (59): $(), api(), applyPreset(), applySelectedInputDefaults(), applyViewerStyle(), basename(), clamp(), clearViewer() (+51 more)

### Community 3 - "Community 3"
Cohesion: 0.26
Nodes (20): boolFromYamlValue(), parseBuilderYaml(), parseInlineYamlValue(), parseYamlConstraints(), parseYamlItemMapping(), parseYamlModifications(), parseYamlProperties(), parseYamlSequences() (+12 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (14): dependencies, yaml, description, engines, node, name, private, scripts (+6 more)

### Community 5 - "Community 5"
Cohesion: 0.14
Nodes (13): BoltzUI, Build The Image, Constraint Types, GPU Guidance, Laptop GPU Length Boundary, Laptop Smoke Benchmark, Prediction Options, Prediction Presets (+5 more)

### Community 7 - "Community 7"
Cohesion: 0.22
Nodes (8): Build From Source, Docker Hub Description, Highlights, Overview, Prediction Presets, Quick Start, Short Description, VRAM Note

### Community 8 - "Community 8"
Cohesion: 0.07
Nodes (65): $(), api(), appendPolymerYaml(), applyParsedYamlToBuilder(), applyYamlPreset(), atomContactCard(), bindBuilderPage(), bindRepeatLists() (+57 more)

### Community 13 - "Community 13"
Cohesion: 0.33
Nodes (5): Build input, GPU memory, Host system, Prediction presets, Requirements

### Community 19 - "Community 19"
Cohesion: 0.56
Nodes (11): check_compatibility(), main(), patch_featurizerv2(), patch_inferencev2(), patch_schema(), patch_types(), replace_once(), source_sha256() (+3 more)

### Community 22 - "Community 22"
Cohesion: 0.07
Nodes (41): defaultOptions(), METHOD_CHOICES, normalizeOptions(), normalizeScalar(), optionSchema, presetById(), presets, publicPresets() (+33 more)

### Community 23 - "Community 23"
Cohesion: 0.12
Nodes (30): addMmcifAtom(), atomKey(), createMmcifNamespace(), createRestraintReport(), endpoint(), endpointText(), findStructureFiles(), fsp (+22 more)

### Community 24 - "Community 24"
Cohesion: 0.13
Nodes (20): AtomContactValidationError, buildChainIndex(), canonicalPair(), endpointLabel(), entityIds(), fs, inputMsaSummary(), normalizeEndpoint() (+12 more)

## Knowledge Gaps
- **120 isolated node(s):** `fs`, `path`, `YAML`, `fsp`, `path` (+115 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `$()` connect `Community 8` to `Community 3`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Why does `path` connect `Community 19` to `Community 1`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **What connects `fs`, `path`, `YAML` to the rest of the system?**
  _120 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05714285714285714 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.056189640035118525 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.07596153846153846 - nodes in this community are weakly interconnected._
- **Should `Community 4` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._