import { useRef, useEffect, useMemo } from "react";
import * as d3 from "d3";
import { ZoomIn, ZoomOut, Maximize2 } from "lucide-react";
import { useContainerSize } from "../hooks/useContainerSize.js";
import { useForceLayout } from "../hooks/useForceLayout.js";

export default function GraphCanvas({
  nodes,
  edges,
  incomingMap,
  outgoingMap,
  selectedId,
  onSelectNode,
}) {
  const [containerRef, size] = useContainerSize();
  const positions = useForceLayout(nodes, edges, size.width, size.height);
  const gRef = useRef(null);
  const svgRef = useRef(null);
  const zoomBehaviorRef = useRef(null);
  const autoFittedForRef = useRef(null);

  useEffect(() => {
    if (!svgRef.current || !gRef.current) return;
    const zoom = d3
      .zoom()
      .scaleExtent([0.15, 3])
      .on("zoom", (event) => {
        gRef.current.setAttribute("transform", event.transform);
      });
    d3.select(svgRef.current).call(zoom);
    zoomBehaviorRef.current = zoom;
  }, []);

  // Auto-fit the view to the graph's content once, for each new dataset —
  // otherwise a freshly-loaded graph starts centered-but-unzoomed, which
  // for a large or spread-out repo often means half the nodes are outside
  // the visible viewport until the user manually zooms out. Identified by
  // dataset via a signature of node ids, so it re-fits on a new scan but
  // never fights the user's own zoom/pan on the same dataset.
  useEffect(() => {
    const datasetKey = nodes.map((n) => n.id).sort().join("|");
    if (!datasetKey || datasetKey === autoFittedForRef.current) return;
    if (Object.keys(positions).length < nodes.length) return; // wait for layout to populate
    if (!svgRef.current || !zoomBehaviorRef.current) return;

    const timeout = setTimeout(() => {
      const coords = Object.values(positions);
      if (!coords.length) return;
      const xs = coords.map((p) => p.x);
      const ys = coords.map((p) => p.y);
      const minX = Math.min(...xs) - 60;
      const maxX = Math.max(...xs) + 60;
      const minY = Math.min(...ys) - 40;
      const maxY = Math.max(...ys) + 40;
      const w = Math.max(1, maxX - minX);
      const h = Math.max(1, maxY - minY);
      const scale = Math.min(2, Math.min(size.width / w, size.height / h));
      const tx = size.width / 2 - scale * (minX + w / 2);
      const ty = size.height / 2 - scale * (minY + h / 2);

      d3.select(svgRef.current)
        .transition()
        .duration(350)
        .call(
          zoomBehaviorRef.current.transform,
          d3.zoomIdentity.translate(tx, ty).scale(scale)
        );

      autoFittedForRef.current = datasetKey;
    }, 650); // let the force simulation settle a bit before measuring bounds

    return () => clearTimeout(timeout);
  }, [nodes, positions, size.width, size.height]);

  const handleZoom = (factor) => {
    if (!svgRef.current || !zoomBehaviorRef.current) return;
    d3.select(svgRef.current)
      .transition()
      .duration(200)
      .call(zoomBehaviorRef.current.scaleBy, factor);
  };

  const handleReset = () => {
    if (!svgRef.current || !zoomBehaviorRef.current) return;
    d3.select(svgRef.current)
      .transition()
      .duration(250)
      .call(zoomBehaviorRef.current.transform, d3.zoomIdentity);
  };

  const neighborSet = useMemo(() => {
    if (!selectedId) return null;
    const s = new Set([selectedId]);
    (outgoingMap[selectedId] || []).forEach((n) => s.add(n));
    (incomingMap[selectedId] || []).forEach((n) => s.add(n));
    return s;
  }, [selectedId, outgoingMap, incomingMap]);

  return (
    <div ref={containerRef} className="flex-1 relative bg-zinc-950 overflow-hidden">
      <div className="absolute top-3 right-3 z-10 flex flex-col gap-1">
        <IconButton icon={ZoomIn} label="Zoom in" onClick={() => handleZoom(1.4)} />
        <IconButton icon={ZoomOut} label="Zoom out" onClick={() => handleZoom(0.7)} />
        <IconButton icon={Maximize2} label="Reset view" onClick={handleReset} />
      </div>

      <Legend />

      <svg ref={svgRef} width="100%" height="100%" role="img" aria-label="Dependency graph">
        <g ref={gRef}>
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="22"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M0 0L10 5L0 10z" fill="#2dd4bf" fillOpacity="0.7" />
            </marker>
          </defs>

          {edges.map((e, i) => {
            const from = positions[e.source];
            const to = positions[e.target];
            if (!from || !to) return null;
            const dimmed =
              neighborSet && !(neighborSet.has(e.source) && neighborSet.has(e.target));
            return (
              <line
                key={i}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke={dimmed ? "#2b303c" : "#2dd4bf"}
                strokeOpacity={dimmed ? 0.3 : 0.8}
                strokeWidth={dimmed ? 1 : 1.5}
                markerEnd="url(#arrow)"
              />
            );
          })}

          {nodes.map((n) => {
            const pos = positions[n.id];
            if (!pos) return null;
            const isSelected = selectedId === n.id;
            const isNeighbor = neighborSet && neighborSet.has(n.id);
            const dimmed = neighborSet && !isNeighbor;

            // Subtle size hierarchy by connectivity — more-depended-on
            // files read as visually more central, without disrupting
            // the force layout's fixed collision radius (46px).
            const h = 26 + Math.min(8, n.degree * 1.2);
            const fontSize = 10.5 + Math.min(1.5, n.degree * 0.2);
            const w = Math.min(180, Math.max(64, n.label.length * 6.5 + 20));

            const hasExpectedOnly = !n.hasUnresolved && n.expectedCount > 0;

            const tooltipParts = [n.id];
            if (n.attentionCount > 0) {
              tooltipParts.push(
                `${n.attentionCount} unresolved import${n.attentionCount === 1 ? "" : "s"} need attention`
              );
            }
            if (n.expectedCount > 0) {
              tooltipParts.push(
                `${n.expectedCount} stdlib/third-party import${n.expectedCount === 1 ? "" : "s"} (expected)`
              );
            }

            return (
              <g
                key={n.id}
                transform={`translate(${pos.x - w / 2}, ${pos.y - h / 2})`}
                onClick={() => onSelectNode(n.id)}
                style={{ cursor: "pointer" }}
                opacity={dimmed ? 0.35 : 1}
              >
                <title>{tooltipParts.join(" — ")}</title>
                <rect
                  width={w}
                  height={h}
                  rx={6}
                  fill={n.hasUnresolved ? "#2e2312" : "#132b28"}
                  stroke={
                    isSelected ? "#2dd4bf" : n.hasUnresolved ? "#f2a93b" : "#2a5f59"
                  }
                  strokeWidth={isSelected ? 2 : 1}
                  strokeDasharray={hasExpectedOnly ? "2 2" : undefined}
                />
                <text
                  x={w / 2}
                  y={h / 2}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontFamily="ui-monospace, monospace"
                  fontSize={fontSize}
                  fill="#e8eaf0"
                >
                  {n.label}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}

function Legend() {
  return (
    <div className="absolute bottom-3 left-3 z-10 bg-zinc-900/85 border border-zinc-800 rounded-md px-3 py-2 text-[10px] text-zinc-400 space-y-1.5 backdrop-blur-sm">
      <div className="flex items-center gap-2">
        <span className="w-3 h-3 rounded-sm border border-[#2a5f59] bg-[#132b28] shrink-0" />
        resolved cleanly
      </div>
      <div className="flex items-center gap-2">
        <span className="w-3 h-3 rounded-sm border border-[#f2a93b] bg-[#2e2312] shrink-0" />
        needs attention
      </div>
      <div className="flex items-center gap-2">
        <span
          className="w-3 h-3 rounded-sm border border-dashed border-[#2a5f59] bg-[#132b28] shrink-0"
        />
        only stdlib/third-party
      </div>
      <div className="flex items-center gap-2 pt-0.5 border-t border-zinc-800">
        larger box = more connected
      </div>
    </div>
  );
}

function IconButton({ icon: Icon, label, onClick }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      className="w-7 h-7 flex items-center justify-center rounded-md border border-zinc-700 bg-zinc-900/80 text-zinc-300 hover:border-teal-500 hover:text-teal-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
    >
      <Icon className="w-3.5 h-3.5" aria-hidden="true" />
    </button>
  );
}
