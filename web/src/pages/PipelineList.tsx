import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Play, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useCreatePipeline, useDeletePipeline, usePipelines, useRunPipeline } from "@/lib/query";

export function PipelineList() {
  const navigate = useNavigate();
  const { data: pipelines } = usePipelines();
  const create = useCreatePipeline();
  const del = useDeletePipeline();
  const run = useRunPipeline();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Pipelines</h1>
          <p className="text-sm text-muted-foreground">
            Visual generator funnels. Combine trigger, prompt, model, generate and export
            nodes. They execute topologically with live cost tracking.
          </p>
          <details className="mt-2 text-xs text-muted-foreground">
            <summary className="cursor-pointer select-none">What is a pipeline?</summary>
            <div className="mt-2 space-y-1">
              <p>
                A pipeline is a chain of steps. Each step takes an input, runs a job, and
                hands its output to the next step.
              </p>
              <p>
                Drag nodes onto the canvas, draw wires between them, then run. The
                executor follows the wires in order and tracks the cost as it goes.
              </p>
            </div>
          </details>
        </div>
        <Button onClick={() => setOpen(true)}>
          <Plus className="mr-2 h-4 w-4" /> New pipeline
        </Button>
      </div>

      <Card className="p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase text-muted-foreground">
              <th className="p-3">id</th>
              <th className="p-3">name</th>
              <th className="p-3">nodes</th>
              <th className="p-3">edges</th>
              <th className="p-3">workers</th>
              <th className="p-3" />
            </tr>
          </thead>
          <tbody>
            {(pipelines ?? []).map((p) => (
              <tr
                key={p.id}
                className="cursor-pointer border-b border-border/50 hover:bg-card/60"
                onClick={() => navigate(`/pipelines/${p.id}`)}
              >
                <td className="p-3 text-muted-foreground">{p.id}</td>
                <td className="p-3 font-medium">{p.name}</td>
                <td className="p-3">{p.nodes.length}</td>
                <td className="p-3">{p.edges.length}</td>
                <td className="p-3">{p.max_workers}</td>
                <td className="p-3" onClick={(ev) => ev.stopPropagation()}>
                  <div className="flex gap-1">
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => run.mutate({ id: p.id })}
                      disabled={run.isPending}
                      data-testid={`run-${p.id}`}
                    >
                      <Play className="h-4 w-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => {
                        if (confirm(`Delete "${p.name}"?`)) del.mutate(p.id);
                      }}
                      data-testid={`delete-${p.id}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New pipeline</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium">Name</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="promo-1"
                data-testid="new-pipeline-name"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Description</label>
              <Textarea
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
                placeholder="Optional"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!name.trim() || create.isPending}
              onClick={() => {
                create.mutate(
                  { name, description: desc, nodes: [], edges: [], max_workers: 2 },
                  {
                    onSuccess: (p) => {
                      setOpen(false);
                      setName("");
                      setDesc("");
                      navigate(`/pipelines/${p.id}`);
                    },
                  },
                );
              }}
            >
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
