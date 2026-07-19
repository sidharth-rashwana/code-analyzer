# Code Analyzer

A static Python code analyzer that builds interactive dependency graphs for impact analysis, architecture visualization, and LLM-assisted development.

## Overview

Understanding the impact of a code change becomes increasingly difficult as a project grows. When using LLMs, this often leads to providing entire repositories—or making educated guesses about which files are relevant—resulting in unnecessary context and higher token usage.

Code Analyzer statically resolves Python imports and constructs a complete dependency graph of your project. The graph can be queried and explored interactively to identify downstream dependencies, visualize architecture, and determine the precise scope of a change.

Rather than relying on heuristics, the analyzer resolves imports directly from the source code, making it useful for development workflows, code reviews, refactoring, and preparing focused context for LLMs.

## Use Cases

- **LLM-assisted development** — Supply only the files relevant to a requested change.
- **Impact analysis** — Identify downstream modules affected by a modification.
- **Code reviews** — Understand the blast radius of a pull request.
- **Refactoring** — Discover dependencies before making structural changes.
- **Architecture exploration** — Visualize relationships across a codebase.

---

## Features

- Static Python dependency analysis
- Interactive dependency graph visualization
- Reverse dependency (impact) analysis
- Incremental scanning with caching
- Graphviz (`.dot`) export
- Snapshot comparison between scans

---

## Installation

### Backend

```bash
git clone <your-repo-url>
cd backend

uv sync

# Optional: install API dependencies
pip install fastapi uvicorn
```

**Requirements**

- Python 3.11+
- `uv` (recommended)

### Frontend

```bash
cd frontend
npm install
```

---

## Usage

```bash
# Interactive scan
python main.py

# Scan a project
python main.py /path/to/project

# Export Graphviz
python main.py /path/to/project --dot

# Ignore cache
python main.py /path/to/project --no-cache

# Compare snapshots
python main.py --diff result/old.json result/new.json

# Custom configuration
python main.py /path/to/project --config myconfig.toml

# Review unresolved imports
python review_cli.py /path/to/project

# Run the API
uvicorn endpoints.api:app --reload
```

| Command                         | Description                                                |
| ------------------------------- | ---------------------------------------------------------- |
| `python main.py`                | Analyze a project and generate `result/module_graph.json`. |
| `python main.py --dot`          | Export the dependency graph as Graphviz `.dot`.            |
| `python main.py --diff OLD NEW` | Compare two graph snapshots.                               |
| `python main.py --config FILE`  | Use a custom configuration file.                           |
| `python review_cli.py`          | Review unresolved or ambiguous imports interactively.      |
| `uvicorn api:app --reload`      | Start the FastAPI server.                                  |
| `npm run dev`                   | Start the React application.                               |
| `npm run build`                 | Build the production frontend.                             |

---

## Deployment

The frontend is a static application.

```bash
cd frontend
npm run build
```

The generated `dist/` directory can be deployed to any static hosting platform, including Vercel, Netlify, GitHub Pages, Cloudflare Pages, or a standard web server.

---

## License

Released under the MIT License.
