import { useState, useMemo } from "react";
import { Search, ChevronRight, ChevronDown, Folder } from "lucide-react";
import { shortName, relativePath } from "../utils/graphData.js";

export default function Sidebar({
  files,
  fileTree,
  commonPrefix,
  search,
  onSearchChange,
  unresolvedByFile,
  selectedId,
  onSelect,
}) {
  const [collapsed, setCollapsed] = useState(() => new Set());

  const toggleFolder = (path) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const filtered = useMemo(() => {
    if (!search) return null;
    const q = search.toLowerCase();
    return files
      .filter((f) => f.toLowerCase().includes(q))
      .sort((a, b) => relativePath(a, commonPrefix).localeCompare(relativePath(b, commonPrefix)));
  }, [files, search, commonPrefix]);

  return (
    <aside className="w-64 border-r border-zinc-800 bg-zinc-900/30 flex flex-col shrink-0">
      <div className="p-3 border-b border-zinc-800">
        <div className="relative">
          <Search
            className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-1/2 -translate-y-1/2"
            aria-hidden="true"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Filter files..."
            aria-label="Filter files"
            className="w-full bg-zinc-950 border border-zinc-700 rounded-md pl-8 pr-2 py-1.5 text-xs text-zinc-100 placeholder-zinc-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-1.5">
        {filtered ? (
          <FlatList
            files={filtered}
            commonPrefix={commonPrefix}
            unresolvedByFile={unresolvedByFile}
            selectedId={selectedId}
            onSelect={onSelect}
          />
        ) : (
          <TreeLevel
            node={fileTree}
            depth={0}
            pathPrefix=""
            collapsed={collapsed}
            onToggle={toggleFolder}
            unresolvedByFile={unresolvedByFile}
            selectedId={selectedId}
            onSelect={onSelect}
          />
        )}
      </div>
    </aside>
  );
}

function FlatList({ files, commonPrefix, unresolvedByFile, selectedId, onSelect }) {
  if (files.length === 0) {
    return <p className="text-xs text-zinc-600 px-2 py-3">No matching files.</p>;
  }
  return (
    <>
      {files.map((f) => {
        const rel = relativePath(f, commonPrefix);
        const dir = rel.includes("/") ? rel.slice(0, rel.lastIndexOf("/")) : "";
        return (
          <FileRow
            key={f}
            id={f}
            name={shortName(f)}
            subtitle={dir}
            selected={selectedId === f}
            hasAttention={Boolean(unresolvedByFile[f])}
            onSelect={onSelect}
          />
        );
      })}
    </>
  );
}

function TreeLevel({
  node,
  depth,
  pathPrefix,
  collapsed,
  onToggle,
  unresolvedByFile,
  selectedId,
  onSelect,
}) {
  const folderNames = [...node.folders.keys()].sort();
  const sortedFiles = [...node.files].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <>
      {folderNames.map((name) => {
        const folderPath = pathPrefix ? `${pathPrefix}/${name}` : name;
        const child = node.folders.get(name);
        const isCollapsed = collapsed.has(folderPath);
        const descendantAttentionCount = countAttention(child, unresolvedByFile);

        return (
          <div key={folderPath}>
            <button
              onClick={() => onToggle(folderPath)}
              className="w-full flex items-center gap-1 text-left px-2 py-1.5 rounded-md text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
              style={{ paddingLeft: `${8 + depth * 14}px` }}
            >
              {isCollapsed ? (
                <ChevronRight className="w-3 h-3 shrink-0" aria-hidden="true" />
              ) : (
                <ChevronDown className="w-3 h-3 shrink-0" aria-hidden="true" />
              )}
              <Folder className="w-3.5 h-3.5 shrink-0 text-zinc-500" aria-hidden="true" />
              <span className="truncate flex-1">{name}</span>
              {descendantAttentionCount > 0 && (
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" aria-hidden="true" />
              )}
            </button>
            {!isCollapsed && (
              <TreeLevel
                node={child}
                depth={depth + 1}
                pathPrefix={folderPath}
                collapsed={collapsed}
                onToggle={onToggle}
                unresolvedByFile={unresolvedByFile}
                selectedId={selectedId}
                onSelect={onSelect}
              />
            )}
          </div>
        );
      })}
      {sortedFiles.map((f) => (
        <FileRow
          key={f.id}
          id={f.id}
          name={f.name}
          selected={selectedId === f.id}
          hasAttention={Boolean(unresolvedByFile[f.id])}
          onSelect={onSelect}
          indent={8 + depth * 14 + 16}
        />
      ))}
    </>
  );
}

function countAttention(node, unresolvedByFile) {
  let count = 0;
  node.files.forEach((f) => {
    if (unresolvedByFile[f.id]) count += 1;
  });
  node.folders.forEach((child) => {
    count += countAttention(child, unresolvedByFile);
  });
  return count;
}

function FileRow({ id, name, subtitle, selected, hasAttention, onSelect, indent }) {
  return (
    <button
      onClick={() => onSelect(id)}
      title={id}
      className={`w-full flex items-center gap-2 text-left py-1.5 pr-2 rounded-md text-xs font-mono truncate transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 ${
        selected
          ? "bg-teal-950 text-teal-300"
          : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
      }`}
      style={{ paddingLeft: indent ? `${indent}px` : "8px" }}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full shrink-0 ${
          hasAttention ? "bg-amber-400" : "bg-zinc-600"
        }`}
        aria-hidden="true"
      />
      <span className="truncate">{name}</span>
      {subtitle && (
        <span className="truncate text-zinc-600 text-[10px] ml-auto shrink-0 max-w-[80px]">
          {subtitle}
        </span>
      )}
    </button>
  );
}
