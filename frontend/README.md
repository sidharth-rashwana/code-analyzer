# Dependency Graph Explorer

A React app for exploring the module dependency graph produced by the
`code-analyzer` Python pipeline (`module_graph.json`).

## Setup

```bash
npm install
npm run dev
```

Then open the printed local URL, and drag a `module_graph.json` file onto
the empty state (or use the "Load module_graph.json" button).

## Build for production

```bash
npm run build
npm run preview   # serve the built output locally to sanity-check it
```

## Project structure

```
src/
├── main.jsx                    # React entry point
├── App.jsx                     # Root component — owns state, wires everything together
├── index.css                   # Tailwind base
├── components/
│   ├── TopBar.jsx               # Title, live stats, load button
│   ├── Sidebar.jsx               # Searchable file list
│   ├── GraphCanvas.jsx           # d3-force graph, pan/zoom, neighbor-focus highlighting
│   ├── DetailPanel.jsx           # Selected file's imports / imported-by
│   ├── UnresolvedPanel.jsx       # Read-only list of unresolved imports
│   └── EmptyState.jsx            # Drag-and-drop / browse-to-load screen
├── hooks/
│   ├── useContainerSize.js       # ResizeObserver-backed container sizing
│   └── useForceLayout.js         # d3-force simulation → {id: {x,y}} positions
└── utils/
    └── graphData.js               # Transforms raw {graph, unresolved} JSON into UI-ready shapes
```

## Notes for scaling this up

- **State management**: currently local `useState` in `App.jsx`. If this
  grows (e.g. adding human-in-the-loop review, multiple loaded graphs,
  persisted overrides), consider lifting to a context or a small store
  (Zustand is a good fit for this size of app).
- **Data source**: currently file-upload only, per your choice. If you
  add a backend later, only `App.jsx`'s `handleFile`/data-loading logic
  needs to change — every component below it just takes `nodes`/`edges`/
  maps as props, so swapping the data source doesn't touch the rendering
  layer at all.
- **Testing**: no test setup yet. `utils/graphData.js` is pure functions
  with no DOM/React dependency — that's the easiest place to start with
  unit tests (Vitest pairs naturally with this Vite setup).
- **Styling**: Tailwind utility classes throughout, dark theme via
  hardcoded zinc/teal/amber palette. If you want theming (light mode,
  brand colors), move the palette into `tailwind.config.js` `theme.extend.colors`
  instead of relying on default `zinc`/`teal`/`amber`.
