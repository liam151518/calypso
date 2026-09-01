import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Play, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PipelineCanvas } from "@/components/pipeline/PipelineCanvas";
import { NodePalette } from "@/components/pipeline/NodePalette";
import { Inspector } from "@/components/pipeline/Inspector";
import {
  useNodeSchemas,
  usePipeline,
  usePipelineRuns,
  useRunPipeline,
  useUpdatePipeline,
} from "@/lib/query";
import type { PipelineEdge, PipelineNode } from "@/lib/types";

export function PipelinePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const pid = id ? Number(id) : null;
  const { data: pipeline } = usePipeline(pid);
  const { data: schemas } = useNodeSchemas();
  const update = useUpdatePipeline();
  const run = useRunPipeline();
  const { data: runs } = usePipelineRuns(pid);

  const [name, setName] = useState("");
  const [nodes, setNodes] = useState<PipelineNode[]>([]);
  const [edges, setEdges] = useState<PipelineEdge[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Hydrate local state when pipeline loads
  useEffect(() => {
    if (!pipeline) return;
    setName(pipeline.name);
    setNodes(pipeline.nodes);
    setEdges(pipeline.edges);
  }, [pipeline?.id]);

  const selected = useMemo(
    () => nodes.find((n) => n.id === selectedId) ?? null,
    [nodes, selectedId],
  );

  const selectedSchema = useMemo(
    () => (selected && schemas ? schemas.schemas[selected.type] ?? null : null),
    [selected, schemas],
  );

  if (!schemas || !pipeline) {
    return (
      <div className="p-6 text-sm text-muted-foreground">Loading pipeline…</div>
    );
  }

  function addNode(type: string) {
    const baseId = type.replace(/[^a-z0-9]/gi, "");
    let nid = baseId;
    let i = 1;
    while (nodes.some((n) => n.id === nid)) {
      i += 1;
      nid = `${baseId}${i}`;
    }
    setNodes((prev) => [
      ...prev,
      {
        id: nid,
        type,
        params: defaultParamsFor(type),
        position: { x: 80 + nodes.length * 30, y: 80 + nodes.length * 30 },
      },
    ]);
    setSelectedId(nid);
  }

  function moveNode(id: string, x: number, y: number) {
    setNodes((prev) =>
      prev.map((n) => (n.id === id ? { ...n, position: { x, y } } : n)),
    );
  }

  function connect(source: string, target: string) {
    if (source === target) return;
    if (edges.some((e) => e.source === source && e.target === target)) return;
    setEdges((prev) => [...prev, { source, target }]);
  }

  function deleteSelected() {
    if (!selectedId) return;
    setNodes((prev) => prev.filter((n) => n.id !== selectedId));
    setEdges((prev) =>
      prev.filter((e) => e.source !== selectedId && e.target !== selectedId),
    );
    setSelectedId(null);
  }

  function renameSelected(newId: string) {
    if (!selectedId || newId === selectedId) return;
    if (nodes.some((n) => n.id === newId)) return;
    setNodes((prev) =>
      prev.map((n) => (n.id === selectedId ? { ...n, id: newId } : n)),
    );
    setEdges((prev) =>
      prev.map((e) => ({
        ...e,
        source: e.source === selectedId ? newId : e.source,
        target: e.target === selectedId ? newId : e.target,
      })),
    );
    setSelectedId(newId);
  }

  function updateParams(params: Record<string, unknown>) {
    if (!selectedId) return;
    setNodes((prev) =>
      prev.map((n) =>
        n.id === selectedId ? { ...n, params: { ...params } } : n,
      ),
    );
  }

  function save() {
    if (pid == null) return;
    update.mutate({ id: pid, data: { name, nodes, edges } });
  }

  function runNow() {
    if (pid == null) return;
    save();
    run.mutate({ id: pid });
  }

  return (
    <div className="flex h-full flex-col gap-3 p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Button size="icon" variant="ghost" onClick={() => navigate("/pipelines")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="max-w-xs text-base font-medium"
            data-testid="pipeline-name"
          />
          <span className="text-xs text-muted-foreground">
            {nodes.length} nodes · {edges.length} edges
          </span>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={save} disabled={update.isPending}>
            <Save className="mr-2 h-4 w-4" /> Save
          </Button>
          <Button onClick={runNow} disabled={run.isPending}>
            <Play className="mr-2 h-4 w-4" /> Run
          </Button>
        </div>
      </div>
      <div className="grid flex-1 grid-cols-[16rem_1fr_20rem] gap-3 overflow-hidden">
        <Card className="overflow-auto p-3">
          <NodePalette schemas={schemas} onAdd={addNode} />
        </Card>
        <PipelineCanvas
          nodes={nodes}
          edges={edges}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onMoveNode={moveNode}
          onConnect={connect}
          schemas={schemas.schemas}
        />
        <div className="space-y-3 overflow-auto">
          <Inspector
            node={selected}
            schema={selectedSchema}
            onChange={updateParams}
            onDelete={deleteSelected}
            onRename={renameSelected}
          />
          <RunHistory runs={runs ?? []} />
        </div>
      </div>
    </div>
  );
}

function RunHistory({ runs }: { runs: Array<{ id: number; status: string; started_at: number | null; finished_at: number | null; spent_usd: number; log: Array<{ t: number; node: string; msg: string }> }> }) {
  return (
    <Card className="p-3">
      <h3 className="text-sm font-medium">Recent runs</h3>
      {runs.length === 0 ? (
        <div className="mt-2 text-xs text-muted-foreground">No runs yet.</div>
      ) : (
        <ul className="mt-2 space-y-2 text-xs">
          {runs.slice(0, 5).map((r) => (
            <li key={r.id} className="rounded-md border border-border p-2">
              <div className="flex items-center justify-between">
                <span className="font-medium">#{r.id} · {r.status}</span>
                <span className="text-muted-foreground">${r.spent_usd.toFixed(3)}</span>
              </div>
              <ul className="mt-1 max-h-32 overflow-auto text-[11px] text-muted-foreground">
                {r.log.slice(-10).map((e, i) => (
                  <li key={i}>
                    <span className="font-mono">{e.node}</span> · {e.msg}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function defaultParamsFor(type: string): Record<string, unknown> {
  // Best-effort default values that match schema defaults.
  switch (type) {
    case "trigger":
      return { mode: "manual" };
    case "brand":
      return { brand_id: 0 };
    case "reference":
      return { mode: "tag", tag: "", limit: 8 };
    case "prompt":
      return { mode: "inline", body: "" };
    case "model":
      return { model_id: "minimax/h3" };
    case "cost_guard":
      return { max_usd: 5 };
    case "generate":
      return { duration: 8, resolution: "768p" };
    case "image":
      return { aspect_ratio: "1:1", num_images: 1 };
    case "combine":
      return { mode: "concat", crossfade_ms: 250 };
    case "export":
      return { destination: "outputs" };
    default:
      return {};
  }
}
