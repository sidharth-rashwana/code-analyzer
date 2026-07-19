import { useState } from "react";
import { ChevronRight, ChevronDown, CheckCircle2 } from "lucide-react";
import { shortName } from "../utils/graphData.js";

export default function UnresolvedPanel({ attention, expected }) {
  const [expectedOpen, setExpectedOpen] = useState(false);

  if (attention.length === 0 && expected.length === 0) {
    return (
      <div className="p-4 flex items-center gap-2 text-xs text-zinc-600">
        <CheckCircle2 className="w-3.5 h-3.5 text-teal-600" aria-hidden="true" />
        Nothing unresolved.
      </div>
    );
  }

  return (
    <div>
      {attention.length === 0 ? (
        <div className="p-4 flex items-center gap-2 text-xs text-zinc-600">
          <CheckCircle2 className="w-3.5 h-3.5 text-teal-600" aria-hidden="true" />
          No imports need attention.
        </div>
      ) : (
        <div className="p-4 space-y-3">
          {attention.map((u, i) => (
            <UnresolvedEntry key={i} u={u} tone="amber" />
          ))}
        </div>
      )}

      {expected.length > 0 && (
        <div className="border-t border-zinc-800">
          <button
            onClick={() => setExpectedOpen((v) => !v)}
            className="w-full flex items-center gap-1.5 px-4 py-2.5 text-left text-[10.5px] text-zinc-500 hover:text-zinc-300 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-teal-500"
          >
            {expectedOpen ? (
              <ChevronDown className="w-3 h-3 shrink-0" aria-hidden="true" />
            ) : (
              <ChevronRight className="w-3 h-3 shrink-0" aria-hidden="true" />
            )}
            {expected.length} stdlib / third-party import{expected.length === 1 ? "" : "s"}
            <span className="text-zinc-600">(expected, not a problem)</span>
          </button>
          {expectedOpen && (
            <div className="px-4 pb-4 space-y-3">
              {expected.map((u, i) => (
                <UnresolvedEntry key={i} u={u} tone="muted" />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function UnresolvedEntry({ u, tone }) {
  return (
    <div className="pb-3 border-b border-zinc-800 last:border-none last:pb-0">
      <p
        className={`font-mono text-[11px] break-all ${
          tone === "amber" ? "text-amber-400" : "text-zinc-500"
        }`}
      >
        {u.raw || u.imported_name || "(dynamic)"}
      </p>
      <p className="text-[10.5px] text-zinc-500 mt-0.5">{u.reason}</p>
      <p className="font-mono text-[10px] text-zinc-600 mt-0.5">
        {shortName(u.file)}:{u.line ?? "?"}
      </p>
    </div>
  );
}
