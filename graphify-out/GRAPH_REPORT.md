# Graph Report - BoltzUI  (2026-07-05)

## Corpus Check
- 9 files · ~86,327 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 218 nodes · 370 edges · 9 communities (7 shown, 2 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3f725dd1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 20|Community 20]]

## God Nodes (most connected - your core abstractions)
1. `$()` - 54 edges
2. `$()` - 44 edges
3. `buildYamlFromBuilder()` - 16 edges
4. `handleApi()` - 13 edges
5. `BoltzUI` - 10 edges
6. `renderModelTable()` - 9 edges
7. `refreshAll()` - 9 edges
8. `renderOverview()` - 8 edges
9. `renderResults()` - 8 edges
10. `resultsForSelectedInput()` - 7 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Import Cycles
- None detected.

## Communities (9 total, 2 thin omitted)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (47): addLog(), appendPredictOptions(), buildBoltzCommand(), contentType(), EventEmitter, findFiles(), fs, fsp (+39 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (46): $(), api(), applyViewerStyle(), basename(), clamp(), clearViewer(), colorStyle(), createOptionGrid() (+38 more)

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
Cohesion: 0.10
Nodes (41): $(), api(), appendPolymerYaml(), applyYamlPreset(), bindBuilderPage(), bindRepeatLists(), builderState, buildYamlFromBuilder() (+33 more)

### Community 13 - "Community 13"
Cohesion: 0.40
Nodes (4): Build input, GPU memory, Host system, Requirements

## Knowledge Gaps
- **49 isolated node(s):** `name`, `version`, `private`, `description`, `start` (+44 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `name`, `version`, `private` to the rest of the system?**
  _49 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05714285714285714 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.07102040816326531 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.08925979680696662 - nodes in this community are weakly interconnected._
- **Should `Community 8` be split into smaller, more focused modules?**
  _Cohesion score 0.10299003322259136 - nodes in this community are weakly interconnected._