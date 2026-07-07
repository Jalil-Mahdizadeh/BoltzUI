# Graph Report - BoltzUI  (2026-07-07)

## Corpus Check
- 50 files · ~78,033 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 282 nodes · 511 edges · 20 communities (8 shown, 12 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `faee90d7`
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
- [[_COMMUNITY_Community 20|Community 20]]

## God Nodes (most connected - your core abstractions)
1. `$()` - 78 edges
2. `$()` - 58 edges
3. `buildYamlFromBuilder()` - 16 edges
4. `handleApi()` - 16 edges
5. `parseYamlConstraints()` - 11 edges
6. `applyParsedYamlToBuilder()` - 11 edges
7. `stripYamlQuotes()` - 10 edges
8. `parseYamlSequences()` - 10 edges
9. `BoltzUI` - 10 edges
10. `renderModelTable()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `loadExistingYaml()` --calls--> `parseBuilderYaml()`  [EXTRACTED]
  public/builder.js → public/builder.js  _Bridges community 3 → community 8_

## Import Cycles
- None detected.

## Communities (20 total, 12 thin omitted)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (52): addLog(), appendPredictOptions(), buildBoltzCommand(), contentType(), ensureDataWorkspace(), EventEmitter, findFiles(), fs (+44 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (50): $(), api(), applyViewerStyle(), basename(), clamp(), clearViewer(), colorStyle(), createOptionGrid() (+42 more)

### Community 3 - "Community 3"
Cohesion: 0.25
Nodes (20): boolFromYamlValue(), parseBuilderYaml(), parseInlineYamlValue(), parseYamlConstraints(), parseYamlItemMapping(), parseYamlModifications(), parseYamlProperties(), parseYamlSequences() (+12 more)

### Community 4 - "Community 4"
Cohesion: 0.20
Nodes (9): description, engines, node, name, private, scripts, check, start (+1 more)

### Community 5 - "Community 5"
Cohesion: 0.18
Nodes (10): BoltzUI, Build The Image, GPU Guidance, Laptop GPU Length Boundary, Laptop Smoke Benchmark, Prediction Options, Real NusA GPU Ladder, Repository Contents (+2 more)

### Community 7 - "Community 7"
Cohesion: 0.25
Nodes (7): Build From Source, Docker Hub Description, Highlights, Overview, Quick Start, Short Description, VRAM Note

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (55): $(), api(), appendPolymerYaml(), applyParsedYamlToBuilder(), applyYamlPreset(), bindBuilderPage(), bindRepeatLists(), builderState (+47 more)

### Community 13 - "Community 13"
Cohesion: 0.40
Nodes (4): Build input, GPU memory, Host system, Requirements

## Knowledge Gaps
- **63 isolated node(s):** `name`, `version`, `private`, `description`, `start` (+58 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `$()` connect `Community 8` to `Community 3`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **What connects `name`, `version`, `private` to the rest of the system?**
  _63 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05714285714285714 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.06734006734006734 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.08333333333333333 - nodes in this community are weakly interconnected._
- **Should `Community 8` be split into smaller, more focused modules?**
  _Cohesion score 0.08208020050125313 - nodes in this community are weakly interconnected._