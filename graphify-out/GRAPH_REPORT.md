# Graph Report - BoltzUI  (2026-07-05)

## Corpus Check
- 20 files · ~67,246 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 176 nodes · 277 edges · 20 communities (14 shown, 6 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8cdb262c`
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
1. `$()` - 54 edges
2. `handleApi()` - 13 edges
3. `renderModelTable()` - 9 edges
4. `refreshAll()` - 9 edges
5. `BoltzUI` - 9 edges
6. `renderOverview()` - 8 edges
7. `renderResults()` - 8 edges
8. `resultsForSelectedInput()` - 7 edges
9. `renderResultSelectors()` - 7 edges
10. `renderResultCards()` - 7 edges

## Surprising Connections (you probably didn't know these)
- `applyViewerStyle()` --calls--> `$()`  [EXTRACTED]
  public/app.js → public/app.js  _Bridges community 2 → community 11_
- `refreshAll()` --calls--> `$()`  [EXTRACTED]
  public/app.js → public/app.js  _Bridges community 2 → community 6_
- `renderModelTable()` --calls--> `$()`  [EXTRACTED]
  public/app.js → public/app.js  _Bridges community 2 → community 3_
- `renderOptionGroups()` --calls--> `$()`  [EXTRACTED]
  public/app.js → public/app.js  _Bridges community 2 → community 10_
- `renderModelTable()` --calls--> `escapeHtml()`  [EXTRACTED]
  public/app.js → public/app.js  _Bridges community 6 → community 3_

## Import Cycles
- None detected.

## Communities (20 total, 6 thin omitted)

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (20): EventEmitter, fs, fsp, http, INPUT_EXTENSIONS, JOB_DIR, jobEvents, jobs (+12 more)

### Community 2 - "Community 2"
Cohesion: 0.17
Nodes (10): $(), api(), formatDate(), loadJob(), refreshResults(), renderRunBanner(), showToast(), state (+2 more)

### Community 3 - "Community 3"
Cohesion: 0.36
Nodes (11): currentModel(), currentResult(), modelLabel(), renderModelTable(), renderResultCards(), renderResults(), renderResultSelectors(), renderSelectedStructure() (+3 more)

### Community 4 - "Community 4"
Cohesion: 0.20
Nodes (9): description, engines, node, name, private, scripts, check, start (+1 more)

### Community 5 - "Community 5"
Cohesion: 0.20
Nodes (9): BoltzUI, Build The Image, GPU Guidance, Laptop GPU Length Boundary, Laptop Smoke Benchmark, Prediction Options, Real NusA GPU Ladder, Repository Contents (+1 more)

### Community 6 - "Community 6"
Cohesion: 0.27
Nodes (10): basename(), defaultsFromSchema(), escapeHtml(), fileStem(), latestJob(), refreshAll(), renderInputs(), renderJobs() (+2 more)

### Community 7 - "Community 7"
Cohesion: 0.25
Nodes (7): Build From Source, Docker Hub Description, Highlights, Overview, Quick Start, Short Description, VRAM Note

### Community 8 - "Community 8"
Cohesion: 0.30
Nodes (12): addLog(), buildBoltzCommand(), handleApi(), listResults(), openLocalPath(), publicJob(), readBody(), safeResolve() (+4 more)

### Community 9 - "Community 9"
Cohesion: 0.50
Nodes (4): findFiles(), modelIndexFromName(), numericMetric(), summarizeResultDir()

### Community 10 - "Community 10"
Cohesion: 0.50
Nodes (5): createOptionGrid(), groupOptions(), renderOptionField(), renderOptionGroups(), renderSegmented()

### Community 11 - "Community 11"
Cohesion: 0.50
Nodes (5): applyViewerStyle(), clearViewer(), colorStyle(), draw3DStructure(), updateConfidenceLegend()

### Community 12 - "Community 12"
Cohesion: 0.40
Nodes (5): clamp(), formatNumber(), metric(), normalizeScore(), scoreCell()

### Community 13 - "Community 13"
Cohesion: 0.40
Nodes (4): Build input, GPU memory, Host system, Requirements

### Community 15 - "Community 15"
Cohesion: 0.40
Nodes (5): contentType(), isInside(), sendJson(), serveStatic(), streamJobEvents()

## Knowledge Gaps
- **47 isolated node(s):** `records`, `name`, `version`, `private`, `description` (+42 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `$()` connect `Community 2` to `Community 3`, `Community 6`, `Community 10`, `Community 11`, `Community 12`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Why does `handleApi()` connect `Community 8` to `Community 16`, `Community 1`, `Community 15`?**
  _High betweenness centrality (0.002) - this node is a cross-community bridge._
- **What connects `records`, `name`, `version` to the rest of the system?**
  _47 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05714285714285714 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.08695652173913043 - nodes in this community are weakly interconnected._