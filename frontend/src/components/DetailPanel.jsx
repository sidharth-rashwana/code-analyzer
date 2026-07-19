import { Network } from "lucide-react";
import { relativePath } from "../utils/graphData.js";

export default function DetailPanel({
  selectedId,
  outgoingMap,
  incomingMap,
  onSelect,
  commonPrefix,
  hubs,
  stats,
}) {
  if (!selectedId) {
    return <EmptyOverview hubs={hubs} stats={stats} commonPrefix={commonPrefix} onSelect={onSelect} />;
  }

  const outgoing = outgoingMap[selectedId] || [];
  const incoming = incomingMap[selectedId] || [];

  return (
    <div className="p-4">
      <p className="font-mono text-xs text-zinc-100 break-all mb-4" title={selectedId}>
        {relativePath(selectedId, commonPrefix)}
      </p>

      <RelList
        title="Imports"
        items={outgoing}
        commonPrefix={commonPrefix}
        onSelect={onSelect}
      />
      <RelList
        title="Imported by"
        items={incoming}
        commonPrefix={commonPrefix}
        onSelect={onSelect}
        className="mt-4"
      />
    </div>
  );
}

function EmptyOverview({ hubs, stats, commonPrefix, onSelect }) {
  return (
    <div className="p-4">
      <p className="text-xs text-zinc-600 mb-4">Select a file to see its dependencies.</p>

      {stats && (
        <div className="grid grid-cols-2 gap-2 mb-5">
          <MiniStat label="files" value={stats.files} />
          <MiniStat label="edges" value={stats.edges} />
        </div>
      )}

      {hubs && hubs.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <Network className="w-3 h-3 text-zinc-500" aria-hidden="true" />
            <p className="text-[10px] uppercase tracking-wide text-zinc-500">
              Most connected
            </p>
          </div>
          <ul className="space-y-0.5">
            {hubs.map((h) => (
              <li key={h.id}>
                <button
                  onClick={() => onSelect(h.id)}
                  className="w-full flex items-center gap-2 text-left px-1.5 py-1 rounded hover:bg-zinc-800 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-teal-500"
                  title={h.id}
                >
                  <span className="font-mono text-[11px] text-zinc-300 truncate flex-1">
                    {relativePath(h.id, commonPrefix)}
                  </span>
                  <span className="text-[10px] font-mono text-zinc-500 shrink-0">
                    {h.degree}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div className="bg-zinc-900/60 border border-zinc-800 rounded-md px-2.5 py-2">
      <p className="font-mono text-sm text-zinc-100">{value}</p>
      <p className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</p>
    </div>
  );
}

function RelList({ title, items, commonPrefix, onSelect, className = "" }) {
  return (
    <div className={className}>
      <p className="text-[10px] uppercase tracking-wide text-zinc-500 mb-1.5">
        {title} ({items.length})
      </p>
      {items.length === 0 && <p className="text-xs text-zinc-600">none</p>}
      <ul className="space-y-0.5">
        {items.map((o) => (
          <li key={o}>
            <button
              onClick={() => onSelect(o)}
              className="font-mono text-[11px] text-zinc-400 hover:text-teal-300 truncate block w-full text-left focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-teal-500 rounded"
              title={o}
            >
              {relativePath(o, commonPrefix)}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
