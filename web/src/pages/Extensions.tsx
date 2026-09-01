import { useState } from "react";
import { Power, PowerOff, RotateCw, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useExtensions, useToggleExtension } from "@/lib/query";

type ExtItem = {
  id: string;
  version: string;
  type: string;
  name: string;
  author: string;
  description: string;
  homepage: string;
  license: string;
  checksum: string;
  signed: boolean;
  enabled: boolean;
};

export function ExtensionsPage() {
  const { data: items, isFetching, refetch } = useExtensions();
  const toggle = useToggleExtension();
  const [filter, setFilter] = useState<string>("");

  const filtered = (items ?? []).filter(
    (e) => !filter || e.type === filter || e.name.toLowerCase().includes(filter.toLowerCase()),
  );

  const types = Array.from(new Set((items ?? []).map((e) => e.type))).sort();

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Extensions</h1>
          <p className="text-sm text-muted-foreground">
            Calypso is a platform. Install community extensions to add
            models, agents, pipeline nodes, channels, forms, and importers.
          </p>
        </div>
        <Button variant="outline" onClick={() => refetch()}>
          <RotateCw className="mr-2 h-4 w-4" /> Refresh
        </Button>
      </div>

      <div className="flex gap-2 text-xs">
        <Button
          size="sm"
          variant={filter === "" ? "default" : "outline"}
          onClick={() => setFilter("")}
        >
          All
        </Button>
        {types.map((t) => (
          <Button
            key={t}
            size="sm"
            variant={filter === t ? "default" : "outline"}
            onClick={() => setFilter(t)}
            data-testid={`filter-${t}`}
          >
            {t}
          </Button>
        ))}
      </div>

      {isFetching ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : null}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((e) => (
          <ExtensionCard key={e.id} item={e} onToggle={toggle.mutate} />
        ))}
      </div>
    </div>
  );
}

function ExtensionCard({
  item,
  onToggle,
}: {
  item: ExtItem;
  onToggle: (p: { id: string; enable: boolean }) => void;
}) {
  return (
    <Card className="p-4" data-testid={`extension-${item.id}`}>
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-medium">{item.name}</h3>
          <div className="text-xs text-muted-foreground">
            {item.id} · v{item.version} · {item.type}
          </div>
        </div>
        {item.signed ? (
          <ShieldCheck
            className="h-4 w-4 text-green-500"
            aria-label="signed"
          />
        ) : null}
      </div>
      <p className="mt-2 line-clamp-3 text-xs text-muted-foreground">
        {item.description || "(no description)"}
      </p>
      <div className="mt-3 flex items-center justify-between text-xs">
        <div className="text-muted-foreground">
          {item.author ? `by ${item.author} · ` : ""} {item.license}
        </div>
        <Button
          size="sm"
          variant={item.enabled ? "outline" : "default"}
          onClick={() => onToggle({ id: item.id, enable: !item.enabled })}
          data-testid={`toggle-${item.id}`}
        >
          {item.enabled ? (
            <>
              <PowerOff className="mr-1 h-3 w-3" /> Disable
            </>
          ) : (
            <>
              <Power className="mr-1 h-3 w-3" /> Enable
            </>
          )}
        </Button>
      </div>
    </Card>
  );
}
