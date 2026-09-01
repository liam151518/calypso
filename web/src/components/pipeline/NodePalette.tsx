import type { NodeSchemaResponse } from "@/lib/types";

type Props = {
  schemas: NodeSchemaResponse;
  onAdd: (type: string) => void;
};

export function NodePalette({ schemas, onAdd }: Props) {
  const grouped = schemas.categories;
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium">Add node</h3>
      {Object.entries(grouped).map(([category, types]) => (
        <div key={category} className="space-y-1">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            {category}
          </div>
          {types.map((t) => {
            const schema = schemas.schemas[t];
            return (
              <button
                key={t}
                className="w-full rounded-md border border-border bg-card/60 p-2 text-left text-xs hover:border-signal hover:bg-card"
                onClick={() => onAdd(t)}
                data-testid={`palette-${t}`}
              >
                <div className="font-medium text-foreground">{schema?.title ?? t}</div>
                <div className="text-[11px] text-muted-foreground line-clamp-2">
                  {schema?.description}
                </div>
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}
