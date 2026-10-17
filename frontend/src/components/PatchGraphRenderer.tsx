import { useMemo, useState } from "react";
import type { PatchEdge, PatchGraph } from "@/types/canon";

type GraphView = "beginner" | "structural" | "diagnostic";

function cableLabel(edge: PatchEdge) {
  const flags = [edge.attenuate ? "attenuated" : "", edge.breaks_normal ? "breaks normal" : ""]
    .filter(Boolean)
    .join(", ");
  return `${edge.signal_type}${flags ? `, ${flags}` : ""}`;
}

export default function PatchGraphRenderer({ graph }: { graph: PatchGraph }) {
  const [view, setView] = useState<GraphView>("beginner");
  const [selectedEdgeId, setSelectedEdgeId] = useState(graph.edges[0]?.edge_id ?? "");
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const ports = useMemo(
    () => new Map(graph.nodes.flatMap((node) => node.ports.map((port) => [port.port_id, port]))),
    [graph.nodes],
  );
  const orderedNodes = useMemo(
    () => [...graph.nodes].sort((a, b) => a.node_id.localeCompare(b.node_id)),
    [graph.nodes],
  );
  const positions = useMemo(
    () =>
      new Map(
        orderedNodes.map((node, index) => [
          node.node_id,
          { x: 90 + index * 190, y: 110 + (index % 2) * 90 },
        ]),
      ),
    [orderedNodes],
  );
  const nodeForPort = (portId: string) =>
    orderedNodes.find((node) => node.ports.some((port) => port.port_id === portId));

  const selectRelative = (offset: number) => {
    if (!graph.edges.length) return;
    const current = graph.edges.findIndex((edge) => edge.edge_id === selectedEdgeId);
    const next = (Math.max(current, 0) + offset + graph.edges.length) % graph.edges.length;
    setSelectedEdgeId(graph.edges[next].edge_id);
  };

  return (
    <section className="patch-graph" aria-labelledby="patch-graph-title">
      <div className="patch-graph-header">
        <div>
          <p className="eyebrow">Synchronized graph and cable table</p>
          <h2 id="patch-graph-title">Patch structure</h2>
        </div>
        <div className="graph-controls" aria-label="Graph controls">
          <button
            className="button button-quiet"
            type="button"
            onClick={() => setZoom(Math.min(2, zoom + 0.2))}
            aria-label="Zoom in"
          >
            +
          </button>
          <button
            className="button button-quiet"
            type="button"
            onClick={() => setZoom(Math.max(0.5, zoom - 0.2))}
            aria-label="Zoom out"
          >
            −
          </button>
          <button
            className="button button-quiet"
            type="button"
            onClick={() => {
              setZoom(0.85);
              setPan({ x: 0, y: 0 });
            }}
          >
            Fit
          </button>
          <button
            className="button button-quiet"
            type="button"
            onClick={() => {
              setZoom(1);
              setPan({ x: 0, y: 0 });
            }}
          >
            Reset
          </button>
        </div>
      </div>

      <fieldset className="view-switcher">
        <legend>Detail level</legend>
        {(["beginner", "structural", "diagnostic"] as GraphView[]).map((option) => (
          <label key={option}>
            <input
              type="radio"
              name="graph-view"
              value={option}
              checked={view === option}
              onChange={() => setView(option)}
            />
            <span>{option[0].toUpperCase() + option.slice(1)}</span>
          </label>
        ))}
      </fieldset>

      <div
        className="graph-canvas"
        role="application"
        aria-label="Patch graph. Use left and right arrow keys to traverse cables."
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "ArrowRight" || event.key === "ArrowDown") {
            event.preventDefault();
            selectRelative(1);
          }
          if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
            event.preventDefault();
            selectRelative(-1);
          }
          if (event.key === "w") setPan((value) => ({ ...value, y: value.y + 20 }));
          if (event.key === "s") setPan((value) => ({ ...value, y: value.y - 20 }));
          if (event.key === "a") setPan((value) => ({ ...value, x: value.x + 20 }));
          if (event.key === "d") setPan((value) => ({ ...value, x: value.x - 20 }));
        }}
      >
        <svg viewBox="0 0 720 360" aria-hidden="true">
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" />
            </marker>
          </defs>
          <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
            {graph.edges.map((edge) => {
              const sourceNode = nodeForPort(edge.source_port_id);
              const targetNode = nodeForPort(edge.target_port_id);
              if (!sourceNode || !targetNode) return null;
              const source = positions.get(sourceNode.node_id)!;
              const target = positions.get(targetNode.node_id)!;
              return (
                <line
                  key={edge.edge_id}
                  className={`graph-edge graph-edge-${edge.signal_type}${selectedEdgeId === edge.edge_id ? " selected" : ""}`}
                  x1={source.x + 110}
                  y1={source.y + 28}
                  x2={target.x}
                  y2={target.y + 28}
                  markerEnd="url(#arrow)"
                  strokeDasharray={
                    edge.signal_type === "cv"
                      ? "8 5"
                      : edge.signal_type === "gate"
                        ? "2 5"
                        : undefined
                  }
                />
              );
            })}
            {orderedNodes.map((node) => {
              const position = positions.get(node.node_id)!;
              return (
                <g key={node.node_id} transform={`translate(${position.x} ${position.y})`}>
                  <rect className="graph-node" width="110" height="56" rx="5" />
                  <text className="graph-node-label" x="10" y="23">
                    {node.label}
                  </text>
                  {view !== "beginner" ? (
                    <text className="graph-node-meta" x="10" y="42">
                      {node.active_mode || "default mode"}
                    </text>
                  ) : null}
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      <div className="cable-table-wrap">
        <table className="cable-table">
          <caption>
            Structured cable list; selecting a row highlights the same cable in the graph.
          </caption>
          <thead>
            <tr>
              <th scope="col">Cable</th>
              <th scope="col">From</th>
              <th scope="col">To</th>
              <th scope="col">Signal and safety</th>
            </tr>
          </thead>
          <tbody>
            {graph.edges.map((edge) => {
              const source = ports.get(edge.source_port_id);
              const target = ports.get(edge.target_port_id);
              const selected = selectedEdgeId === edge.edge_id;
              return (
                <tr key={edge.edge_id} className={selected ? "selected" : undefined}>
                  <th scope="row">
                    <button
                      type="button"
                      onClick={() => setSelectedEdgeId(edge.edge_id)}
                      aria-pressed={selected}
                    >
                      {edge.edge_id}
                    </button>
                  </th>
                  <td>
                    {source?.module_instance_id} · {source?.label}{" "}
                    <span className="direction">OUT</span>
                  </td>
                  <td>
                    {target?.module_instance_id} · {target?.label}{" "}
                    <span className="direction">IN</span>
                  </td>
                  <td>
                    <span className={`cable-swatch cable-${edge.signal_type}`} aria-hidden="true" />
                    {cableLabel(edge)}
                    {edge.feedback_cycle_id ? ` · feedback ${edge.feedback_cycle_id}` : ""}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {graph.edges.some((edge) => edge.feedback_cycle_id) ? (
        <p className="status status-warning">
          Feedback paths are declared in the cable table. Begin at minimum gain and follow the
          threshold phase.
        </p>
      ) : null}
    </section>
  );
}
