import { useRef, useState, useEffect } from "react";
import * as d3 from "d3";

/**
 * Runs a d3-force simulation over the given nodes/edges and returns live
 * {id: {x, y}} positions as state, updated on every simulation tick.
 *
 * Positions (not DOM nodes) are handed back so rendering stays fully
 * React-controlled — d3 only computes the physics, React owns the SVG.
 */
export function useForceLayout(nodes, edges, width, height) {
  const [positions, setPositions] = useState({});
  const prevNodesRef = useRef([]);

  useEffect(() => {
    if (!nodes.length || width === 0 || height === 0) {
      setPositions({});
      return undefined;
    }

    const simNodes = nodes.map((n) => {
      const prev = prevNodesRef.current.find((p) => p.id === n.id);
      return prev
        ? { ...n, x: prev.x, y: prev.y }
        : {
            ...n,
            x: width / 2 + (Math.random() - 0.5) * 40,
            y: height / 2 + (Math.random() - 0.5) * 40,
          };
    });
    const simEdges = edges.map((e) => ({ ...e }));

    const simulation = d3
      .forceSimulation(simNodes)
      .force(
        "link",
        d3.forceLink(simEdges).id((d) => d.id).distance(95).strength(0.5)
      )
      .force("charge", d3.forceManyBody().strength(-260))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collide", d3.forceCollide(46))
      .alphaDecay(0.03);

    simulation.on("tick", () => {
      prevNodesRef.current = simNodes;
      const pos = {};
      simNodes.forEach((n) => {
        pos[n.id] = { x: n.x, y: n.y };
      });
      setPositions(pos);
    });

    return () => simulation.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, width, height]);

  return positions;
}
