import { useEffect, useMemo, useRef, useState } from "react";

import type { PipelineEdge, PipelineNode, NodeSchema } from "@/lib/types";

type Props = {
  nodes: PipelineNode[];
  edges: PipelineEdge[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onMoveNode: (id: string, x: number, y: number) => void;
  onConnect: (source: string, target: string) => void;
  schemas: Record<string, NodeSchema>;
};

const NODE_W = 180;
const NODE_H = 64;

export function PipelineCanvas({
  nodes,
  edges,
  selectedId,
  onSelect,
  onMoveNode,
  onConnect,
  schemas,
}: Props) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [connectFrom, setConnectFrom] = useState<string | null>(null);

  const positions = useMemo(() => {
    const out: Record<string, { x: number; y: number }> = {};
    for (const n of nodes) {
      out[n.id] = n.position ?? { x: 60, y: 60 + Object.keys(out).length * 90 };
    }
    return out;
  }, [nodes]);

  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!draggingId || !svgRef.current) return;
      const rect = svgRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left - NODE_W / 2;
      const y = e.clientY - rect.top - NODE_H / 2;
      onMoveNode(draggingId, Math.max(0, x), Math.max(0, y));
    }
    function onUp() {
      setDraggingId(null);
    }
    if (draggingId) {
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
      return () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };
    }
  }, [draggingId, onMoveNode]);

  return (
    <div className="relative h-full w-full overflow-auto rounded-md border border-border bg-card/40">
      <svg
        ref={svgRef}
        width={1200}
        height={900}
        className="block"
        onMouseDown={() => onSelect(null)}
      >
        {/* edges */}
        {edges.map((e, i) => {
          const a = positions[e.source];
          const b = positions[e.target];
          if (!a || !b) return null;
          const x1 = a.x + NODE_W;
          const y1 = a.y + NODE_H / 2;
          const x2 = b.x;
          const y2 = b.y + NODE_H / 2;
          const mx = (x1 + x2) / 2;
          return (
            <path
              key={i}
              d={`M ${x1} ${y1} C ${mx} ${y1} ${mx} ${y2} ${x2} ${y2}`}
              fill="none"
              stroke="hsl(var(--border))"
              strokeWidth={1.5}
            />
          );
        })}
        {/* nodes */}
        {nodes.map((n) => {
          const p = positions[n.id];
          const schema = schemas[n.type];
          const title = schema?.title ?? n.type;
          const selected = selectedId === n.id;
          return (
            <g
              key={n.id}
              transform={`translate(${p.x}, ${p.y})`}
              onMouseDown={(ev) => {
                ev.stopPropagation();
                onSelect(n.id);
              }}
              data-testid={`node-${n.id}`}
            >
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={6}
                fill={selected ? "hsl(var(--accent))" : "hsl(var(--card))"}
                stroke={selected ? "hsl(var(--signal))" : "hsl(var(--border))"}
                strokeWidth={selected ? 2 : 1}
                onMouseDown={(ev) => {
                  ev.stopPropagation();
                  setDraggingId(n.id);
                }}
                style={{ cursor: "grab" }}
              />
              <text x={12} y={22} fontSize={13} fill="hsl(var(--foreground))">
                {title}
              </text>
              <text x={12} y={42} fontSize={11} fill="hsl(var(--muted-foreground))">
                {n.id}
              </text>
              {/* input handle (left) */}
              {schema?.inputs?.map((port) => (
                <circle
                  key={port}
                  cx={0}
                  cy={NODE_H / 2}
                  r={5}
                  fill="hsl(var(--muted))"
                  onMouseUp={(ev) => {
                    ev.stopPropagation();
                    if (connectFrom && connectFrom !== n.id) {
                      onConnect(connectFrom, n.id);
                    }
                    setConnectFrom(null);
                  }}
                />
              ))}
              {/* output handle (right) */}
              {schema?.outputs?.map((port) => (
                <circle
                  key={port}
                  cx={NODE_W}
                  cy={NODE_H / 2}
                  r={5}
                  fill="hsl(var(--signal))"
                  onMouseDown={(ev) => {
                    ev.stopPropagation();
                    setConnectFrom(n.id);
                  }}
                  style={{ cursor: "crosshair" }}
                />
              ))}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
