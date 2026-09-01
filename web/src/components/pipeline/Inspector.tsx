import { Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { NodeSchema, PipelineNode } from "@/lib/types";

type Props = {
  node: PipelineNode | null;
  schema: NodeSchema | null;
  onChange: (params: Record<string, unknown>) => void;
  onDelete: () => void;
  onRename: (id: string) => void;
};

export function Inspector({ node, schema, onChange, onDelete, onRename }: Props) {
  if (!node || !schema) {
    return (
      <div className="rounded-md border border-border bg-card/40 p-3 text-xs text-muted-foreground">
        Select a node to edit its parameters.
      </div>
    );
  }
  const params = (node.params ?? {}) as Record<string, unknown>;
  const propsSchema = (schema.params?.properties ?? {}) as Record<string, { type: string; enum?: unknown[]; default?: unknown; title?: string; description?: string; minimum?: number; maximum?: number; items?: { type: string } }>;

  return (
    <div className="space-y-3 rounded-md border border-border bg-card/40 p-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">{schema.title}</h3>
        <Button size="icon" variant="ghost" onClick={onDelete}>
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
      <div>
        <label className="text-xs text-muted-foreground">Node id</label>
        <Input
          value={node.id}
          onChange={(e) => onRename(e.target.value || node.id)}
        />
      </div>
      {Object.entries(propsSchema).map(([key, prop]) => (
        <SchemaField
          key={key}
          name={key}
          prop={prop}
          value={params[key] ?? prop.default ?? ""}
          onChange={(v) => onChange({ ...params, [key]: v })}
        />
      ))}
    </div>
  );
}

function SchemaField({
  name,
  prop,
  value,
  onChange,
}: {
  name: string;
  prop: { type: string; enum?: unknown[]; default?: unknown; title?: string; description?: string; minimum?: number; maximum?: number; items?: { type: string } };
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const id = `inspector-${name}`;
  const label = prop.title ?? name;
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </label>
      {prop.enum ? (
        <select
          id={id}
          className="block w-full rounded-md border border-border bg-background px-2 py-1 text-sm"
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
          data-testid={`field-${name}`}
        >
          {prop.enum.map((opt) => (
            <option key={String(opt)} value={String(opt)}>
              {String(opt)}
            </option>
          ))}
        </select>
      ) : prop.type === "number" || prop.type === "integer" ? (
        <Input
          id={id}
          type="number"
          value={String(value ?? 0)}
          min={prop.minimum}
          max={prop.maximum}
          onChange={(e) => onChange(Number(e.target.value))}
          data-testid={`field-${name}`}
        />
      ) : prop.type === "array" ? (
        <Input
          id={id}
          value={Array.isArray(value) ? (value as string[]).join(", ") : ""}
          onChange={(e) =>
            onChange(
              e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
            )
          }
          data-testid={`field-${name}`}
        />
      ) : (
        <Input
          id={id}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
          data-testid={`field-${name}`}
        />
      )}
      {prop.description ? (
        <div className="text-[10px] text-muted-foreground">{prop.description}</div>
      ) : null}
    </div>
  );
}
