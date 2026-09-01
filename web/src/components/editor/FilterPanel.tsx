import { useEditorStore } from "@/hooks/useEditor";
import { useFilters } from "@/hooks/templates";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function FilterPanel() {
  const filter = useEditorStore((s) => s.filter);
  const intensity = useEditorStore((s) => s.filterIntensity);
  const setFilter = useEditorStore((s) => s.setFilter);
  const setIntensity = useEditorStore((s) => s.setIntensity);

  const { data, isLoading } = useFilters();
  const presets = data?.presets ?? [];
  const userPresets = data?.user ?? [];

  return (
    <section className="flex h-32 flex-col gap-y-2 border-t bg-white px-3 py-2">
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Filters</h3>
        {filter && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setFilter(null)}
            className="text-xs"
          >
            Clear
          </Button>
        )}
      </header>

      <div className="flex flex-wrap gap-1.5 overflow-x-auto">
        {isLoading && (
          <span className="text-xs text-muted-foreground">Loading…</span>
        )}
        {presets.map((p) => (
          <button
            key={p.name}
            type="button"
            onClick={() => setFilter(p.name)}
            className={cn(
              "rounded border px-2 py-1 text-xs",
              filter === p.name
                ? "border-sky-500 bg-sky-50 text-sky-700"
                : "border-stone-200 bg-white hover:bg-stone-50",
            )}
            data-testid="filter-preset"
          >
            {p.name}
          </button>
        ))}
        {userPresets.length > 0 && (
          <div className="ml-2 flex items-center gap-1 border-l pl-2 text-xs text-muted-foreground">
            <span>Custom:</span>
            {userPresets.map((p) => (
              <button
                key={p.id ?? p.name}
                type="button"
                onClick={() => setFilter(p.name)}
                className={cn(
                  "rounded border px-2 py-1 text-xs",
                  filter === p.name
                    ? "border-sky-500 bg-sky-50 text-sky-700"
                    : "border-stone-200 bg-white hover:bg-stone-50",
                )}
              >
                {p.name}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 text-xs">
        <label htmlFor="filter-intensity" className="w-20 text-muted-foreground">
          Intensity
        </label>
        <Input
          id="filter-intensity"
          type="range"
          min={0}
          max={2}
          step={0.05}
          value={intensity}
          onChange={(e) => setIntensity(parseFloat(e.target.value))}
          className="h-2 max-w-xs"
          aria-label="Filter intensity"
        />
        <span className="w-10 tabular-nums text-muted-foreground">
          {Math.round(intensity * 100)}%
        </span>
      </div>
    </section>
  );
}