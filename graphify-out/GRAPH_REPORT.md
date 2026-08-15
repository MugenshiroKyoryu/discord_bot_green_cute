# Graph Report - botdiscord  (2026-08-15)

## Corpus Check
- Corpus is ~2,397 words - fits in a single context window. You may not need a graph.

## Summary
- 89 nodes · 152 edges · 10 communities
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- MangaUpdates API Surface
- Scraper API Layer
- Paginated Embed View
- Bot Bootstrap and Keepalive
- Alltype Command
- Manga Command
- Manhua Command
- Manhwa Command
- Novel Search Command
- MangaUpdates API Surface (2)

## God Nodes (most connected - your core abstractions)
1. `SeriesView` - 22 edges
2. `search_series()` - 14 edges
3. `SeriesModelV1` - 6 edges
4. `fetch_series_detail()` - 5 edges
5. `Series` - 5 edges
6. `Manga` - 5 edges
7. `Manhua` - 5 edges
8. `Manhwa` - 5 edges
9. `Novel` - 5 edges
10. `search_Series()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `Series` --uses--> `SeriesView`  [INFERRED]
  commands/alltype.py → utils/series_view.py
- `Manga` --uses--> `SeriesView`  [INFERRED]
  commands/manga.py → utils/series_view.py
- `Manhua` --uses--> `SeriesView`  [INFERRED]
  commands/manhua.py → utils/series_view.py
- `Manhwa` --uses--> `SeriesView`  [INFERRED]
  commands/manhwa.py → utils/series_view.py
- `Novel` --uses--> `SeriesView`  [INFERRED]
  commands/novel.py → utils/series_view.py

## Import Cycles
- None detected.

## Communities (10 total, 0 thin omitted)

### Community 0 - "MangaUpdates API Surface"
Cohesion: 0.20
Nodes (14): fetch_series_detail(), ClientSession, GET /series/{id}, AvatarModelSearchV1, CategoriesModelV1, ImageModelV1, ListsSeriesModelV1, SeriesModelSearchV1 (+6 more)

### Community 1 - "Scraper API Layer"
Cohesion: 0.29
Nodes (7): search_Series(), _request_json(), search_series(), search_manga(), search_Manhua(), search_Manhwa(), search_novel()

### Community 2 - "Paginated Embed View"
Cohesion: 0.30
Nodes (5): button, Embed, build_embed(), Interaction, SeriesView

### Community 3 - "Bot Bootstrap and Keepalive"
Cohesion: 0.29
Nodes (8): event, load_extensions(), main(), on_ready(), home(), run(), server_on(), route

### Community 4 - "Alltype Command"
Cohesion: 0.33
Nodes (4): command, Interaction, Series, setup()

### Community 5 - "Manga Command"
Cohesion: 0.33
Nodes (4): Manga, command, Interaction, setup()

### Community 6 - "Manhua Command"
Cohesion: 0.33
Nodes (4): Manhua, command, Interaction, setup()

### Community 7 - "Manhwa Command"
Cohesion: 0.33
Nodes (4): Manhwa, command, Interaction, setup()

### Community 8 - "Novel Search Command"
Cohesion: 0.33
Nodes (4): Novel, command, Interaction, setup()

### Community 9 - "MangaUpdates API Surface (2)"
Cohesion: 0.40
Nodes (5): POST /series/search, ApiContextV1, ApiResponseV1, ApiValidationErrorsV1, SeriesSearchRequestV1

## Knowledge Gaps
- **5 isolated node(s):** `ApiContextV1`, `ApiValidationErrorsV1`, `AvatarModelSearchV1`, `CategoriesModelV1`, `SeriesSearchRequestV1`
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SeriesView` connect `Paginated Embed View` to `Alltype Command`, `Manga Command`, `Manhua Command`, `Manhwa Command`, `Novel Search Command`?**
  _High betweenness centrality (0.343) - this node is a cross-community bridge._
- **Why does `search_series()` connect `Scraper API Layer` to `MangaUpdates API Surface`, `MangaUpdates API Surface (2)`?**
  _High betweenness centrality (0.312) - this node is a cross-community bridge._
- **Why does `POST /series/search` connect `MangaUpdates API Surface (2)` to `MangaUpdates API Surface`, `Scraper API Layer`?**
  _High betweenness centrality (0.156) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `SeriesView` (e.g. with `Series` and `Manga`) actually correct?**
  _`SeriesView` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `ApiContextV1`, `ApiValidationErrorsV1`, `AvatarModelSearchV1` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._