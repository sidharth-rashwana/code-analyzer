import { useState, useRef } from "react";
import { Upload, FileCode, AlertTriangle, FolderSearch, Loader2 } from "lucide-react";

export default function EmptyState({ onFile, onScanPath, scanning, scanStatus, error }) {
  const [dragActive, setDragActive] = useState(false);
  const [path, setPath] = useState("");
  const inputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) onFile(file);
  };

  const handleScanSubmit = (e) => {
    e.preventDefault();
    const trimmed = path.trim();
    if (trimmed && !scanning) onScanPath(trimmed);
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-6 m-6">
      <div className="w-full max-w-sm">
        <p className="text-[10px] uppercase tracking-wide text-zinc-500 mb-2 text-center">
          Scan a project
        </p>
        <form onSubmit={handleScanSubmit} className="flex items-center gap-2">
          <input
            type="text"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="/path/to/project"
            aria-label="Project path to scan"
            disabled={scanning}
            className="flex-1 bg-zinc-950 border border-zinc-700 rounded-md px-3 py-2 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={scanning || !path.trim()}
            className="flex items-center gap-2 text-xs font-medium border border-zinc-700 rounded-md px-3 py-2 text-zinc-200 hover:border-teal-500 hover:bg-zinc-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 disabled:opacity-50 disabled:pointer-events-none shrink-0"
          >
            {scanning ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <FolderSearch className="w-3.5 h-3.5" aria-hidden="true" />
            )}
            {scanning ? (scanStatus || "Scanning…") : "Scan"}
          </button>
        </form>
      </div>

      <div className="flex items-center gap-3 w-full max-w-sm text-zinc-700">
        <div className="flex-1 h-px bg-zinc-800" />
        <span className="text-[10px] uppercase tracking-wide text-zinc-600">or</span>
        <div className="flex-1 h-px bg-zinc-800" />
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        className={`w-full max-w-sm flex flex-col items-center justify-center gap-4 border-2 border-dashed rounded-xl p-8 transition-colors ${
          dragActive ? "border-teal-500 bg-teal-950/20" : "border-zinc-800"
        }`}
      >
        <FileCode className="w-8 h-8 text-zinc-600" aria-hidden="true" />
        <div className="text-center">
          <p className="text-sm text-zinc-400 mb-1">
            Drop a saved <span className="font-mono text-zinc-200">module_graph.json</span> here
          </p>
        </div>
        <button
          onClick={() => inputRef.current?.click()}
          className="flex items-center gap-2 text-xs font-medium border border-zinc-700 rounded-md px-4 py-2 text-zinc-200 hover:border-teal-500 hover:bg-zinc-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
        >
          <Upload className="w-3.5 h-3.5" aria-hidden="true" />
          Browse for file
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="application/json"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onFile(file);
          }}
        />
      </div>

      {error && (
        <div className="flex items-center gap-2 text-xs text-red-400 max-w-sm text-center">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
          {error}
        </div>
      )}
    </div>
  );
}
