# TODO — code-analyzer-UI

Ideas for further work, roughly ordered by impact. Items marked "done this
pass" were addressed in the signal-to-noise / professional-polish update;
everything else is still open.

## Done this pass (for context)

- Split "unresolved" into real issues vs. expected stdlib/third-party noise
  (`isExpectedUnresolved` in `graphData.js`) — previously every file lit up
  amber just for importing `json`/`os`, which drowned out real signal.
- Sidebar: flat 14-file alphabetical dump → collapsible directory tree
  (falls back to a flat filtered list while searching).
- DetailPanel empty state: one line of hint text → project stats + "most
  connected files" (hub) list.
- GraphCanvas: auto-fit-to-content on load (previously started centered
  but unzoomed, so a spread-out graph needed manual zoom-out every time),
  degree-based node sizing, hover tooltips, a legend.
- UnresolvedPanel: attention items shown expanded, stdlib/third-party noise
  collapsed by default behind a disclosure toggle.
- Paths shown relative to project root everywhere instead of full absolute
  paths (`relativePath` / `commonPrefix`).

## High impact, not yet done

- **`function_edges` panel.** `Depends()`/`add_task()` edges flow into the
  app and show up as a TopBar count, but there's no way to browse them —
  no dedicated panel, no representation on the graph canvas itself (they're
  a different edge *type* than module imports and arguably deserve a
  visually distinct line style, e.g. dashed, or a toggleable overlay layer).
- **Search should highlight in the canvas, not just filter the sidebar.**
  Right now typing in the filter box only narrows the sidebar list; the
  graph itself doesn't dim non-matching nodes or pan/zoom to matches. For a
  large repo, finding a file in the graph by eye is the actual bottleneck.
- **Node clustering by directory in the graph itself.** The sidebar now
  groups by folder, but the graph canvas still treats every file as a peer
  in one flat force simulation — for a large multi-package repo this
  produces a hairball. A d3 "cluster force" (grouping nodes by top-level
  directory, e.g. via `forceX`/`forceY` biased per-group) would make
  package boundaries visually legible.
- **Overrides-aware rendering.** The Python backend has a whole
  human-in-the-loop review flow (`overrides.py`, `review_cli.py`,
  confirm/reject/manual-edge decisions persisted to `overrides.json`), but
  the UI has no visibility into it at all. At minimum: show which edges
  were manually confirmed/overridden vs. resolved automatically (e.g. a
  small icon or different stroke), and ideally let a user do the
  confirm/reject/manual-edge review *in the UI* instead of only via
  `review_cli.py`'s terminal prompts — this is the most natural home for
  that workflow, not a separate CLI tool.

## Medium impact

- **Minimap.** For a graph too big to see all at once, a small
  bottom-corner overview with a viewport rectangle (standard in Figma,
  Miro, any serious node-graph tool) makes spatial orientation much
  easier than zoom-in/zoom-out/reset alone.
- **Loading/skeleton states.** Right now the transition from "scanning…"
  to a populated graph is instant-or-nothing. A skeleton graph (placeholder
  nodes fading in) during the force simulation's settle time would read as
  more polished than the current pop-in.
- **Drag-to-reposition nodes**, with position pinning (d3-drag + fixing
  `fx`/`fy` on drag end) so a user can manually untangle a specific area
  and have it stay put across re-renders — right now every node's position
  is entirely simulation-driven and un-pinnable.
- **Export.** "Save as PNG/SVG" for the current canvas view, and "Save as
  Graphviz .dot" from the UI directly (the backend already generates this
  via `output_dot.py` — just needs a UI trigger + download, or a button
  that calls a new backend endpoint).
- **URL state / shareable views.** Encode `selectedId` + search + which
  scan (job id or file) into the URL, so a link can be shared that opens
  directly to a specific file's dependencies instead of everyone re-scanning
  and re-clicking.
- **Diff view.** The backend has `diff.py` / `main.py --diff` for comparing
  two snapshots (added/removed files, added/removed edges) — there's no UI
  for this at all. A side-by-side or overlay view (green = added edge, red
  = removed) would make PR-review use cases much more usable than reading
  the CLI's text output.

## Lower impact / polish

- **Keyboard navigation for the sidebar tree** (arrow keys to move between
  rows, `→`/`←` to expand/collapse folders) — currently mouse/click-only
  beyond the existing Escape-to-deselect handler.
- **Right-click context menu on nodes** (e.g. "copy path", "show only this
  file's subgraph", "open in editor" via a `vscode://` deep link if
  running locally).
- **Virtualized rendering for very large repos.** Both the sidebar tree and
  the SVG canvas render every node/row unconditionally; for a repo with
  thousands of files this will get slow. Windowing the sidebar list and/or
  switching the canvas to WebGL (e.g. `pixi.js` or `regl`) instead of raw
  SVG would be the fix, but only worth doing if real usage hits that scale
  — premature for the current target size.
- **Light theme.** Currently dark-only; if this ever needs to sit inside a
  light-themed internal tool page, the zinc/teal/amber palette would need a
  light-mode variant.
- **Persist UI preferences** (which sidebar folders are collapsed, last
  selected file, last search) to `localStorage` — currently everything
  resets to defaults every reload. **Note:** artifacts-hosted deployments
  of this UI can't use `localStorage`/`sessionStorage`; that constraint
  wouldn't apply to a normal Vite/npm deployment like this one, but worth
  flagging if this ever gets embedded somewhere with that restriction.
- **Error boundary.** A single bad node in `rawData` (malformed but
  schema-valid JSON) currently has no guardrail beyond `validateGraphPayload`'s
  shallow check — a React error boundary around the data-dependent view
  would turn "the whole app goes white" into a recoverable error state.
- **Automated test coverage beyond the current smoke tests.** `test/smoke.test.jsx`
  covers Sidebar/DetailPanel/UnresolvedPanel/GraphCanvas mounting and basic
  interaction, added during this pass — worth expanding into a proper suite
  (edge-dedup cases, tree-building edge cases like files directly at the
  common-prefix root, the auto-fit zoom math) rather than leaving it as a
  one-off verification pass.

## Explicitly out of scope for now

- Real-time/live-reload scanning (watch the filesystem, re-scan
  automatically on file save) — the API's job model is request/response,
  not a subscription; would need a websocket or SSE endpoint added to
  `api.py` first.
- Multi-project / multi-tab support (comparing two different repos side by
  side) — current app state is single-dataset by design.
