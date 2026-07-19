import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Sidebar from "../src/components/Sidebar.jsx";
import DetailPanel from "../src/components/DetailPanel.jsx";
import UnresolvedPanel from "../src/components/UnresolvedPanel.jsx";
import { buildElements } from "../src/utils/graphData.js";

const rawData = {
  graph: {
    "/proj/main.py": { hash: "h1", imports: [
      { kind: "from_import", raw: "utils.helper", imported_name: "greet", resolved_file: "/proj/utils/helper.py" },
    ]},
    "/proj/utils/helper.py": { hash: "h2", imports: [] },
    "/proj/utils/graph/module_graph.py": { hash: "h3", imports: [
      { kind: "from_import", raw: "utils.rules.rules", imported_name: "resolve_import", resolved_file: "/proj/utils/rules/rules.py" },
    ]},
    "/proj/utils/rules/rules.py": { hash: "h4", imports: [] },
  },
  unresolved: [
    { file: "/proj/main.py", line: 1, raw: "json", reason: "stdlib or third-party (not found in project)" },
    { file: "/proj/utils/rules/rules.py", line: 5, raw: "not_exported", reason: "'not_exported' not found among top-level names of /proj/x.py" },
  ],
  function_edges: [],
};

describe("Sidebar", () => {
  it("renders the directory tree without crashing", () => {
    const data = buildElements(rawData);
    render(
      <Sidebar
        files={data.files}
        fileTree={data.fileTree}
        commonPrefix={data.commonPrefix}
        search=""
        onSearchChange={() => {}}
        unresolvedByFile={data.unresolvedByFile}
        selectedId={null}
        onSelect={() => {}}
      />
    );
    expect(screen.getByText("main.py")).toBeTruthy();
    expect(screen.getByText("utils")).toBeTruthy();
    // nested folders under utils
    expect(screen.getByText("graph")).toBeTruthy();
    expect(screen.getByText("rules")).toBeTruthy();
  });

  it("collapses a folder on click", () => {
    const data = buildElements(rawData);
    render(
      <Sidebar
        files={data.files}
        fileTree={data.fileTree}
        commonPrefix={data.commonPrefix}
        search=""
        onSearchChange={() => {}}
        unresolvedByFile={data.unresolvedByFile}
        selectedId={null}
        onSelect={() => {}}
      />
    );
    expect(screen.getByText("graph")).toBeTruthy();
    fireEvent.click(screen.getByText("utils"));
    expect(screen.queryByText("graph")).toBeNull();
  });

  it("falls back to a flat filtered list while searching", () => {
    const data = buildElements(rawData);
    const onSearchChange = vi.fn();
    render(
      <Sidebar
        files={data.files}
        fileTree={data.fileTree}
        commonPrefix={data.commonPrefix}
        search="rules"
        onSearchChange={onSearchChange}
        unresolvedByFile={data.unresolvedByFile}
        selectedId={null}
        onSelect={() => {}}
      />
    );
    expect(screen.getByText("rules.py")).toBeTruthy();
    expect(screen.queryByText("main.py")).toBeNull();
  });

  it("calls onSelect with the file id when a file row is clicked", () => {
    const data = buildElements(rawData);
    const onSelect = vi.fn();
    render(
      <Sidebar
        files={data.files}
        fileTree={data.fileTree}
        commonPrefix={data.commonPrefix}
        search=""
        onSearchChange={() => {}}
        unresolvedByFile={data.unresolvedByFile}
        selectedId={null}
        onSelect={onSelect}
      />
    );
    fireEvent.click(screen.getByText("main.py"));
    expect(onSelect).toHaveBeenCalledWith("/proj/main.py");
  });
});

describe("DetailPanel", () => {
  it("renders the empty overview with hubs and stats when nothing selected", () => {
    const data = buildElements(rawData);
    render(
      <DetailPanel
        selectedId={null}
        outgoingMap={data.outgoingMap}
        incomingMap={data.incomingMap}
        onSelect={() => {}}
        commonPrefix={data.commonPrefix}
        hubs={data.hubs}
        stats={{ files: data.files.length, edges: data.edges.length }}
      />
    );
    expect(screen.getByText("Select a file to see its dependencies.")).toBeTruthy();
    expect(screen.getByText("Most connected")).toBeTruthy();
  });

  it("renders relative paths (not full absolute paths) for a selected file", () => {
    const data = buildElements(rawData);
    render(
      <DetailPanel
        selectedId="/proj/main.py"
        outgoingMap={data.outgoingMap}
        incomingMap={data.incomingMap}
        onSelect={() => {}}
        commonPrefix={data.commonPrefix}
        hubs={data.hubs}
        stats={{ files: data.files.length, edges: data.edges.length }}
      />
    );
    expect(screen.getByText("main.py")).toBeTruthy();
    expect(screen.queryByText("/proj/main.py")).toBeNull();
    expect(screen.getByText("utils/helper.py")).toBeTruthy();
  });
});

describe("UnresolvedPanel", () => {
  it("shows attention items expanded and expected items collapsed by default", () => {
    const data = buildElements(rawData);
    render(
      <UnresolvedPanel attention={data.unresolvedAttention} expected={data.unresolvedExpected} />
    );
    expect(screen.getByText("not_exported")).toBeTruthy(); // attention item, visible
    expect(screen.queryByText("json")).toBeNull(); // expected item, collapsed
    expect(screen.getByText(/stdlib \/ third-party import/)).toBeTruthy();
  });

  it("expands the expected section on click", () => {
    const data = buildElements(rawData);
    render(
      <UnresolvedPanel attention={data.unresolvedAttention} expected={data.unresolvedExpected} />
    );
    fireEvent.click(screen.getByText(/stdlib \/ third-party import/));
    expect(screen.getByText("json")).toBeTruthy();
  });

  it("shows a clean success state when nothing is unresolved", () => {
    render(<UnresolvedPanel attention={[]} expected={[]} />);
    expect(screen.getByText("Nothing unresolved.")).toBeTruthy();
  });
});

describe("GraphCanvas", () => {
  it("renders without crashing given nodes/edges/positions data", async () => {
    // jsdom has no ResizeObserver; stub it so useContainerSize doesn't throw
    global.ResizeObserver = class {
      observe() {}
      disconnect() {}
    };
    const { default: GraphCanvas } = await import("../src/components/GraphCanvas.jsx");
    const data = buildElements(rawData);
    const { container } = render(
      <GraphCanvas
        nodes={data.nodes}
        edges={data.edges}
        incomingMap={data.incomingMap}
        outgoingMap={data.outgoingMap}
        selectedId={null}
        onSelectNode={() => {}}
      />
    );
    expect(container.querySelector("svg")).toBeTruthy();
    expect(screen.getByText("resolved cleanly")).toBeTruthy();
  });
});
