import { Upload, GitBranch, RotateCcw } from "lucide-react";

export default function TopBar({ stats, onLoadClick, onNewScan, hasData }) {
  return (
    <div className="h-14 flex items-center gap-6 px-5 border-b border-zinc-800 bg-zinc-900/60 shrink-0">
      <div className="flex items-center gap-2 font-semibold text-sm text-zinc-100">
        <GitBranch className="w-4 h-4 text-teal-400" aria-hidden="true" />
        Dependency graph explorer
      </div>

      <div className="flex items-center gap-5">
        <Stat label="files" value={stats.files} />
        <Stat label="edges" value={stats.edges} />
        <Stat label="unresolved" value={stats.unresolved} warn />
        <Stat label="fn edges" value={stats.functionEdges} />
      </div>

      <div className="flex-1" />

      {hasData && (
        <button
          onClick={onNewScan}
          className="flex items-center gap-2 text-xs font-medium border border-zinc-700 rounded-md px-3 py-1.5 text-zinc-200 hover:border-teal-500 hover:bg-zinc-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
        >
          <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" />
          New scan
        </button>
      )}

      <button
        onClick={onLoadClick}
        className="flex items-center gap-2 text-xs font-medium border border-zinc-700 rounded-md px-3 py-1.5 text-zinc-200 hover:border-teal-500 hover:bg-zinc-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
      >
        <Upload className="w-3.5 h-3.5" aria-hidden="true" />
        Load module_graph.json
      </button>
    </div>
  );
}

function Stat({ label, value, warn }) {
  return (
    <div className="flex flex-col leading-tight">
      <span className={`font-mono text-sm ${warn && value > 0 ? "text-amber-400" : "text-zinc-100"}`}>
        {value}
      </span>
      <span className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</span>
    </div>
  );
}
