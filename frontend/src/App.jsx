import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import TopBar from "./components/TopBar.jsx";
import Sidebar from "./components/Sidebar.jsx";
import GraphCanvas from "./components/GraphCanvas.jsx";
import DetailPanel from "./components/DetailPanel.jsx";
import UnresolvedPanel from "./components/UnresolvedPanel.jsx";
import EmptyState from "./components/EmptyState.jsx";
import { buildElements, validateGraphPayload } from "./utils/graphData.js";
import { scanAndFetch } from "./utils/api.js";

export default function App() {
  const [rawData, setRawData] = useState(null);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [search, setSearch] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanStatus, setScanStatus] = useState(null);
  const fileInputRef = useRef(null);

  const {
    files,
    nodes,
    edges,
    incomingMap,
    outgoingMap,
    unresolvedByFile,
    unresolvedAttention,
    unresolvedExpected,
    functionEdges,
    commonPrefix,
    fileTree,
    hubs,
  } = useMemo(() => buildElements(rawData), [rawData]);

  const handleFile = useCallback((file) => {
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const parsed = JSON.parse(evt.target.result);
        validateGraphPayload(parsed);
        setRawData(parsed);
        setError(null);
        setSelectedId(null);
      } catch (err) {
        setError(err.message || "Could not parse this file as valid JSON.");
      }
    };
    reader.onerror = () => setError("Could not read the file.");
    reader.readAsText(file);
  }, []);

  const handleScanPath = useCallback(async (path) => {
    setScanning(true);
    setScanStatus("queued…");
    setError(null);
    try {
      const data = await scanAndFetch(path, {
        onStatus: (s) => {
          if (s.status === "queued") setScanStatus("queued…");
          else if (s.status === "running") setScanStatus("running…");
        },
      });
      validateGraphPayload(data);
      setRawData(data);
      setSelectedId(null);
    } catch (err) {
      setError(err.message || "Scan failed.");
    } finally {
      setScanning(false);
      setScanStatus(null);
    }
  }, []);

  const handleNewScan = useCallback(() => {
    setRawData(null);
    setSelectedId(null);
    setError(null);
  }, []);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // "unresolved" in the top bar counts only imports that genuinely need a
  // human's attention (see isExpectedUnresolved) — not every `import os`,
  // which would otherwise make nearly every real project look broken.
  const stats = {
    files: files.length,
    edges: edges.length,
    unresolved: unresolvedAttention.length,
    functionEdges: functionEdges.length,
  };

  return (
    <div className="h-screen w-full bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      <TopBar
        stats={stats}
        onLoadClick={() => fileInputRef.current?.click()}
        onNewScan={handleNewScan}
        hasData={Boolean(rawData)}
      />
      <input
        ref={fileInputRef}
        type="file"
        accept="application/json"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />

      <div className="flex flex-1 min-h-0">
        {!rawData ? (
          <EmptyState
            onFile={handleFile}
            onScanPath={handleScanPath}
            scanning={scanning}
            scanStatus={scanStatus}
            error={error}
          />
        ) : (
          <>
            <Sidebar
              files={files}
              fileTree={fileTree}
              commonPrefix={commonPrefix}
              search={search}
              onSearchChange={setSearch}
              unresolvedByFile={unresolvedByFile}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
            <GraphCanvas
              nodes={nodes}
              edges={edges}
              incomingMap={incomingMap}
              outgoingMap={outgoingMap}
              selectedId={selectedId}
              onSelectNode={setSelectedId}
            />
            <aside className="w-80 border-l border-zinc-800 bg-zinc-900/30 overflow-y-auto shrink-0 divide-y divide-zinc-800">
              <div>
                <p className="text-[10px] uppercase tracking-wide text-zinc-500 px-4 pt-4">
                  Selected file
                </p>
                <DetailPanel
                  selectedId={selectedId}
                  outgoingMap={outgoingMap}
                  incomingMap={incomingMap}
                  onSelect={setSelectedId}
                  commonPrefix={commonPrefix}
                  hubs={hubs}
                  stats={stats}
                />
              </div>
              <div>
                <div className="flex items-center gap-1.5 px-4 pt-4">
                  <p className="text-[10px] uppercase tracking-wide text-zinc-500">
                    Unresolved imports
                  </p>
                  {unresolvedAttention.length > 0 && (
                    <span className="text-[10px] font-mono text-amber-400">
                      ({unresolvedAttention.length})
                    </span>
                  )}
                </div>
                <UnresolvedPanel attention={unresolvedAttention} expected={unresolvedExpected} />
              </div>
            </aside>
          </>
        )}
      </div>
    </div>
  );
}
