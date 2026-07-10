# Graph Report - BoltzUI  (2026-07-10)

## Corpus Check
- 148 files · ~87,121 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 323 nodes · 578 edges · 30 communities (9 shown, 21 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `172239ab`
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

## God Nodes (most connected - your core abstractions)
1. `$()` - 88 edges
2. `$()` - 60 edges
3. `buildYamlFromBuilder()` - 17 edges
4. `handleApi()` - 16 edges
5. `applyParsedYamlToBuilder()` - 14 edges
6. `applyYamlPreset()` - 12 edges
7. `parseYamlConstraints()` - 11 edges
8. `stripYamlQuotes()` - 10 edges
9. `parseYamlSequences()` - 10 edges
10. `BoltzUI` - 10 edges

## Surprising Connections (you probably didn't know these)
- `write_if_changed()` --references--> `path`  [EXTRACTED]
  patches/boltz_atom_contact/apply_atom_contact_patch.py → server.js
- `patch_schema()` --references--> `path`  [EXTRACTED]
  patches/boltz_atom_contact/apply_atom_contact_patch.py → server.js
- `patch_types()` --references--> `path`  [EXTRACTED]
  patches/boltz_atom_contact/apply_atom_contact_patch.py → server.js
- `patch_inferencev2()` --references--> `path`  [EXTRACTED]
  patches/boltz_atom_contact/apply_atom_contact_patch.py → server.js
- `patch_featurizerv2()` --references--> `path`  [EXTRACTED]
  patches/boltz_atom_contact/apply_atom_contact_patch.py → server.js

## Import Cycles
- None detected.

## Communities (30 total, 21 thin omitted)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (53): addLog(), appendPredictOptions(), buildBoltzCommand(), contentType(), ensureDataWorkspace(), EventEmitter, findFiles(), fs (+45 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (53): $(), api(), applyViewerStyle(), basename(), clamp(), clearViewer(), colorStyle(), createOptionGrid() (+45 more)

### Community 3 - "Community 3"
Cohesion: 0.26
Nodes (20): boolFromYamlValue(), parseBuilderYaml(), parseInlineYamlValue(), parseYamlConstraints(), parseYamlItemMapping(), parseYamlModifications(), parseYamlProperties(), parseYamlSequences() (+12 more)

### Community 4 - "Community 4"
Cohesion: 0.20
Nodes (9): description, engines, node, name, private, scripts, check, start (+1 more)

### Community 5 - "Community 5"
Cohesion: 0.17
Nodes (11): BoltzUI, Build The Image, Constraint Types, GPU Guidance, Laptop GPU Length Boundary, Laptop Smoke Benchmark, Prediction Options, Real NusA GPU Ladder (+3 more)

### Community 7 - "Community 7"
Cohesion: 0.25
Nodes (7): Build From Source, Docker Hub Description, Highlights, Overview, Quick Start, Short Description, VRAM Note

### Community 8 - "Community 8"
Cohesion: 0.07
Nodes (65): $(), api(), appendPolymerYaml(), applyParsedYamlToBuilder(), applyYamlPreset(), atomContactCard(), bindBuilderPage(), bindRepeatLists() (+57 more)

### Community 13 - "Community 13"
Cohesion: 0.40
Nodes (4): Build input, GPU memory, Host system, Requirements

### Community 19 - "Community 19"
Cohesion: 0.69
Nodes (8): main(), patch_featurizerv2(), patch_inferencev2(), patch_schema(), patch_types(), replace_once(), write_if_changed(), path

## Knowledge Gaps
- **71 isolated node(s):** `name`, `version`, `private`, `description`, `start` (+66 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `$()` connect `Community 8` to `Community 3`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `path` connect `Community 19` to `Community 1`?**
  _High betweenness centrality (0.009) - this node is a cross-community bridge._
- **What connects `name`, `version`, `private` to the rest of the system?**
  _71 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05714285714285714 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.06688311688311688 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.08007013442431327 - nodes in this community are weakly interconnected._
- **Should `Community 8` be split into smaller, more focused modules?**
  _Cohesion score 0.06965174129353234 - nodes in this community are weakly interconnected._